import { DocPage, H1, H2, Lead, P, Code, Table, Note, Ic } from "../_components";

export default function ProtocolPage() {
  return (
    <DocPage
      prev={{ href: "/docs/validator", label: "Run a Validator" }}
      next={{ href: "/docs/architecture", label: "Architecture" }}
      toc={[
        { id: "synapses", label: "Synapses" },
        { id: "cid", label: "CID spec" },
        { id: "scoring", label: "Scoring formulas" },
        { id: "constants", label: "Constants" },
      ]}
    >
      <H1>Protocol Reference</H1>
      <Lead>The Engram wire protocol — synapse types, CID specification, scoring formulas, and network constants.</Lead>

      <H2 id="synapses">Synapse types</H2>
      <P>Engram uses two Bittensor synapse types for neuron communication:</P>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 my-5">
        {[
          {
            name: "IngestSynapse",
            dir: "Validator → Miner",
            desc: "Carry text and metadata to the miner for embedding and storage.",
            fields: [
              ["text", "str", "Text to embed (max 8192 chars)"],
              ["metadata", "dict", "Key-value metadata (max 4 KB)"],
              ["→ cid", "str", "Assigned content identifier"],
              ["→ error", "str | None", "Error message if failed"],
            ],
          },
          {
            name: "QuerySynapse",
            dir: "Validator → Miner",
            desc: "Carry a query text and top_k. Miner returns ranked results.",
            fields: [
              ["query_text", "str", "Natural language query"],
              ["top_k", "int", "Max results (1–100)"],
              ["→ results", "list[dict]", "Ranked {cid, score, metadata}"],
              ["→ error", "str | None", "Error message if failed"],
            ],
          },
        ].map(({ name, dir, desc, fields }) => (
          <div key={name} className="border border-[#1e1525] rounded-xl overflow-hidden">
            <div className="px-4 py-3 bg-[#0e0b12] border-b border-[#1e1525] flex items-center justify-between">
              <code className="text-[13px] font-mono text-[#e040fb]">{name}</code>
              <span className="text-[10px] font-mono text-[#6b5a7e]">{dir}</span>
            </div>
            <div className="px-4 py-3">
              <p className="text-[12px] text-[#6b5a7e] mb-3">{desc}</p>
              <div className="space-y-1.5">
                {fields.map(([name, type, desc]) => (
                  <div key={name} className="flex items-start gap-2">
                    <code className="text-[11px] font-mono text-[#e040fb] w-20 flex-shrink-0">{name}</code>
                    <code className="text-[11px] font-mono text-[#7c3aed] w-16 flex-shrink-0">{type}</code>
                    <span className="text-[11px] text-[#6b5a7e]">{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>

      <H2 id="cid">CID specification</H2>
      <P>
        CIDs are deterministically derived from the embedding vector using SHA-256:
      </P>
      <Code lang="python">{`# CID derivation (simplified)
import hashlib

def derive_cid(embedding: list[float]) -> str:
    raw = b"".join(struct.pack("<f", x) for x in embedding)
    digest = hashlib.sha256(raw).hexdigest()
    return f"v1::{digest[:32]}"

# Example
cid = "v1::a3f2b1c4d5e6f7a8b9c0d1e2f3a4b5c6"`}</Code>

      <Note>
        The same text always produces the same CID regardless of which miner stores it. This is the core content-addressing guarantee.
      </Note>

      <H2 id="scoring">Scoring formulas</H2>
      <Code lang="python">{`# Composite score (computed by validator, per miner)
composite_score = (
    0.50 * recall_at_10          # fraction of challenge vectors correctly returned
  + 0.30 * latency_score         # normalized inverse latency
  + 0.20 * proof_success_rate    # HMAC challenges passed / total
)

# Latency score — 1.0 at ≤100ms, 0.0 at ≥500ms
latency_score = max(0.0, 1.0 - (latency_ms - 100) / 400)

# Miners below 50% proof success rate → weight = 0
if proof_success_rate < 0.50:
    composite_score = 0.0

# Weights are proportional to normalized scores
weights = softmax(composite_scores)`}</Code>

      <H2 id="constants">Constants</H2>
      <Table
        headers={["Constant", "Value", "Description"]}
        rows={[
          ["NETUID", "42", "Subnet UID on testnet"],
          ["EMBEDDING_DIM", "1536", "Vector dimension (text-embedding-3-small)"],
          ["MAX_TEXT_LENGTH", "8192", "Max characters per ingest"],
          ["REPLICATION_FACTOR", "3", "Target copies across miners"],
          ["SCORING_INTERVAL", "120s", "Time between scoring rounds"],
          ["WEIGHT_INTERVAL", "600s", "Time between on-chain weight updates"],
          ["CHALLENGE_SAMPLE_SIZE", "10", "CIDs challenged per miner per round"],
          ["MIN_PROOF_RATE", "0.50", "Proof success rate floor"],
          ["MIN_STAKE_TAO", "0.001 τ", "Minimum stake to pass stake check"],
          ["RATE_LIMIT_RPM", "60", "Max requests per minute per hotkey"],
          ["CID_VERSION", '"v1"', "Current CID scheme version"],
        ]}
      />
    </DocPage>
  );
}
