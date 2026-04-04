"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { ArrowRight, Github, ArrowUpRight, Terminal, ChevronRight, ExternalLink } from "lucide-react";

// ── Live stats ──────────────────────────────────────────────────────────────────

function useLiveStats() {
  const [stats, setStats] = useState<{ miners: number; vectors: number; uptime: string; avgScore: string } | null>(null);
  useEffect(() => {
    async function fetch_() {
      try {
        const res = await fetch("/api/subnet/stats");
        if (res.ok) setStats(await res.json());
      } catch { /* no live API yet — show nothing */ }
    }
    fetch_();
    const id = setInterval(fetch_, 30_000);
    return () => clearInterval(id);
  }, []);
  return stats;
}

// ── Syntax coloring helpers ─────────────────────────────────────────────────────

function PyCode({ code }: { code: string }) {
  const lines = code.split("\n");
  return (
    <pre className="text-[12.5px] font-mono leading-[1.85] overflow-x-auto">
      {lines.map((line, i) => {
        if (line.trim().startsWith("#")) {
          return <div key={i} className="text-[#5c6370]">{line}</div>;
        }
        const styled = line
          .replace(/(from|import|def|class|return|for|in|if|not|and|or|True|False|None|async|await|with|as)\b/g, '<kw>$1</kw>')
          .replace(/(".*?"|'.*?')/g, '<str>$1</str>')
          .replace(/(\b\d+\.?\d*\b)/g, '<num>$1</num>')
          .replace(/([a-zA-Z_]\w*)\s*(?=\()/g, '<fn>$1</fn>')
          .replace(/# .*/g, '<cmt>$&</cmt>');

        return (
          <div key={i} dangerouslySetInnerHTML={{ __html:
            styled
              .replace(/<kw>(.*?)<\/kw>/g, '<span style="color:#c678dd">$1</span>')
              .replace(/<str>(.*?)<\/str>/g, '<span style="color:#98c379">$1</span>')
              .replace(/<num>(.*?)<\/num>/g, '<span style="color:#d19a66">$1</span>')
              .replace(/<fn>(.*?)<\/fn>/g, '<span style="color:#61afef">$1</span>')
              .replace(/<cmt>(.*?)<\/cmt>/g, '<span style="color:#5c6370">$1</span>')
          }} />
        );
      })}
    </pre>
  );
}

function CliCode({ code }: { code: string }) {
  const lines = code.split("\n");
  return (
    <pre className="text-[12.5px] font-mono leading-[1.85] overflow-x-auto">
      {lines.map((line, i) => {
        if (line.trim().startsWith("#")) return <div key={i} className="text-[#5c6370]">{line}</div>;
        if (line.trim().startsWith("$") || line.trim().startsWith("→") || line.trim().startsWith("#")) {
          return <div key={i} className="text-[#5c6370]">{line}</div>;
        }
        const parts = line.split(" ");
        if (parts[0] === "engram" || parts[0] === "pip" || parts[0] === "git" || parts[0] === "python") {
          return (
            <div key={i}>
              <span style={{ color: "#61afef" }}>{parts[0]}</span>
              {" "}
              <span style={{ color: "#e06c75" }}>{parts[1] || ""}</span>
              {parts.length > 2 && <span className="text-white/50">{" " + parts.slice(2).join(" ")}</span>}
            </div>
          );
        }
        return <div key={i} className="text-white/50">{line}</div>;
      })}
    </pre>
  );
}

// ── Terminal block wrapper ──────────────────────────────────────────────────────

function TermBlock({ title, children, className = "" }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl overflow-hidden border border-white/[0.07] ${className}`}>
      <div className="flex items-center gap-2 px-4 py-2.5 bg-[#0d0b11] border-b border-white/[0.06]">
        <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
        {title && <span className="ml-2 text-[11px] text-white/25 font-mono tracking-wide">{title}</span>}
      </div>
      <div className="bg-[#0a0810] px-5 py-4 text-white/55">{children}</div>
    </div>
  );
}

// ── Navbar ──────────────────────────────────────────────────────────────────────

function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const h = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", h);
    return () => window.removeEventListener("scroll", h);
  }, []);

  return (
    <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
      scrolled ? "bg-[#080608]/95 backdrop-blur-xl border-b border-white/[0.06]" : ""
    }`}>
      <div className="max-w-6xl mx-auto px-6 h-[64px] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Image src="/logo.png" alt="Engram" width={30} height={30} className="block" />
          <span className="font-semibold text-[15px] tracking-tight text-white font-sans">Engram</span>
          <span className="text-[10px] font-semibold tracking-[0.12em] uppercase px-2 py-0.5 rounded border border-[#e040fb]/20 text-[#e040fb]/60 ml-0.5 font-mono">
            v0.1 · testnet
          </span>
        </div>

        <div className="hidden md:flex items-center gap-8 text-[13px] text-white/35 font-normal">
          <a href="#protocol" className="hover:text-white/70 transition-colors">Protocol</a>
          <a href="#features" className="hover:text-white/70 transition-colors">Features</a>
          <a href="#sdk" className="hover:text-white/70 transition-colors">SDK</a>
          <a href="#mine" className="hover:text-white/70 transition-colors">Mine</a>
          <Link href="/dashboard" className="hover:text-white/70 transition-colors">Dashboard</Link>
          <Link href="/docs" className="hover:text-white/70 transition-colors">Docs</Link>
          <a href="https://github.com/Dipraise1/-Engram-" target="_blank" rel="noopener noreferrer"
            className="hover:text-white/70 transition-colors flex items-center gap-1">
            GitHub <ArrowUpRight className="w-3 h-3" />
          </a>
        </div>

        <div className="flex items-center gap-3">
          <a href="https://github.com/Dipraise1/-Engram-" target="_blank" rel="noopener noreferrer"
            className="text-white/25 hover:text-white/60 transition-colors">
            <Github className="w-[17px] h-[17px]" />
          </a>
          <Link href="/dashboard"
            className="flex items-center gap-1.5 bg-white text-[#080608] text-[12px] font-bold px-4 py-2 rounded-full hover:bg-white/90 transition-colors tracking-tight font-sans">
            Launch App <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </div>
    </nav>
  );
}

