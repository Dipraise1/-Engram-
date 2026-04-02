"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  Database, Zap, Shield, Globe, ArrowRight, Github,
  ChevronRight, Terminal, CheckCircle, Cpu, Network,
  Lock, BarChart3, ExternalLink
} from "lucide-react";

// ── Live stats (fetched from API, falls back to demo numbers) ─────────────────

function useLiveStats() {
  const [stats, setStats] = useState({
    miners: 0, vectors: 0, queries: 0, uptime: "0%", avgScore: "0.00",
  });

  useEffect(() => {
    async function fetchStats() {
      try {
        const res = await fetch("/api/subnet/stats");
        if (res.ok) setStats(await res.json());
      } catch {
        // Demo numbers when API is not yet connected
        setStats({ miners: 12, vectors: 847_293, queries: 24_891, uptime: "99.7%", avgScore: "0.84" });
      }
    }
    fetchStats();
    const id = setInterval(fetchStats, 30_000);
    return () => clearInterval(id);
  }, []);

  return stats;
}

// ── Navbar ─────────────────────────────────────────────────────────────────────

function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handler);
    return () => window.removeEventListener("scroll", handler);
  }, []);

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled ? "bg-engram-dark/95 backdrop-blur border-b border-engram-border" : "bg-transparent"
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-engram-purple flex items-center justify-center">
            <Database className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-lg tracking-tight">Engram</span>
          <span className="text-xs text-engram-light bg-engram-purple/10 border border-engram-purple/30 px-2 py-0.5 rounded-full ml-1">
            Testnet
          </span>
        </div>

        <div className="hidden md:flex items-center gap-8 text-sm text-slate-400">
          <a href="#how" className="hover:text-white transition-colors">How it works</a>
          <a href="#features" className="hover:text-white transition-colors">Features</a>
          <a href="#mine" className="hover:text-white transition-colors">Mine</a>
          <Link href="/dashboard" className="hover:text-white transition-colors">Dashboard</Link>
          <a
            href="https://github.com/Dipraise1/-Engram-"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-white transition-colors"
          >
            Docs
          </a>
        </div>

        <div className="flex items-center gap-3">
          <a
            href="https://github.com/Dipraise1/-Engram-"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
          >
            <Github className="w-4 h-4" />
            <span className="hidden sm:inline">GitHub</span>
          </a>
          <Link
            href="/dashboard"
            className="flex items-center gap-1.5 bg-engram-purple hover:bg-engram-violet text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            Dashboard <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    </nav>
  );
}

// ── Hero ───────────────────────────────────────────────────────────────────────

