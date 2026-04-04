"use client";
import { DocPage, H1, H2, Lead, P, Code, Note } from "../_components";

export default function ArchitecturePage() {
  return (
    <DocPage
      prev={{ href: "/docs/protocol", label: "Protocol Reference" }}
      toc={[
        { id: "overview", label: "Overview" },
        { id: "components", label: "Components" },
        { id: "flow", label: "Data flows" },
        { id: "storage", label: "Storage layer" },
      ]}
    >
      <H1>Architecture</H1>
      <Lead>System design, component overview, and data flows for the Engram subnet.</Lead>

      <H2 id="overview">Overview</H2>
      <Code lang="bash" title="System diagram">{`┌──────────────────────────────────────────────────────────────┐
│                       Bittensor Chain                        │
│               (metagraph · weight setting · TAO)             │
└─────────────────────┬──────────────────────┬─────────────────┘
                      │                      │
              ┌───────▼──────┐    ┌──────────▼──────┐
              │  Validator   │    │      Miner       │
              │              │    │                  │
              │ • challenge  │───▶│ • FAISS index    │
              │ • score      │    │ • embedder       │
              │ • set weights│◀───│ • proof service  │
              └──────────────┘    └──────────┬───────┘
                                             │
                                   ┌─────────▼────────┐
                                   │   engram-core     │
                                   │   (Rust / PyO3)   │
                                   │ • CID generation  │
                                   │ • HMAC proofs     │
                                   └──────────────────┘`}</Code>

      <H2 id="components">Components</H2>

      <div className="space-y-3 my-5">
        {[
          {
            name: "Miner (neurons/miner.py)",
            desc: "An aiohttp HTTP server that exposes /ingest and /query endpoints. Embeds text using OpenAI or sentence-transformers, stores vectors in a FAISS IVF-flat index, and responds to validator challenges with HMAC proofs.",
          },
          {
            name: "Validator (neurons/validator.py)",
            desc: "Issues IngestSynapse and QuerySynapse calls to all registered miners, measures recall accuracy and latency, then sets on-chain weights proportional to composite scores every 600 seconds.",
          },
          {
            name: "engram-core (Rust/PyO3)",
            desc: "A Rust extension module compiled with PyO3. Handles CID generation (SHA-256 over float32 bytes) and HMAC-SHA256 storage proof generation/verification.",
          },
          {
            name: "SDK (engram/sdk/)",
            desc: "EngramClient — a zero-dependency Python HTTP client. Also provides LangChain VectorStore and LlamaIndex BasePydanticVectorStore adapters.",
          },
          {
            name: "FastAPI backend (engram-web/api/)",
            desc: "A thin FastAPI bridge between the Next.js frontend and the live subnet. Caches metagraph data for 30 seconds. Deployed at api.theengram.space.",
          },
          {
            name: "Frontend (engram-web/)",
            desc: "Next.js app with a live subnet dashboard, query playground, miner leaderboard, and this docs site. Deployed on Vercel at theengram.space.",
          },
        ].map(({ name, desc }) => (
          <div key={name} className="p-4 rounded-xl border border-[#1e1525] bg-[#0a0810]">
            <div className="text-[14px] font-semibold text-white mb-1.5 font-mono">{name}</div>
            <div className="text-[13px] text-[#6b5a7e] leading-relaxed">{desc}</div>
          </div>
        ))}
      </div>

      <H2 id="flow">Data flows</H2>

      <P><strong className="text-white">Ingest flow:</strong></P>
      <Code lang="bash">{`Client SDK
  → POST /ingest {text, metadata}
  → Miner embeds text (OpenAI / sentence-transformers)
  → engram-core derives CID from embedding
  → FAISS index stores vector + CID
  → Response: {cid: "v1::a3f2b1..."}`}</Code>

      <P><strong className="text-white">Query flow:</strong></P>
      <Code lang="bash">{`Client SDK
  → POST /query {query_text, top_k}
  → Miner embeds query text
  → FAISS ANN search → top-K nearest neighbors
  → Response: [{cid, score, metadata}, ...]`}</Code>

      <P><strong className="text-white">Validation flow:</strong></P>
      <Code lang="bash">{`Validator
  → Pick random CID from ground truth corpus
  → Send IngestSynapse to miner
  → Verify returned vector matches ground truth (cosine sim > 0.99)
  → Record latency and proof success
  → Repeat for all registered miners
  → Compute composite scores → set on-chain weights`}</Code>

      <H2 id="storage">Storage layer</H2>
      <P>
        Miners use FAISS IVF-flat for in-memory vector storage with persistence to disk. The index is saved to <code className="text-[#e040fb] bg-[#1a0d22] px-1.5 py-0.5 rounded text-[12px] font-mono">FAISS_INDEX_PATH</code> after each ingest session and loaded on startup.
      </P>

      <Note>
        The Rust <code className="text-[#e040fb] bg-[#1a0d22] px-1.5 py-0.5 rounded text-[12px] font-mono">engram-core</code> module is optional — the Python fallback is used automatically if the Rust build is unavailable. Build it with <code className="text-[#e040fb] bg-[#1a0d22] px-1.5 py-0.5 rounded text-[12px] font-mono">pip install maturin && cd engram-core && maturin develop --release</code> for production performance.
      </Note>
    </DocPage>
  );
}