// ── S-shaped marquee ────────────────────────────────────────────────────────────

function SMarquee() {
  const label = "MEMORY FOR AI · BITTENSOR SUBNET · CONTENT-ADDRESSED · STORAGE PROOFS · DECENTRALIZED · RUST CORE · ";
  const text = label.repeat(6);

  return (
    <>
      <svg className="absolute inset-0 w-full h-full pointer-events-none select-none md:hidden"
        viewBox="0 0 390 844" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <path id="s-path-mobile" d="M 370 0 C 370 250, 20 250, 20 422 C 20 594, 370 594, 370 844" />
        </defs>
        <text fontSize="9" fontFamily="JetBrains Mono, monospace" fontWeight="600" letterSpacing="2" fill="rgba(255,255,255,0.10)">
          <textPath href="#s-path-mobile" startOffset="0%">
            <animate attributeName="startOffset" values="0%;-50%" dur="22s" repeatCount="indefinite" />
            {text}
          </textPath>
        </text>
      </svg>
      <svg className="absolute inset-0 w-full h-full pointer-events-none select-none hidden md:block"
        viewBox="0 0 1440 900" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <path id="s-path-desktop" d="M 1380 0 C 1380 280, 60 280, 60 450 C 60 620, 1380 620, 1380 900" />
        </defs>
        <text fontSize="11" fontFamily="JetBrains Mono, monospace" fontWeight="600" letterSpacing="3" fill="rgba(255,255,255,0.10)">
          <textPath href="#s-path-desktop" startOffset="0%">
            <animate attributeName="startOffset" values="0%;-50%" dur="28s" repeatCount="indefinite" />
            {text}
          </textPath>
        </text>
      </svg>
    </>
  );
}

// ── Hero ────────────────────────────────────────────────────────────────────────