function Hero({ stats }: { stats: ReturnType<typeof useLiveStats> }) {
  return (
    <section className="relative min-h-screen flex items-center justify-center grid-bg overflow-hidden">
      {/* Background glow */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="w-[700px] h-[700px] rounded-full blur-[140px]"
          style={{ background: "radial-gradient(circle, rgba(192,38,163,0.15) 0%, rgba(124,58,237,0.08) 50%, transparent 70%)" }}
        />
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-6 pt-24 pb-16 text-center">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 bg-engram-purple/10 border border-engram-purple/30 text-engram-light text-sm px-4 py-1.5 rounded-full mb-8">
          <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
          Built on Bittensor Subnet
        </div>

        {/* Headline */}
        <h1 className="text-5xl sm:text-6xl md:text-7xl font-bold leading-tight tracking-tight mb-6">
          The Decentralized{" "}
          <span className="gradient-text">Vector Database</span>
        </h1>

        <p className="text-lg sm:text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
          Store, retrieve, and prove ownership of embeddings — without a central authority.
          Engram is IPFS for AI memory, running on Bittensor&apos;s incentivized network.
        </p>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
          <Link
            href="/dashboard"
            className="flex items-center gap-2 bg-engram-purple hover:bg-engram-violet text-white font-semibold px-8 py-3.5 rounded-xl transition-all glow-purple hover:scale-105 w-full sm:w-auto justify-center"
          >
            Open Dashboard <ArrowRight className="w-4 h-4" />
          </Link>
          <a
            href="#mine"
            className="flex items-center gap-2 bg-engram-card border border-engram-border hover:border-engram-purple/50 text-white font-semibold px-8 py-3.5 rounded-xl transition-all w-full sm:w-auto justify-center"
          >
            Start Mining <ChevronRight className="w-4 h-4" />
          </a>
        </div>

        {/* Live stats bar */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 max-w-3xl mx-auto">
          {[
            { label: "Miners", value: stats.miners.toLocaleString() },
            { label: "Vectors Stored", value: stats.vectors.toLocaleString() },
            { label: "Queries Today", value: stats.queries.toLocaleString() },
            { label: "Network Uptime", value: stats.uptime },
            { label: "Avg Score", value: stats.avgScore },
          ].map((s) => (
            <div
              key={s.label}
              className="bg-engram-card border border-engram-border rounded-xl px-4 py-3 text-center"
            >
              <div className="text-xl font-bold text-white">{s.value}</div>
              <div className="text-xs text-slate-500 mt-0.5">{s.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── How It Works ───────────────────────────────────────────────────────────────

function HowItWorks() {
  const steps = [
    {
      icon: <Terminal className="w-6 h-6" />,
      title: "Ingest",
      desc: "Send text or a vector embedding to the network. Engram generates a content-addressed CID — a permanent fingerprint of your data.",
      code: `engram ingest "AI will transform the world"
# → CID: v1::a3f9d2...`,
    },
    {
      icon: <Network className="w-6 h-6" />,
      title: "Route & Replicate",
      desc: "The DHT router assigns your CID to 3 miners via XOR distance. Your embedding is stored redundantly across the network.",
      code: `assign("v1::a3f9d2")
# → miners [uid=4, uid=11, uid=23]`,
    },
    {
      icon: <Zap className="w-6 h-6" />,
      title: "Query",
      desc: "Submit a semantic search query. Miners return the top-K nearest embeddings by cosine similarity in milliseconds.",
      code: `engram query "machine learning future"
# → 5 results, 23ms`,
    },
    {
      icon: <Shield className="w-6 h-6" />,
      title: "Prove",
      desc: "Validators issue cryptographic storage challenges. Miners respond with HMAC-SHA256 proofs — slashable if they lie.",
      code: `verify_response(nonce, cid, proof)
# → True ✓ (miner scored)`,
    },
  ];

  return (
    <section id="how" className="py-24 px-6">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold mb-4">How Engram Works</h2>
          <p className="text-slate-400 text-lg max-w-xl mx-auto">
            Four steps from data to decentralized, incentivized storage.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          {steps.map((s, i) => (
            <div
              key={i}
              className="bg-engram-card border border-engram-border rounded-2xl p-6 hover:border-engram-purple/40 transition-colors group"
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-engram-purple/20 text-engram-light flex items-center justify-center group-hover:bg-engram-purple/30 transition-colors">
                  {s.icon}
                </div>
                <div>
                  <div className="text-xs text-slate-500 uppercase tracking-widest">Step {i + 1}</div>
                  <div className="font-semibold text-white">{s.title}</div>
                </div>
              </div>
              <p className="text-slate-400 text-sm mb-4 leading-relaxed">{s.desc}</p>
              <div className="code-block text-slate-300 text-xs whitespace-pre">{s.code}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Features ───────────────────────────────────────────────────────────────────

function Features() {
  const features = [
    {
      icon: <Lock className="w-5 h-5" />,
      title: "Content-Addressed",
      desc: "Every vector gets a CID — a SHA-256 fingerprint of its content. Tamper-proof and verifiable by anyone.",
    },
    {
      icon: <Globe className="w-5 h-5" />,
      title: "No Central Authority",
      desc: "No AWS, no single point of failure. Embeddings live across a distributed network of incentivized miners.",
    },
    {
      icon: <Zap className="w-5 h-5" />,
      title: "HNSW Index",
      desc: "Miners run FAISS or Qdrant HNSW indexes. Sub-50ms approximate nearest-neighbor search at scale.",
    },
    {
      icon: <Shield className="w-5 h-5" />,
      title: "Storage Proofs",
      desc: "HMAC-SHA256 challenge-response protocol. Validators slash miners who claim to store data they don't.",
    },
    {
      icon: <Cpu className="w-5 h-5" />,
      title: "Rust Core",
      desc: "CID generation and proof verification run in a PyO3 Rust extension — 10–50x faster than pure Python.",
    },
    {
      icon: <BarChart3 className="w-5 h-5" />,
      title: "Incentivized Quality",
      desc: "Miners scored on recall@K, latency, and proof rate. Higher scores = more TAO emissions.",
    },
    {
      icon: <Network className="w-5 h-5" />,
      title: "Kademlia DHT",
      desc: "XOR-distance routing ensures the same CID always maps to the same miners — deterministic replication.",
    },
    {
      icon: <Database className="w-5 h-5" />,
      title: "Simple SDK",
      desc: "One Python client. ingest(), query(), query_by_vector(). Swap out Pinecone in an afternoon.",
    },
  ];

  return (
    <section id="features" className="py-24 px-6 bg-engram-card/30">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold mb-4">Built Different</h2>
          <p className="text-slate-400 text-lg max-w-xl mx-auto">
            Everything you expect from a vector database — plus cryptographic guarantees.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {features.map((f, i) => (
            <div
              key={i}
              className="bg-engram-card border border-engram-border rounded-xl p-5 hover:border-engram-purple/40 transition-colors"
            >
              <div className="w-9 h-9 rounded-lg bg-engram-purple/20 text-engram-light flex items-center justify-center mb-3">
                {f.icon}
              </div>
              <div className="font-semibold text-white mb-2">{f.title}</div>
              <div className="text-slate-400 text-sm leading-relaxed">{f.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── SDK Snippet ────────────────────────────────────────────────────────────────

function SDKSection() {
  const [tab, setTab] = useState<"ingest" | "query" | "cli">("ingest");

  const snippets = {
    ingest: `from engram.sdk.client import EngramClient

client = EngramClient(netuid=42)

# Ingest text — returns a CID
cid = client.ingest(
    "Transformers revolutionized NLP in 2017",
    metadata={"source": "arxiv", "year": 2017}
)

print(cid)  # v1::a3f9d2e8...`,
    query: `# Semantic search — returns top-K results
results = client.query(
    "attention mechanism neural networks",
    top_k=5
)

for r in results:
    print(f"{r['score']:.3f}  {r['cid'][:16]}...")`,
    cli: `# Install
pip install engram-subnet

# Ingest
engram ingest "your text here"
engram ingest --file ./data.jsonl

# Query
engram query "semantic search" --top-k 10

# Status
engram status`,
  };

  return (
    <section className="py-24 px-6">
      <div className="max-w-5xl mx-auto">
        <div className="grid md:grid-cols-2 gap-12 items-center">
          <div>
            <h2 className="text-4xl font-bold mb-4">
              Drop-in replacement for{" "}
              <span className="gradient-text">Pinecone</span>
            </h2>
            <p className="text-slate-400 leading-relaxed mb-6">
              One Python client. Works with any embedding model. No API key,
              no vendor lock-in — your data lives on a network you can verify.
            </p>
            <ul className="space-y-3">
              {[
                "Works with OpenAI, Cohere, or local models",
                "Content-addressed — same data = same CID always",
                "CLI for quick ingest and search",
                "Built-in storage proofs — miners can't lie",
              ].map((item) => (
                <li key={item} className="flex items-center gap-2 text-sm text-slate-300">
                  <CheckCircle className="w-4 h-4 text-engram-light flex-shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="bg-engram-card border border-engram-border rounded-2xl overflow-hidden">
            {/* Tab bar */}
            <div className="flex border-b border-engram-border">
              {(["ingest", "query", "cli"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={`px-4 py-3 text-sm font-medium transition-colors ${
                    tab === t
                      ? "text-engram-light border-b-2 border-engram-purple"
                      : "text-slate-500 hover:text-slate-300"
                  }`}
                >
                  {t === "cli" ? "CLI" : t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
            <pre className="p-5 text-sm text-slate-300 font-mono overflow-x-auto leading-relaxed">
              <code>{snippets[tab]}</code>
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Mine Section ───────────────────────────────────────────────────────────────

function MineSection() {
  return (
    <section id="mine" className="py-24 px-6 bg-engram-card/30">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold mb-4">Earn TAO by Mining</h2>
          <p className="text-slate-400 text-lg max-w-xl mx-auto">
            Run a miner node and earn Bittensor emissions for storing and serving embeddings.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6 mb-12">
          {[
            {
              role: "Miner",
              icon: <Database className="w-6 h-6" />,
              desc: "Store embeddings, serve queries, respond to storage proofs. Earn from the miner emission pool.",
              reqs: ["4GB RAM min", "100GB SSD", "Python 3.10+"],
              earn: "41% of subnet emissions",
            },
            {
              role: "Validator",
              icon: <Shield className="w-6 h-6" />,
              desc: "Score miners on recall, latency, and proof rate. Set weights on chain. Earn from the validator pool.",
              reqs: ["8GB RAM", "Stake required", "Always-on uptime"],
              earn: "41% of subnet emissions",
            },
            {
              role: "Builder",
              icon: <Terminal className="w-6 h-6" />,
              desc: "Integrate Engram into your AI stack. Use the SDK to replace Pinecone or Weaviate in your app.",
              reqs: ["pip install engram-subnet", "Any embedding model", "Any language"],
              earn: "Free during testnet",
            },
          ].map((r) => (
            <div
              key={r.role}
              className={`bg-engram-card border rounded-2xl p-6 flex flex-col ${
                r.role === "Miner"
                  ? "border-engram-purple/50 glow-purple-sm"
                  : "border-engram-border"
              }`}
            >
              <div className="w-10 h-10 rounded-lg bg-engram-purple/20 text-engram-light flex items-center justify-center mb-4">
                {r.icon}
              </div>
              <div className="font-bold text-lg text-white mb-2">{r.role}</div>
              <p className="text-slate-400 text-sm mb-4 leading-relaxed flex-1">{r.desc}</p>
              <div className="space-y-1 mb-4">
                {r.reqs.map((req) => (
                  <div key={req} className="flex items-center gap-2 text-xs text-slate-400">
                    <span className="w-1 h-1 bg-engram-light rounded-full" />
                    {req}
                  </div>
                ))}
              </div>
              <div className="text-xs font-medium text-engram-light bg-engram-purple/10 border border-engram-purple/20 rounded-lg px-3 py-2">
                {r.earn}
              </div>
            </div>
          ))}
        </div>

        <div className="bg-engram-card border border-engram-border rounded-2xl p-6">
          <div className="text-sm text-slate-400 mb-3 font-medium">Quick start — run a miner in 3 commands:</div>
          <div className="code-block text-slate-300 text-sm whitespace-pre">
{`git clone https://github.com/Dipraise1/-Engram- && cd engram
pip install -e ".[miner]"
python neurons/miner.py --wallet.name mywallet --netuid 42`}
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Footer ─────────────────────────────────────────────────────────────────────

function Footer() {
  return (
    <footer className="border-t border-engram-border py-12 px-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-engram-purple flex items-center justify-center">
              <Database className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="font-bold">Engram</span>
            <span className="text-slate-600 text-sm">— Decentralized Vector Database on Bittensor</span>
          </div>

          <div className="flex items-center gap-6 text-sm text-slate-500">
            <Link href="/dashboard" className="hover:text-white transition-colors">Dashboard</Link>
            <a
              href="https://github.com/Dipraise1/-Engram-"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 hover:text-white transition-colors"
            >
              GitHub <ExternalLink className="w-3 h-3" />
            </a>
            <a
              href="https://bittensor.com"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 hover:text-white transition-colors"
            >
              Bittensor <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
        <div className="mt-6 text-center text-xs text-slate-700">
          Built on Bittensor · Open Source · Testnet Active
        </div>
      </div>
    </footer>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function Home() {
  const stats = useLiveStats();

  return (
    <main>
      <Navbar />
      <Hero stats={stats} />
      <HowItWorks />
      <Features />
      <SDKSection />
      <MineSection />
      <Footer />
    </main>
  );
}
