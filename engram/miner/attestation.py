"""
Engram Miner — Namespace Attestation

Links a namespace to a Bittensor hotkey so its on-chain stake becomes a
trust signal for anyone querying that namespace.

How it works
------------
When a namespace is created with an owner_hotkey:
  1. The owner signs a canonical challenge: "engram-attest:{namespace}:{timestamp}"
  2. We verify the signature against their hotkey
  3. We read their TAO stake from the metagraph
  4. We assign a trust tier (sovereign / verified / community / anonymous)
  5. The attestation is persisted alongside the namespace

On every query result the trust_tier of the namespace is returned.
Agents decide which tier they are willing to trust — Engram enforces nothing
at the content level, but makes accountability legible and on-chain-verifiable.

Trust tiers (see config.py for thresholds):
  sovereign  — ≥1000 TAO staked
  verified   — ≥100  TAO staked
  community  — ≥1    TAO staked
  anonymous  — no hotkey provided, or stake below community threshold

Stake is refreshed from the metagraph every ATTESTATION_STAKE_REFRESH_SECS.
If the owner's stake drops below their tier threshold, the tier degrades
automatically — no manual intervention required.

Loophole acknowledgement
------------------------
A well-funded attacker CAN buy a high trust tier by staking TAO, then inject
bad content, then unstake. The economic cost of doing this at scale is the
defence — not cryptographic impossibility. Combined with private namespaces
(only you write) this covers the realistic threat model for production agents.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Optional

from loguru import logger

from engram.config import (
    ATTESTATION_STAKE_REFRESH_SECS,
    TRUST_TIER_COMMUNITY,
    TRUST_TIER_SOVEREIGN,
    TRUST_TIER_VERIFIED,
)

_DEFAULT_PATH = Path(os.getenv("ATTESTATION_REGISTRY_PATH", "data/attestations.json"))


# ── Trust tiers ───────────────────────────────────────────────────────────────

class TrustTier(str, Enum):
    SOVEREIGN  = "sovereign"   # ≥1000 TAO
    VERIFIED   = "verified"    # ≥100  TAO
    COMMUNITY  = "community"   # ≥1    TAO
    ANONYMOUS  = "anonymous"   # no hotkey / below threshold


def tier_from_stake(stake_tao: float) -> TrustTier:
    if stake_tao >= TRUST_TIER_SOVEREIGN:
        return TrustTier.SOVEREIGN
    if stake_tao >= TRUST_TIER_VERIFIED:
        return TrustTier.VERIFIED
    if stake_tao >= TRUST_TIER_COMMUNITY:
        return TrustTier.COMMUNITY
    return TrustTier.ANONYMOUS


# ── Attestation record ────────────────────────────────────────────────────────

@dataclass
class NamespaceAttestation:
    namespace:        str
    owner_hotkey:     str                    # SS58 address
    stake_tao:        float                  # TAO at last refresh
    trust_tier:       TrustTier
    attested_at:      float = field(default_factory=time.time)
    stake_refreshed_at: float = field(default_factory=time.time)

    @property
    def stake_stale(self) -> bool:
        return (time.time() - self.stake_refreshed_at) > ATTESTATION_STAKE_REFRESH_SECS

    def to_dict(self) -> dict:
        d = asdict(self)
        d["trust_tier"] = self.trust_tier.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "NamespaceAttestation":
        d = dict(d)
        d["trust_tier"] = TrustTier(d["trust_tier"])
        return cls(**d)


# ── Attestation registry ──────────────────────────────────────────────────────

class AttestationRegistry:
    """
    Persists and serves namespace attestations.

    Thread-safe. Stake is refreshed lazily when queried after going stale.
    """

    def __init__(
        self,
        path: Path = _DEFAULT_PATH,
        subtensor=None,
        netuid: Optional[int] = None,
    ) -> None:
        self._path     = path
        self._subtensor = subtensor
        self._netuid   = netuid
        self._lock     = Lock()
        self._records: dict[str, NamespaceAttestation] = self._load()

    # ── Public API ─────────────────────────────────────────────────────────────

    def attest(
        self,
        namespace:    str,
        owner_hotkey: str,
        signature_hex: str,
        timestamp_ms: int,
    ) -> NamespaceAttestation:
        """
        Create or update an attestation for a namespace.

        The owner must sign the canonical challenge:
            f"engram-attest:{namespace}:{timestamp_ms}"

        Args:
            namespace:     The namespace being attested.
            owner_hotkey:  SS58 address of the signing keypair.
            signature_hex: sr25519 signature over the canonical message (hex).
            timestamp_ms:  Unix milliseconds — must be within ±60s of server time.

        Returns:
            The created/updated NamespaceAttestation.

        Raises:
            ValueError on invalid signature, stale timestamp, or hotkey mismatch.
        """
        self._verify_timestamp(timestamp_ms)
        self._verify_signature(namespace, owner_hotkey, signature_hex, timestamp_ms)

        stake = self._fetch_stake(owner_hotkey)
        tier  = tier_from_stake(stake)

        att = NamespaceAttestation(
            namespace=namespace,
            owner_hotkey=owner_hotkey,
            stake_tao=stake,
            trust_tier=tier,
        )

        with self._lock:
            self._records[namespace] = att
            self._flush()

        logger.info(
            f"Namespace attested | ns={namespace!r} | hotkey={owner_hotkey[:12]}… "
            f"| stake=τ{stake:.2f} | tier={tier.value}"
        )
        return att

    def get(self, namespace: str) -> Optional[NamespaceAttestation]:
        """
        Return the attestation for a namespace, refreshing stake if stale.
        Returns None for unattested (anonymous) namespaces.
        """
        with self._lock:
            att = self._records.get(namespace)

        if att is None:
            return None

        if att.stake_stale:
            att = self._refresh_stake(att)

        return att

    def trust_tier(self, namespace: str) -> TrustTier:
        """Convenience: return the trust tier for a namespace (ANONYMOUS if unattested)."""
        att = self.get(namespace)
        return att.trust_tier if att else TrustTier.ANONYMOUS

    def revoke(self, namespace: str, owner_hotkey: str, signature_hex: str, timestamp_ms: int) -> bool:
        """
        Remove an attestation. Requires a valid signature from the owner.
        Returns True if removed, False if not found.
        """
        att = self.get(namespace)
        if att is None:
            return False
        if att.owner_hotkey != owner_hotkey:
            raise ValueError("Only the original owner can revoke an attestation.")
        self._verify_timestamp(timestamp_ms)
        self._verify_signature(namespace, owner_hotkey, signature_hex, timestamp_ms)

        with self._lock:
            self._records.pop(namespace, None)
            self._flush()

        logger.info(f"Attestation revoked | ns={namespace!r} | hotkey={owner_hotkey[:12]}…")
        return True

    def list_attested(self) -> list[NamespaceAttestation]:
        with self._lock:
            return list(self._records.values())

    # ── Stake refresh ──────────────────────────────────────────────────────────

    def _refresh_stake(self, att: NamespaceAttestation) -> NamespaceAttestation:
        stake = self._fetch_stake(att.owner_hotkey)
        tier  = tier_from_stake(stake)

        if tier != att.trust_tier:
            logger.info(
                f"Trust tier changed | ns={att.namespace!r} | "
                f"{att.trust_tier.value} → {tier.value} | stake=τ{stake:.2f}"
            )

        att.stake_tao        = stake
        att.trust_tier       = tier
        att.stake_refreshed_at = time.time()

        with self._lock:
            self._records[att.namespace] = att
            self._flush()

        return att

    def _fetch_stake(self, hotkey: str) -> float:
        """Read TAO stake from metagraph. Returns 0.0 if unavailable."""
        if self._subtensor is None or self._netuid is None:
            logger.debug("Subtensor not configured — stake defaults to 0.0")
            return 0.0
        try:
            stake = self._subtensor.get_stake_for_coldkey_and_hotkey(
                coldkey_ss58=hotkey,
                hotkey_ss58=hotkey,
                netuid=self._netuid,
            )
            return float(stake)
        except Exception as exc:
            logger.warning(f"Stake fetch failed for {hotkey[:12]}…: {exc} — defaulting to 0.0")
            return 0.0

    # ── Signature verification ─────────────────────────────────────────────────

    @staticmethod
    def _verify_timestamp(timestamp_ms: int, window_secs: float = 60.0) -> None:
        now_ms = int(time.time() * 1000)
        if abs(now_ms - timestamp_ms) > window_secs * 1000:
            raise ValueError(
                f"Attestation timestamp is outside the ±{int(window_secs)}s window. "
                "Check your system clock."
            )

    @staticmethod
    def _canonical_message(namespace: str, timestamp_ms: int) -> bytes:
        return f"engram-attest:{namespace}:{timestamp_ms}".encode()

    @classmethod
    def _verify_signature(
        cls,
        namespace:     str,
        owner_hotkey:  str,
        signature_hex: str,
        timestamp_ms:  int,
    ) -> None:
        message = cls._canonical_message(namespace, timestamp_ms)
        try:
            sig_bytes = bytes.fromhex(signature_hex.removeprefix("0x"))
        except ValueError:
            raise ValueError("signature_hex must be a valid hex string.")

        try:
            import bittensor as bt
            kp = bt.Keypair(ss58_address=owner_hotkey)
            if not kp.verify(message, sig_bytes):
                raise ValueError(
                    f"Signature verification failed for hotkey {owner_hotkey[:12]}…. "
                    "Sign the canonical message: f'engram-attest:{namespace}:{timestamp_ms}'"
                )
        except ImportError:
            logger.warning("bittensor not installed — skipping signature verification (dev mode)")
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Signature verification error: {exc}") from exc

    # ── Persistence ────────────────────────────────────────────────────────────

    def _load(self) -> dict[str, NamespaceAttestation]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return {k: NamespaceAttestation.from_dict(v) for k, v in raw.items()}
        except Exception as exc:
            logger.warning(f"Failed to load attestations from {self._path}: {exc}")
            return {}

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        try:
            tmp.write_text(
                json.dumps({k: v.to_dict() for k, v in self._records.items()}, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self._path)
        except Exception as exc:
            logger.error(f"Failed to flush attestations: {exc}")
            tmp.unlink(missing_ok=True)


# ── Signing helper (for SDK / tests) ─────────────────────────────────────────

def build_attestation_payload(
    keypair,      # bt.Keypair
    namespace: str,
) -> dict:
    """
    Build the signed payload needed to call the /attest endpoint.

    Usage:
        from engram.miner.attestation import build_attestation_payload
        import bittensor as bt

        wallet = bt.wallet(name="my_wallet")
        payload = build_attestation_payload(wallet.hotkey, "my_namespace")
        # POST payload to /AttestNamespace
    """
    timestamp_ms = int(time.time() * 1000)
    message = f"engram-attest:{namespace}:{timestamp_ms}".encode()
    sig_hex = "0x" + keypair.sign(message).hex()
    return {
        "namespace":    namespace,
        "owner_hotkey": keypair.ss58_address,
        "signature":    sig_hex,
        "timestamp_ms": timestamp_ms,
    }