function Hero() {
  return (
    <section className="relative min-h-screen flex flex-col overflow-hidden">
      <div className="absolute inset-0 pointer-events-none select-none"
        style={{
          backgroundImage: "linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          WebkitMaskImage: "radial-gradient(ellipse 90% 70% at 50% 40%, black 40%, transparent 100%)",
          maskImage: "radial-gradient(ellipse 90% 70% at 50% 40%, black 40%, transparent 100%)",
        }} />
      <SMarquee />

      <div className="relative z-10 flex-1 flex items-center">
        <div className="max-w-6xl w-full mx-auto px-6 pt-32 pb-20">
          {/* Mobile: stacked layout — image on top */}
          <div className="flex flex-col lg:block">
            {/* Mobile image — centered at top */}
            <div className="flex justify-center mb-10 lg:hidden pointer-events-none select-none">
              <Image src="/logo.png" alt="" width={220} height={220} className="block" style={{ opacity: 0.88 }} priority />
            </div>

            <div className="max-w-xl">
              <h1 className="font-display font-bold text-white leading-[1.0] mb-8"
                style={{ fontSize: "clamp(48px, 6.5vw, 96px)", letterSpacing: "-0.03em" }}>
                Memory for AI,<br />
                <span className="gradient-text" style={{ fontStyle: "italic" }}>owned by no one.</span>
              </h1>
              <p className="text-[17px] text-white/40 leading-relaxed mb-10 max-w-lg font-light">
                Engram is a decentralized vector database on Bittensor. Store embeddings with cryptographic proofs — no AWS, no central authority.
              </p>
              <div className="flex items-center gap-3">
                <Link href="/dashboard"
                  className="group flex items-center gap-2 bg-white text-[#080608] font-bold text-[13px] px-6 py-3 rounded-full hover:bg-white/90 transition-all font-sans">
                  Open Dashboard <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                </Link>
                <a href="#mine"
                  className="flex items-center gap-2 text-white/50 font-medium text-[13px] px-6 py-3 rounded-full border border-white/10 hover:border-white/20 hover:text-white/70 transition-all font-sans">
                  Start Mining <ChevronRight className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>
          </div>
        </div>

        {/* Desktop image — absolute right panel */}
        <div className="absolute right-[4%] top-1/2 -translate-y-1/2 pointer-events-none select-none hidden lg:flex items-center justify-center"
          style={{ width: "42%", height: "80%" }}>
          <Image src="/logo.png" alt="" width={460} height={460} className="block" style={{ opacity: 0.92 }} priority />
        </div>
      </div>
      <div className="h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
    </section>
  );
}

// ── Ticker strip ────────────────────────────────────────────────────────────────

