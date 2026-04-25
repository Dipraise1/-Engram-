# Engram — Task Backlog

## Security Hardening (ATLAS Threat Model)

### ✅ Done

| Task | Closes | Shipped |
|---|---|---|
| Gaussian DP noise on private namespace embeddings | AML.T0024 vector inversion | `f80a804` |
| `encrypt_raw()` — encrypt media bytes before Arweave upload | AML.T0035 pre-vectorization plaintext | `f80a804` |
| Replace `namespace_key` wire exposure with sr25519 signed challenge | AML.T0043 key-in-transit | `58b312f` |
| Flag-stripping downgrade closed via signature coverage | AML.T0043 downgrade | `58b312f` |
| TLS on miner — `https://api.theengram.space` routes to port 8091 | passive wire sniffing | `58b312f` |
| Arweave storage across full stack (SDK + miner, not just web) | AML.T0035 | `f80a804` |
| Fix event-loop blocking — embed/metagraph calls moved to thread executors | operational resilience | `c5dbbeb` |
| Switch vector store to Qdrant — crash-safe WAL, zero data loss on restart | operational resilience | `c5dbbeb` |
| Timing + payload padding for private namespace queries | AML.T0036 side-channel | current |
| REQUIRE_HOTKEY_SIG defaults to true on mainnet via ENGRAM_ENV | AML.T0043 unsigned bypass | current |
| Weekly miner auto-restart cron (`/etc/cron.d/engram-miner-restart`) | operational resilience | current |

---

### 🔲 Threshold Decryption (K-of-N miners)

**Priority:** High  
**ATLAS:** AML.T0010 — Compromised miner acting as honest node  
**Effort:** 1–2 weeks

**Problem:**  
A miner that passes all spec checks and stake attestation can still log decrypted content
at retrieval time. No software-only fix fully closes this without hardware TEE.

**Solution:**  
Split the namespace decryption key across N miners using Shamir Secret Sharing.
Any single miner holds only a key share — it cannot decrypt alone.
Retrieval requires K-of-N miners to cooperate via a lightweight MPC round.

**Design sketch:**
```
1. Client generates namespace key K.
2. Split K into N shares using Shamir(k=2, n=3) (or configurable).
3. Distribute one share to each of the top-N miners by stake/trust.
4. At query time, client requests partial decryptions from K miners.
5. Client reconstructs K locally — miners never see the full key.
```

**Files to touch:**
- `engram/sdk/encryption.py` — add `ShamirKeySplit` / `ShamirKeyReconstruct`
- `engram/sdk/client.py` — distribute shares on namespace creation; collect on query
- `engram/protocol.py` — add `KeyShareSynapse` for share distribution
- `engram/miner/` — add key share store + partial-decrypt endpoint
- `neurons/miner.py` — register share endpoint

---

### ✅ Timing / Access-Pattern Side-Channel

Shipped. Private namespace queries now padded to nearest 100ms latency bucket (`_pad_latency`) and nearest 1KB/4KB/16KB/64KB payload bucket (`_pad_payload`) in `neurons/miner.py`. Public queries unaffected (no validator scoring impact).

---

### ✅ Miner Event-Loop Freeze + Memory Loss Prevention

Root cause was two blocking calls on the asyncio event loop (OpenAI embedding + metagraph refresh), not FAISS memory growth. Fixed by moving both to thread executors. Vector store switched from FAISS (in-memory, crash-loses-data) to Qdrant (WAL-backed, crash-safe). Weekly restart cron added as safety net.

---

### ✅ REQUIRE_HOTKEY_SIG Enforcement

Shipped. `ENGRAM_ENV=mainnet` in `.env.miner` causes `REQUIRE_HOTKEY_SIG` to default to `true`. Local dev remains permissive without any env change needed.

---

## Infrastructure

### 🔲 theengram.space SSL Certificate

**Priority:** Medium  
**Effort:** 30 minutes

DNS for `theengram.space` resolves to Vercel (216.198.79.65), not the VPS.
Vercel handles TLS automatically. No action needed unless the domain is migrated.

If the domain is pointed at the VPS in the future:
```bash
certbot --nginx -d theengram.space -d www.theengram.space \
  --non-interactive --agree-tos -m careyisabella22@gmail.com --redirect
```

---

### ✅ Weekly Miner Auto-Restart Cron

Shipped. `/etc/cron.d/engram-miner-restart` restarts the miner every Sunday at 04:00 UTC.
