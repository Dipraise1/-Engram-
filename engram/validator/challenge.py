"""
Engram Validator — Storage Challenge Dispatcher

Periodically challenges miners to prove they hold stored CIDs.
Uses the Rust engram_core module for challenge generation and verification.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from loguru import logger

from engram.config import CHALLENGE_TIMEOUT_SECS, SLASH_THRESHOLD

try:
    import engram_core
    _RUST_AVAILABLE = True
except ImportError:
    _RUST_AVAILABLE = False
    logger.warning("engram_core (Rust) not available — storage proof challenges disabled.")


@dataclass
class MinerProofRecord:
    """Running stats for one miner's storage proof history."""
    uid: str
    total_challenges: int = 0
    passed_challenges: int = 0
    last_challenged_at: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_challenges == 0:
            return 1.0  # no data yet — assume honest
        return self.passed_challenges / self.total_challenges

    @property
    def should_slash(self) -> bool:
        return self.total_challenges >= 5 and self.success_rate < SLASH_THRESHOLD


class ChallengeDispatcher:
    """
    Issues storage proof challenges to miners and tracks their results.
    The validator calls `run_challenge_round()` on a timer.
    """

    def __init__(self) -> None:
        self._records: dict[str, MinerProofRecord] = {}
        self._known_cids: list[str] = []   # CIDs the validator has ground truth for

    def register_cid(self, cid: str) -> None:
        """Register a CID that the validator can use for challenges."""
        if cid not in self._known_cids:
            self._known_cids.append(cid)

    def get_record(self, uid: str) -> MinerProofRecord:
        if uid not in self._records:
            self._records[uid] = MinerProofRecord(uid=uid)
        return self._records[uid]

    def all_success_rates(self) -> dict[str, float]:
        return {uid: r.success_rate for uid, r in self._records.items()}

    def slashable_miners(self) -> list[str]:
        return [uid for uid, r in self._records.items() if r.should_slash]

    def build_challenge(self, cid: str) -> "engram_core.Challenge | None":
        if not _RUST_AVAILABLE:
            return None
        return engram_core.generate_challenge(cid, CHALLENGE_TIMEOUT_SECS)

    def verify_response(
        self,
        challenge: "engram_core.Challenge",
        response_embedding_hash: str,
        response_proof: str,
        expected_embedding: list[float],
    ) -> bool:
        if not _RUST_AVAILABLE:
            return False

        # Reconstruct ProofResponse from miner's fields
        response = engram_core.ProofResponse.__new__(engram_core.ProofResponse)
        # We verify via the Rust verify_response function
        # Build a temporary ProofResponse by going through generate_response on our side
        # and compare — or we reconstruct and call verify_response directly.
        # Since ProofResponse is a Rust struct, we use generate_response to create one
        # from the challenge, then compare fields.
        expected_response = engram_core.generate_response(challenge, expected_embedding)
        return (
            expected_response.embedding_hash == response_embedding_hash
            and expected_response.proof == response_proof
        )

    def record_result(self, uid: str, passed: bool) -> None:
        record = self.get_record(uid)
        record.total_challenges += 1
        record.last_challenged_at = time.time()
        if passed:
            record.passed_challenges += 1
            logger.debug(f"Challenge PASSED | miner={uid} | rate={record.success_rate:.2f}")
        else:
            logger.warning(f"Challenge FAILED | miner={uid} | rate={record.success_rate:.2f}")
            if record.should_slash:
                logger.error(f"SLASH THRESHOLD HIT | miner={uid}")

    def pick_random_cid(self) -> str | None:
        if not self._known_cids:
            return None
        return random.choice(self._known_cids)