function Strip() {
  const items = ["recall@K scoring", "HMAC-SHA256 proofs", "Kademlia XOR routing", "HNSW indexing", "PyO3 Rust core", "TAO emissions", "content-addressed CIDs", "subnet netuid", "FAISS · Qdrant"];
  return (
    <div className="border-y border-white/[0.05] overflow-hidden py-2.5 bg-[#080608]">
      <div className="flex gap-10 animate-[marquee_35s_linear_infinite] whitespace-nowrap" style={{ width: "max-content" }}>
        {[...items, ...items].map((item, i) => (
          <span key={i} className="flex items-center gap-3 text-[10px] font-mono tracking-[0.14em] uppercase text-white/18">
            <span className="text-[#e040fb]/40">◆</span>
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Protocol ────────────────────────────────────────────────────────────────────

const STEPS = [
  {
    n: "01",
    title: "Ingest",
    tag: "SHA-256 · deterministic · content-addressed",
    file: "ingest.py",
    summary: "Send any text or pre-computed vector. Engram hashes it into a permanent CID — identical inputs always yield the same identifier, forever.",
    detail: [
      "Works with raw text (auto-embedded) or pre-computed float vectors",
      "CID format: v1::<sha256-hex> — 100% reproducible from content",
      "Optional metadata stored alongside the embedding",
    ],
    code: `from engram.sdk.client import EngramClient

client = EngramClient(netuid=42)

cid = client.ingest(
    "Transformers changed NLP in 2017",
    metadata={"source": "arxiv", "year": 2017}
)
# → "v1::a3f9d2e8c7b14f09d6e3..."

# Same input always → same CID
assert client.ingest("Transformers changed NLP in 2017") == cid`,
  },
  {
    n: "02",
    title: "Route & Replicate",
    tag: "Kademlia DHT · XOR distance · replication=3",
    file: "router.py",
    summary: "A Kademlia DHT assigns your CID to 3 miners by XOR-distance. Redundant storage — no single node going offline can lose your data.",
    detail: [
      "XOR(key, node_id) — closest 3 miners by bit distance store the CID",
      "Replication factor is configurable per subnet deployment",
      "ReplicationManager tracks status: HEALTHY → DEGRADED → CRITICAL",
    ],
    code: `# XOR distance routing (deterministic)
key = cid_to_key("v1::a3f9d2e8...")
peers = router.find_closest(key, k=3)
# → [Peer(uid=4,  dist=0x03fa...),
#    Peer(uid=11, dist=0x07c1...),
#    Peer(uid=23, dist=0x0fb8...)]

replication_mgr.register(cid, peers)
# status → ReplicationStatus.HEALTHY`,
  },
  {
    n: "03",
    title: "Query",
    tag: "HNSW · ANN · cosine similarity · <50ms",
    file: "query.py",
    summary: "Submit a query vector. Miners run HNSW approximate nearest-neighbor search and return top-K results ranked by cosine similarity.",
    detail: [
      "FAISS or Qdrant HNSW index — M=16, ef_construction=200",
      "Results sorted by cosine similarity score (0.0 → 1.0)",
      "Typical round-trip: 15–50ms depending on index size",
    ],
    code: `results = client.query(
    "attention mechanism deep learning",
    top_k=5
)

for r in results:
    print(f"{r['score']:.4f}  {r['cid'][:28]}...")

# 0.9821  v1::a3f9d2e8c7b14f09...
# 0.9714  v1::b2c7f1a93e605d22...
# 0.9508  v1::c1d8e4b27a914c33...`,
  },
  {
    n: "04",
    title: "Prove Storage",
    tag: "HMAC-SHA256 · challenge-response · slashable",
    file: "challenge.py",
    summary: "Validators issue random storage challenges. Miners must compute an HMAC-SHA256 proof from their stored embedding. Fail enough times — get slashed.",
    detail: [
      "Validator generates nonce + expiry → miner signs with HMAC-SHA256(nonce ∥ embedding)",
      "proof_rate = passed_challenges / total_challenges",
      "should_slash = total ≥ 5 AND proof_rate < 0.6",
    ],
    code: `# Validator side
challenge = generate_challenge(cid, ttl=60)
# Challenge(cid, nonce=0x3f9a1b..., expires=1712345678)

# Miner computes proof
response = generate_response(challenge, embedding)
# ProofResponse(embedding_hash=..., proof=HMAC(...))

# Validator verifies
passed = verify_response(challenge, response)
# True → proof_rate[uid] += 1/N`,
  },
];

function Protocol() {
  const [active, setActive] = useState(0);
  const step = STEPS[active];

  return (
    <section id="protocol" className="py-24 px-6">
      <div className="max-w-6xl mx-auto">

        {/* Section header */}
        <div className="flex items-end justify-between mb-14">
          <div>
            <p className="text-[10px] font-mono tracking-[0.2em] uppercase text-[#e040fb]/50 mb-3">// how it works</p>
            <h2 className="font-display font-semibold text-[48px] md:text-[60px] text-white leading-[1.0]">
              Four steps.<br />Fully decentralized.
            </h2>
          </div>
          <p className="hidden md:block text-[13px] text-white/30 max-w-[220px] text-right leading-relaxed font-light">
            From raw text to cryptographically verified storage.
          </p>
        </div>

        {/* Step selector tabs */}
        <div className="flex gap-px bg-white/[0.05] rounded-xl overflow-hidden mb-1 p-1">
          {STEPS.map((s, i) => (
            <button key={i} onClick={() => setActive(i)}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg text-[12px] font-mono transition-all ${
                active === i
                  ? "bg-[#1a0f22] text-white border border-[#e040fb]/20"
                  : "text-white/25 hover:text-white/50 hover:bg-white/[0.03]"
              }`}>
              <span className={`text-[10px] ${active === i ? "text-[#e040fb]/60" : "text-white/15"}`}>{s.n}</span>
              <span className="hidden sm:inline">{s.title}</span>
            </button>
          ))}
        </div>

        {/* Active step content */}
        <div className="border border-white/[0.07] rounded-xl overflow-hidden">

          {/* Step header bar */}
          <div className="flex items-center justify-between px-6 py-3 bg-[#0d0b11] border-b border-white/[0.06]">
            <div className="flex items-center gap-3">
              <span className="font-mono text-[10px] text-[#e040fb]/50">{step.n}</span>
              <span className="w-px h-3 bg-white/10" />
              <span className="font-mono text-[10px] text-white/30 tracking-wide">{step.tag}</span>
            </div>
            <span className="font-mono text-[10px] text-white/20">{step.file}</span>
          </div>

          {/* Main content: description + code */}
          <div className="grid md:grid-cols-[1fr_1.3fr]">

            {/* Left: big title + description */}
            <div className="p-8 bg-[#0a0810] border-b md:border-b-0 md:border-r border-white/[0.06]">
              <h3 className="font-display font-semibold leading-[1.0] text-white mb-5"
                style={{ fontSize: "clamp(36px, 4vw, 58px)" }}>
                {step.title}
              </h3>
              <p className="text-[14px] text-white/45 leading-relaxed mb-7 font-light">{step.summary}</p>

              <div className="space-y-3">
                {step.detail.map((d, i) => (
                  <div key={i} className="flex gap-3">
                    <span className="font-mono text-[10px] text-[#e040fb]/40 mt-1 flex-shrink-0">→</span>
                    <span className="text-[13px] text-white/35 leading-relaxed font-light">{d}</span>
                  </div>
                ))}
              </div>

              {/* Step navigation */}
              <div className="flex items-center gap-2 mt-8 pt-6 border-t border-white/[0.05]">
                <button onClick={() => setActive(Math.max(0, active - 1))}
                  disabled={active === 0}
                  className="font-mono text-[11px] text-white/25 hover:text-white/60 disabled:opacity-20 transition-colors px-3 py-1.5 rounded border border-white/[0.06] hover:border-white/10 disabled:cursor-not-allowed">
                  ← prev
                </button>
                <div className="flex gap-1.5 mx-auto">
                  {STEPS.map((_, i) => (
                    <button key={i} onClick={() => setActive(i)}
                      className={`w-1.5 h-1.5 rounded-full transition-all ${active === i ? "bg-[#e040fb]/60 w-4" : "bg-white/15 hover:bg-white/30"}`} />
                  ))}
                </div>
                <button onClick={() => setActive(Math.min(STEPS.length - 1, active + 1))}
                  disabled={active === STEPS.length - 1}
                  className="font-mono text-[11px] text-white/25 hover:text-white/60 disabled:opacity-20 transition-colors px-3 py-1.5 rounded border border-white/[0.06] hover:border-white/10 disabled:cursor-not-allowed">
                  next →
                </button>
              </div>
            </div>

            {/* Right: code */}
            <div className="bg-[#0a0810]">
              <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/[0.06]">
                <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
                <span className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
                <span className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
                <span className="ml-2 font-mono text-[11px] text-white/20">{step.file}</span>
              </div>
              <div className="p-6">
                <PyCode code={step.code} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Features ────────────────────────────────────────────────────────────────────

function Features() {
  return (
    <section id="features" className="py-24 px-6 border-t border-white/[0.06]">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-16">
          <div>
            <p className="text-[10px] font-mono tracking-[0.2em] uppercase text-[#e040fb]/50 mb-3">// capabilities</p>
            <h2 className="font-display font-semibold text-[48px] md:text-[60px] text-white leading-[1.0]">
              Built different.
            </h2>
          </div>
          <p className="text-[14px] text-white/35 max-w-xs leading-relaxed md:text-right font-light">
            Everything you expect from a vector DB — plus cryptographic guarantees no centralized system can offer.
          </p>
        </div>

        {/* Spec table */}
        <div className="border border-white/[0.06] rounded-xl overflow-hidden mb-10">
          {/* Header row */}
          <div className="grid grid-cols-[2fr_3fr_1fr] bg-[#0d0b11] border-b border-white/[0.06] px-6 py-3">
            <span className="text-[10px] font-mono tracking-[0.15em] uppercase text-white/25">Feature</span>
            <span className="text-[10px] font-mono tracking-[0.15em] uppercase text-white/25">Description</span>
            <span className="text-[10px] font-mono tracking-[0.15em] uppercase text-white/25">Status</span>
          </div>
          {[
            { feat: "Content-Addressed CIDs", desc: "SHA-256 fingerprint per embedding — identical data always maps to identical CID", status: "live", color: "#28c840" },
            { feat: "HNSW Index", desc: "FAISS & Qdrant approximate nearest-neighbor — sub-50ms query at any scale", status: "live", color: "#28c840" },
            { feat: "Kademlia DHT Routing", desc: "XOR-distance deterministic routing — same CID always routes to same miners", status: "live", color: "#28c840" },
            { feat: "Storage Proofs", desc: "HMAC-SHA256 challenge-response — validators slash miners who cannot prove storage", status: "live", color: "#28c840" },
            { feat: "Rust Core (PyO3)", desc: "CID generation + proof verification in compiled Rust — 10–50× faster than Python", status: "live", color: "#28c840" },
            { feat: "TAO Incentives", desc: "score = 0.50·recall@K + 0.30·latency + 0.20·proof_rate → TAO emissions", status: "live", color: "#28c840" },
            { feat: "Replication Manager", desc: "Auto-detect degraded CIDs and trigger repair across redundant miners", status: "beta", color: "#febc2e" },
            { feat: "SDK / Python Client", desc: "EngramClient — drop-in for Pinecone, Weaviate, or any vector store", status: "live", color: "#28c840" },
          ].map((row, i) => (
            <div key={i} className={`grid grid-cols-[2fr_3fr_1fr] px-6 py-4 border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors ${i % 2 === 0 ? "" : "bg-white/[0.01]"}`}>
              <span className="text-[13px] font-medium text-white/80 font-sans">{row.feat}</span>
              <span className="text-[13px] text-white/35 leading-relaxed font-light pr-4">{row.desc}</span>
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full" style={{ background: row.color }} />
                <span className="text-[11px] font-mono text-white/30">{row.status}</span>
              </span>
            </div>
          ))}
        </div>

        {/* Scoring formula */}
        <div className="border border-white/[0.06] rounded-xl overflow-hidden">
          <div className="px-6 py-3 bg-[#0d0b11] border-b border-white/[0.06]">
            <span className="text-[10px] font-mono tracking-[0.15em] uppercase text-white/25">Scoring Formula — how miners earn TAO</span>
          </div>
          <div className="px-6 py-5 bg-[#0a0810] grid md:grid-cols-3 gap-6">
            {[
              { weight: "50%", label: "recall@K", desc: "Fraction of correct CIDs returned in top-K query results" },
              { weight: "30%", label: "latency", desc: "Query response time — faster miners score proportionally higher" },
              { weight: "20%", label: "proof_rate", desc: "Fraction of storage challenges answered with a valid HMAC proof" },
            ].map((m) => (
              <div key={m.label} className="flex gap-4">
                <div className="text-[28px] font-bold text-[#e040fb]/50 leading-none font-display w-14 flex-shrink-0">{m.weight}</div>
                <div>
                  <div className="font-mono text-[13px] text-white/70 mb-1">{m.label}</div>
                  <div className="text-[12px] text-white/30 leading-relaxed font-light">{m.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

// ── SDK ─────────────────────────────────────────────────────────────────────────

function SDK() {
  const [tab, setTab] = useState<"python" | "cli">("python");

  const pythonCode = `from engram.sdk.client import EngramClient

# Connect to the Engram subnet
client = EngramClient(netuid=42)

# Ingest text → returns content-addressed CID
cid = client.ingest(
    "Transformers revolutionized NLP in 2017",
    metadata={"source": "arxiv", "year": 2017}
)
# → "v1::a3f9d2e8c7b14f09..."

# Semantic search → top-K by cosine similarity
results = client.query("attention mechanisms", top_k=5)
for r in results:
    print(f"{r['score']:.4f}  {r['cid'][:24]}...")

# Vector search (bypass embedding step)
results = client.query_by_vector(my_vector, top_k=10)`;

  const cliCode = `# Install
pip install engram-subnet

# Ingest a single document
engram ingest "your text here"

# Batch ingest from JSONL file
engram ingest --file ./data/corpus.jsonl

# Semantic search (top-10 results)
engram query "machine learning future" --top-k 10

# Network status — miners, scores, emissions
engram status

# Run demo (requires local neurons running)
engram demo`;

  return (
    <section id="sdk" className="py-24 px-6 border-t border-white/[0.06]">
      <div className="max-w-6xl mx-auto">
        <div className="grid md:grid-cols-[1fr_1.6fr] gap-16 items-start">
          <div className="md:sticky md:top-24">
            <p className="text-[10px] font-mono tracking-[0.2em] uppercase text-[#e040fb]/50 mb-3">// developer SDK</p>
            <h2 className="font-display font-semibold text-[44px] text-white leading-[1.0] mb-5">
              Replace Pinecone<br />in an afternoon.
            </h2>
            <p className="text-[14px] text-white/40 leading-relaxed mb-8 font-light">
              One Python client. Works with any embedding model. No API key, no vendor lock-in.
            </p>

            {/* Comparison table */}
            <div className="border border-white/[0.06] rounded-xl overflow-hidden mb-8">
              <div className="grid grid-cols-3 bg-[#0d0b11] border-b border-white/[0.06] px-4 py-2.5">
                <span className="text-[10px] font-mono text-white/25"></span>
                <span className="text-[10px] font-mono text-white/25 text-center">Pinecone</span>
                <span className="text-[10px] font-mono text-[#e040fb]/50 text-center">Engram</span>
              </div>
              {[
                ["Open source", "✗", "✓"],
                ["No API key", "✗", "✓"],
                ["Storage proofs", "✗", "✓"],
                ["Censorship-resistant", "✗", "✓"],
                ["Self-hostable", "✗", "✓"],
                ["TAO incentives", "✗", "✓"],
              ].map(([label, pine, eng]) => (
                <div key={label} className="grid grid-cols-3 px-4 py-2.5 border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors">
                  <span className="text-[12px] text-white/40 font-light">{label}</span>
                  <span className="text-[12px] text-white/20 text-center">{pine}</span>
                  <span className="text-[12px] text-[#28c840]/70 text-center">{eng}</span>
                </div>
              ))}
            </div>

            <TermBlock title="install">
              <CliCode code={`pip install engram-subnet`} />
            </TermBlock>
          </div>

          <div>
            <TermBlock title={tab === "python" ? "example.py" : "terminal"}>
              <div className="flex gap-1 mb-4 -mt-1">
                {(["python", "cli"] as const).map((t) => (
                  <button key={t} onClick={() => setTab(t)}
                    className={`px-3 py-1 text-[11px] font-mono rounded transition-colors ${
                      tab === t ? "bg-white/10 text-white" : "text-white/25 hover:text-white/50"
                    }`}>
                    {t === "python" ? "Python" : "CLI"}
                  </button>
                ))}
              </div>
              {tab === "python" ? <PyCode code={pythonCode} /> : <CliCode code={cliCode} />}
            </TermBlock>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Mine ────────────────────────────────────────────────────────────────────────

function Mine() {
  return (
    <section id="mine" className="py-24 px-6 border-t border-white/[0.06]">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-16">
          <div>
            <p className="text-[10px] font-mono tracking-[0.2em] uppercase text-[#e040fb]/50 mb-3">// participate</p>
            <h2 className="font-display font-semibold text-[48px] md:text-[60px] text-white leading-[1.0]">
              Earn TAO.<br />Run the network.
            </h2>
          </div>
          <p className="text-[14px] text-white/35 max-w-xs leading-relaxed md:text-right font-light">
            Miners and validators earn from subnet emissions. Performance = yield.
          </p>
        </div>

        {/* Role grid */}
        <div className="grid md:grid-cols-3 gap-3 mb-8">
          {[
            {
              role: "Miner",
              badge: "41% pool",
              desc: "Store embeddings, serve queries, pass storage proof challenges.",
              specs: [
                ["RAM", "4 GB minimum"],
                ["Storage", "100 GB SSD"],
                ["Runtime", "Python 3.10+"],
                ["Stake", "Not required"],
              ],
              featured: true,
            },
            {
              role: "Validator",
              badge: "41% pool",
              desc: "Score miners on recall@K, latency, and proof rate. Set weights on-chain.",
              specs: [
                ["RAM", "8 GB minimum"],
                ["Storage", "20 GB SSD"],
                ["Stake", "TAO required"],
                ["Uptime", "Always-on"],
              ],
              featured: false,
            },
            {
              role: "Builder",
              badge: "Free · testnet",
              desc: "Integrate Engram as your vector store using the Python SDK or CLI.",
              specs: [
                ["Install", "pip install engram-subnet"],
                ["Models", "Any embedding model"],
                ["Access", "Free during testnet"],
                ["Lang", "Python 3.10+"],
              ],
              featured: false,
            },
          ].map((r) => (
            <div key={r.role}
              className={`border rounded-xl overflow-hidden ${r.featured ? "border-[#e040fb]/20 bg-[#0e0913]" : "border-white/[0.06] bg-[#0a0810]"}`}>
              <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
                <span className="text-[15px] font-semibold text-white font-sans">{r.role}</span>
                <span className={`font-mono text-[11px] ${r.featured ? "text-[#e040fb]/70" : "text-white/25"}`}>{r.badge}</span>
              </div>
              <div className="px-6 py-4">
                <p className="text-[13px] text-white/40 leading-relaxed mb-5 font-light">{r.desc}</p>
                <div className="space-y-2">
                  {r.specs.map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between">
                      <span className="font-mono text-[11px] text-white/25 uppercase tracking-wide">{k}</span>
                      <span className="font-mono text-[11px] text-white/50">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Quick start */}
        <TermBlock title="quickstart.sh">
          <CliCode code={`git clone https://github.com/Dipraise1/-Engram-
cd engram
pip install -e ".[miner]"
python neurons/miner.py --wallet.name mywallet --netuid 42`} />
        </TermBlock>
      </div>
    </section>
  );
}

// ── CTA ──────────────────────────────────────────────────────────────────────────

function CTA() {
  return (
    <section className="py-24 px-6 border-t border-white/[0.06]">
      <div className="max-w-6xl mx-auto">
        <div className="border border-white/[0.07] rounded-2xl px-8 py-12 md:px-14 flex flex-col md:flex-row items-start md:items-center justify-between gap-10 bg-[#0a0810]">
          <div className="flex items-center gap-5">
            <Image src="/logo.png" alt="Engram" width={56} height={56} className="block flex-shrink-0" />
            <div>
              <h2 className="font-display font-semibold text-[32px] md:text-[44px] text-white leading-[1.05] mb-2">
                The future of AI memory<br />is decentralized.
              </h2>
              <p className="font-mono text-[11px] text-white/25 tracking-wide">
                open source · bittensor subnet · testnet active · v0.1
              </p>
            </div>
          </div>
          <div className="flex flex-col gap-3 flex-shrink-0 w-full md:w-auto">
            <Link href="/dashboard"
              className="group flex items-center gap-2 bg-white text-[#080608] font-bold text-[13px] px-6 py-3 rounded-full hover:bg-white/90 transition-all justify-center font-sans">
              Open Dashboard <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
            </Link>
            <a href="https://github.com/Dipraise1/-Engram-" target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-2 border border-white/10 text-white/50 font-medium text-[13px] px-6 py-3 rounded-full hover:border-white/20 hover:text-white/70 transition-all justify-center font-sans">
              <Github className="w-3.5 h-3.5" /> View Source
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Footer ────────────────────────────────────────────────────────────────────────

function Footer() {
  return (
    <footer className="border-t border-white/[0.06] py-8 px-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <Image src="/logo.png" alt="Engram" width={22} height={22} className="block" />
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[13px] font-semibold text-white font-sans">Engram</span>
                <span className="font-mono text-[10px] text-white/20">v0.1.0</span>
              </div>
              <p className="text-[11px] text-white/20 font-mono mt-0.5">decentralized vector database · bittensor subnet</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-[12px] text-white/25">
            <Link href="/dashboard" className="hover:text-white/60 transition-colors font-mono">dashboard</Link>
            <a href="#protocol" className="hover:text-white/60 transition-colors font-mono">protocol</a>
            <a href="#sdk" className="hover:text-white/60 transition-colors font-mono">sdk</a>
            <a href="https://github.com/Dipraise1/-Engram-" target="_blank" rel="noopener noreferrer"
              className="hover:text-white/60 transition-colors flex items-center gap-1 font-mono">
              github <ExternalLink className="w-3 h-3" />
            </a>
            <a href="https://bittensor.com" target="_blank" rel="noopener noreferrer"
              className="hover:text-white/60 transition-colors flex items-center gap-1 font-mono">
              bittensor <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────────

export default function Home() {
  return (
    <main>
      <Navbar />
      <Hero />
      <Strip />
      <Protocol />
      <Features />
      <SDK />
      <Mine />
      <CTA />
      <Footer />
    </main>
  );
}
