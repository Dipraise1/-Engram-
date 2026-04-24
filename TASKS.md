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

### 🔲 Timing / Access-Pattern Side-Channel

**Priority:** Medium  
**ATLAS:** AML.T0036 — Data from information repositories (side-channel variant)  
**Effort:** 1 day

**Problem:**  
Even with fully encrypted content, response timing and payload sizes leak information:
- Fast response → cache hit → content was recently accessed
- Large response → large stored object
- Query pattern → reveals what topics a user searches

**Solution:**  
1. **Uniform response latency** — pad all responses to a fixed minimum latency bucket
   (e.g. round up to nearest 100ms) before returning.
2. **Payload padding** — pad response JSON to fixed size buckets (1KB, 4KB, 16KB).
3. **Rate-limit logging** — strip per-query timing from logs for private namespaces.

**Files to touch:**
- `neurons/miner.py` — add `_pad_response_timing(min_ms)` around handler calls
- `engram/miner/query.py` — pad result payload size before returning

---

### 🔲 Miner Memory Leak / Freeze Prevention

**Priority:** Medium  
**Not an ATLAS item — operational resilience**  
**Effort:** Half day

**Problem:**  
Miner froze on 2026-04-23 after memory crept to 1.7G (max 2G). Socket accept queue
filled (Recv-Q 129/128). Root cause: FAISS index growth + Python memory fragmentation
over multi-day uptime.

**Solution:**  
1. Add a scheduled miner restart (weekly `systemctl restart engram-miner` via cron).
2. Add memory headroom monitoring — alert or auto-restart at 85% of `MemoryMax`.
3. Investigate FAISS index compaction to reduce RSS.

**Files to touch:**
- `/etc/systemd/system/engram-miner.service` — add `MemoryMax` + `Restart=on-failure`
  with `RestartSec=10` and a weekly `OnCalendar` timer unit
- `neurons/miner.py` — add `/metrics` endpoint exposing RSS + index size

---

### 🔲 REQUIRE_HOTKEY_SIG Enforcement

**Priority:** Low  
**ATLAS:** AML.T0043 — unsigned requests bypass identity checks  
**Effort:** Half day

**Problem:**  
`REQUIRE_HOTKEY_SIG` defaults to `false` — unsigned SDK requests are allowed with only
a deprecation warning. Malicious actors can ingest without any on-chain identity.

**Solution:**  
Flip default to `true` on mainnet, keep `false` for local dev.
Add `ENGRAM_ENV=mainnet|dev` config that sets the default automatically.

**Files to touch:**
- `engram/miner/auth.py` — read `ENGRAM_ENV` to set `REQUIRE_SIG` default
- `engram/config.py` — add `ENGRAM_ENV` constant
- `/opt/engram/.env.miner` — set `ENGRAM_ENV=mainnet` on VPS

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

### 🔲 Weekly Miner Auto-Restart Cron

**Priority:** Medium  
**Effort:** 10 minutes

Prevents the socket-queue freeze seen on 2026-04-23.

```bash
# On VPS: /etc/cron.d/engram-miner-restart
0 4 * * 0 root systemctl restart engram-miner
```
