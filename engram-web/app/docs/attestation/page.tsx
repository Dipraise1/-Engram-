import type { Metadata } from "next";
import { DocPage, H1, H2, H3, Lead, P, Code, Note, Table, Ic } from "../ui";

export const metadata: Metadata = {
  title: "Namespace Attestation",
  description:
    "Link a namespace to a Bittensor hotkey. On-chain TAO stake becomes a publicly verifiable trust signal — no central moderation required.",
  alternates: { canonical: "https://theengram.space/docs/attestation" },
  openGraph: {
    title: "Namespace Attestation — Engram",
    description:
      "On-chain trust tiers for content accountability. Stake TAO, prove ownership, earn trust.",
    url: "https://theengram.space/docs/attestation",
  },
};

export default function AttestationPage() {
  return (
    <DocPage
      prev={{ href: "/docs/namespaces", label: "Private Namespaces" }}
      next={{ href: "/docs/sdk-langchain", label: "LangChain" }}
      toc={[
        { id: "overview", label: "Overview" },
        { id: "trust-tiers", label: "Trust tiers" },
        { id: "how-it-works", label: "How it works" },
        { id: "attest", label: "Attesting a namespace" },
        { id: "query-trust", label: "Filtering by trust" },
        { id: "api", label: "API reference" },
        { id: "threat-model", label: "Threat model" },
      ]}
    >
      <H1>Namespace Attestation</H1>
      <Lead>
        Link a namespace to a Bittensor hotkey. The hotkey's on-chain TAO stake becomes a
        publicly verifiable trust signal —{" "}
        <strong className="text-white">no central moderation required</strong>.
      </Lead>

      <H2 id="overview">Overview</H2>
      <P>
        Engram cannot verify whether stored content is <em>true</em> — that's an unsolvable
        problem for any decentralized system. What it <em>can</em> do is make accountability
        legible and on-chain-verifiable.
      </P>
      <P>
        Namespace attestation works like this: a namespace owner signs a challenge with their
        Bittensor hotkey. Their TAO stake on that hotkey determines a trust tier. Every query
        result carries the trust tier of its namespace. Agents decide which tiers they're
        willing to trust — Engram enforces nothing at the content level.
      </P>
      <Note type="tip">
        Think of it like domain reputation on the web. TCP/IP doesn't verify content
        truthfulness — reputation layers built on top of it do. Attestation is Engram's
        reputation layer.
      </Note>

      <H2 id="trust-tiers">Trust tiers</H2>
      <Table
        headers={["Tier", "Stake required", "What it means"]}
        rows={[
          ["sovereign", "≥ 1000 TAO", "Protocol-level trusted entity — significant economic stake at risk"],
          ["verified", "≥ 100 TAO", "Meaningful accountability — costly to abandon and re-create"],
          ["community", "≥ 1 TAO", "Basic skin in the game — cheap but not free"],
          ["anonymous", "< 1 TAO or unattested", "No guarantees — treat as untrusted"],
        ]}
      />
      <P>
        Stake is refreshed from the metagraph every 10 minutes. If an owner's stake drops
        below their tier threshold, the tier degrades automatically — no manual intervention
        required.
      </P>

      <H2 id="how-it-works">How it works</H2>
      <ol className="list-decimal list-inside space-y-2 text-[#c4b5d4] text-[14px] leading-relaxed mb-6">
        <li>The namespace owner signs a canonical message with their Bittensor sr25519 hotkey</li>
        <li>The miner verifies the signature and reads the owner's TAO stake from the metagraph</li>
        <li>A trust tier is assigned based on stake and persisted alongside the namespace</li>
        <li>Every query result from that namespace carries the <Ic>trust_tier</Ic> field</li>
        <li>Agents filter results by the minimum trust tier they're willing to accept</li>
      </ol>

      <H2 id="attest">Attesting a namespace</H2>
      <H3 id="using-sdk">Using the Python SDK</H3>
      <Code lang="python">{`from engram.miner.attestation import build_attestation_payload
import bittensor as bt
import requests

# Load your wallet
wallet = bt.wallet(name="my_wallet")

# Build a signed attestation payload
payload = build_attestation_payload(wallet.hotkey, "my_agent_memory")

# Submit to your miner
resp = requests.post("http://your-miner:8091/AttestNamespace", json=payload)
print(resp.json())
# {
#   "ok": true,
#   "namespace": "my_agent_memory",
#   "trust_tier": "verified",
#   "stake_tao": 250.0
# }`}</Code>

      <H3 id="using-curl">Using curl</H3>
      <P>
        You need to build the signature yourself. The canonical message to sign is:
      </P>
      <Code lang="text">{`engram-attest:{namespace}:{timestamp_ms}`}</Code>
      <Code lang="bash">{`curl -X POST http://your-miner:8091/AttestNamespace \\
  -H "Content-Type: application/json" \\
  -d '{
    "namespace":    "my_agent_memory",
    "owner_hotkey": "5YourHotkeyAddress...",
    "signature":    "0xsignature_hex...",
    "timestamp_ms": 1712345678123
  }'`}</Code>
      <Note>
        The timestamp must be within ±60 seconds of the miner's clock (replay protection).
        Generate it fresh — don't reuse a previous payload.
      </Note>

      <H3 id="check-tier">Checking a namespace's trust tier</H3>
      <Code lang="bash">{`curl http://your-miner:8091/attestation/my_agent_memory
# {
#   "namespace":    "my_agent_memory",
#   "owner_hotkey": "5YourHotkeyAddress...",
#   "trust_tier":   "verified",
#   "stake_tao":    250.0,
#   "attested_at":  1712345678.0,
#   "attested":     true
# }`}</Code>

      <H2 id="query-trust">Filtering query results by trust</H2>
      <P>
        Every query result now includes a <Ic>trust_tier</Ic> field. Unattested namespaces
        return <Ic>"anonymous"</Ic>.
      </P>
      <Code lang="python">{`results = client.query("attention mechanisms in transformers")

# Only use results from verified or sovereign namespaces
trusted = [r for r in results if r["trust_tier"] in ("verified", "sovereign")]

for r in trusted:
    print(f"{r['score']:.4f}  [{r['trust_tier']}]  {r['cid']}")`}</Code>

      <Code lang="python">{`# Example result structure
{
  "cid":        "v1::a3f2b1c4...",
  "score":      0.9821,
  "metadata":   {"source": "arxiv", "title": "Attention Is All You Need"},
  "trust_tier": "verified"
}`}</Code>

      <Note type="tip">
        For production agents, combine namespace attestation with private namespaces:
        attest your private namespace so other parties can verify you own it, while
        keeping the content encrypted so miners can't read it.
      </Note>

      <H2 id="api">API reference</H2>

      <H3 id="post-attest">POST /AttestNamespace</H3>
      <Table
        headers={["Field", "Type", "Required", "Description"]}
        rows={[
          ["namespace", "string", "Yes", "The namespace to attest"],
          ["owner_hotkey", "string (SS58)", "Yes", "Bittensor hotkey address of the owner"],
          ["signature", "string (hex)", "Yes", "sr25519 signature over canonical message"],
          ["timestamp_ms", "integer", "Yes", "Unix milliseconds — must be within ±60s of server time"],
        ]}
      />

      <H3 id="get-attestation">GET /attestation/{"{namespace}"}</H3>
      <Table
        headers={["Field", "Type", "Description"]}
        rows={[
          ["namespace", "string", "The queried namespace"],
          ["owner_hotkey", "string", "Hotkey that attested (omitted if unattested)"],
          ["trust_tier", "string", "sovereign / verified / community / anonymous"],
          ["stake_tao", "float", "TAO at last refresh (omitted if unattested)"],
          ["attested_at", "float", "Unix timestamp of attestation (omitted if unattested)"],
          ["attested", "boolean", "Whether this namespace has been attested"],
        ]}
      />

      <H2 id="threat-model">Threat model</H2>
      <Table
        headers={["Threat", "Protected?"]}
        rows={[
          ["Attacker injects content into your attested namespace", "✓ Yes — only owner's hotkey can attest; namespace key still required to write"],
          ["Attacker buys high stake, poisons, then unstakes", "Partial — economic cost deters casual attacks; stake lock period adds friction"],
          ["Unattested namespace serves bad content", "Expected — tier shows as 'anonymous'; agents should reject or weight accordingly"],
          ["Owner's stake drops after attesting", "✓ Handled — tier auto-degrades when stake falls below threshold on next refresh"],
          ["Replay attack reuses old attestation payload", "✓ Yes — timestamp window ±60s; old payloads rejected"],
          ["Attacker spoofs hotkey without signing", "✓ Yes — sr25519 signature verification required"],
        ]}
      />
      <Note>
        Attestation solves <strong className="text-white">accountability</strong>, not
        content truth. A sovereign-tier namespace proves the owner has significant economic
        stake at risk — it does not prove their content is accurate. Use it as a trust
        signal, not a content guarantee.
      </Note>
    </DocPage>
  );
}
