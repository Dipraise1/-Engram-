import Link from "next/link";
import { ArrowRight, Zap, Shield, Globe, Cpu } from "lucide-react";
import { DocPage, H1, Lead, Code, Note } from "./_components";

const CARDS = [
  {
    icon: Zap,
    title: "Quick Start",
    desc: "Install, ingest your first text, and run a semantic query in under 2 minutes.",
    href: "/docs/quickstart",
    cta: "Get started",
  },
  {
    icon: Cpu,
    title: "Python SDK",
    desc: "EngramClient, LangChain and LlamaIndex integrations, exception handling.",
    href: "/docs/sdk",
    cta: "View SDK",
  },
  {
    icon: Globe,
    title: "Run a Miner",
    desc: "Wallet setup, subnet registration, configuration, and start commands.",
    href: "/docs/miner",
    cta: "Mine TAO",
  },
  {
    icon: Shield,
    title: "Protocol",
    desc: "IngestSynapse, QuerySynapse, CID spec, scoring formulas, and constants.",
    href: "/docs/protocol",
    cta: "Read spec",
  },
];

export default function DocsIndex() {
  return (
    <DocPage next={{ href: "/docs/quickstart", label: "Quick Start" }}>
      <H1>Engram Documentation</H1>
      <Lead>
        Engram is a decentralized vector database on Bittensor — permanent, content-addressed semantic memory for AI applications. No central server, no single point of failure.
      </Lead>

      {/* Feature cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 my-8">
        {CARDS.map(({ icon: Icon, title, desc, href, cta }) => (
          <Link
            key={href}
            href={href}
            className="group flex flex-col gap-3 p-5 rounded-xl border border-[#1e1525] bg-[#0e0b12] hover:border-[#3a2845] hover:bg-[#0e0b14] transition-all"
          >
            <div className="flex items-center justify-between">
              <div className="w-8 h-8 rounded-lg bg-[#1a1022] flex items-center justify-center">
                <Icon className="w-4 h-4 text-[#e040fb]" />
              </div>
              <ArrowRight className="w-4 h-4 text-[#3a2845] group-hover:text-[#6b5a7e] group-hover:translate-x-0.5 transition-all" />
            </div>
            <div>
              <div className="text-[14px] font-semibold text-white mb-1">{title}</div>
              <div className="text-[12px] text-[#6b5a7e] leading-relaxed">{desc}</div>
            </div>
            <div className="text-[12px] text-[#e040fb] font-mono mt-auto">{cta} →</div>
          </Link>
        ))}
      </div>

      {/* What is Engram */}
      <h2 className="font-display font-light text-white mt-10 mb-3 text-2xl">What is Engram?</h2>
      <p className="text-[15px] text-[#c4b5d4] leading-relaxed mb-4">
        Engram applies the IPFS insight to AI memory: every piece of knowledge gets a{" "}
        <code className="text-[#e040fb] bg-[#1a0d22] px-1.5 py-0.5 rounded text-[12px] font-mono">CID</code>{" "}
        derived deterministically from its embedding. The same text always maps to the same CID — regardless of which miner stores it.
      </p>

      <Code lang="python">{`from engram.sdk import EngramClient

client = EngramClient("http://127.0.0.1:8091")

# Store text — returns a permanent CID
cid = client.ingest("The transformer architecture changed everything.")
print(cid)  # v1::a3f2b1c4d5e6f7a8b9c0d1e2f3a4b5c6

# Semantic search — no exact match needed
results = client.query("how does attention work?", top_k=5)
for r in results:
    print(f"{r['score']:.4f}  {r['cid']}")`}</Code>

      <Note type="tip">
        The CLI defaults to a local FAISS store and sentence-transformers embedder — no OpenAI key or running node needed to get started.
      </Note>

      {/* How it works */}
      <h2 className="font-display font-light text-white mt-10 mb-3 text-2xl">How it works</h2>

      <div className="space-y-3 my-5">
        {[
          ["Ingest", "Text is embedded (OpenAI or local), assigned a SHA-256 CID, and stored in the miner's FAISS index."],
          ["Store", "Miners compete to store vectors and earn TAO. Replication across multiple miners ensures durability."],
          ["Prove", "Validators issue HMAC challenge-response proofs to verify miners actually hold the data."],
          ["Query", "Semantic search runs ANN over the FAISS index — return the top-K most similar embeddings by cosine similarity."],
          ["Score", "Validators score miners on recall accuracy, latency, and proof success rate, then set on-chain weights."],
        ].map(([title, desc], i) => (
          <div key={title} className="flex gap-4 p-4 rounded-xl border border-[#1e1525] bg-[#0a0810]">
            <span className="text-[11px] font-mono text-[#e040fb] w-4 flex-shrink-0 mt-0.5">{String(i + 1).padStart(2, "0")}</span>
            <div>
              <span className="text-[14px] font-semibold text-white">{title} — </span>
              <span className="text-[13px] text-[#6b5a7e]">{desc}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Network info */}
      <h2 className="font-display font-light text-white mt-10 mb-3 text-2xl">Network</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {[
          ["Status", "Testnet"],
          ["Subnet UID", "42"],
          ["Proof type", "HMAC-SHA256"],
          ["Vector index", "FAISS IVF-flat"],
          ["Embedding dim", "1536d"],
          ["Scoring interval", "120 seconds"],
        ].map(([k, v]) => (
          <div key={k} className="p-3 rounded-xl border border-[#1e1525] bg-[#0e0b12]">
            <div className="text-[10px] uppercase tracking-widest text-[#3a2845] font-mono mb-1">{k}</div>
            <div className="text-[13px] text-white font-mono">{v}</div>
          </div>
        ))}
      </div>
    </DocPage>
  );
}
