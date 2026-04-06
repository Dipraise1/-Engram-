"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import Image from "next/image";
import { ArrowRight, Github, ArrowUpRight, ChevronRight, ExternalLink, Check, Circle, Zap } from "lucide-react";

// ── Live stats ──────────────────────────────────────────────────────────────────

function useLiveStats() {
  const [stats, setStats] = useState<{ miners: number; vectors: number; uptime: string; avgScore: string } | null>(null);
  useEffect(() => {
    async function fetch_() {
      try {
        const res = await fetch("/api/subnet/stats");
        if (res.ok) setStats(await res.json());
      } catch { /* no live API yet */ }
    }
    fetch_();
    const id = setInterval(fetch_, 30_000);
    return () => clearInterval(id);
  }, []);
  return stats;
}

// ── Syntax coloring ─────────────────────────────────────────────────────────────

function PyCode({ code }: { code: string }) {
  const lines = code.split("\n");
  return (
    <pre className="text-[12.5px] font-mono leading-[1.85] overflow-x-auto">
      {lines.map((line, i) => {
        if (line.trim().startsWith("#")) return <div key={i} className="text-[#5c6370]">{line}</div>;
        const styled = line
          .replace(/(from|import|def|class|return|for|in|if|not|and|or|True|False|None|async|await|with|as)\b/g, "<kw>$1</kw>")
          .replace(/(".*?"|'.*?')/g, "<str>$1</str>")
          .replace(/(\b\d+\.?\d*\b)/g, "<num>$1</num>")
          .replace(/([a-zA-Z_]\w*)\s*(?=\()/g, "<fn>$1</fn>")
          .replace(/# .*/g, "<cmt>$&</cmt>");
        return (
          <div key={i} dangerouslySetInnerHTML={{
            __html: styled
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
        const parts = line.split(" ");
        if (["engram", "pip", "git", "python", ".venv/bin/python", "cp", "cd"].includes(parts[0])) {
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
          <a href="#roadmap" className="hover:text-white/70 transition-colors">Roadmap</a>
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
        <defs><path id="s-path-mobile" d="M 370 0 C 370 250, 20 250, 20 422 C 20 594, 370 594, 370 844" /></defs>
        <text fontSize="9" fontFamily="JetBrains Mono, monospace" fontWeight="600" letterSpacing="2" fill="rgba(255,255,255,0.10)">
          <textPath href="#s-path-mobile" startOffset="0%">
            <animate attributeName="startOffset" values="0%;-50%" dur="22s" repeatCount="indefinite" />
            {text}
          </textPath>
        </text>
      </svg>
      <svg className="absolute inset-0 w-full h-full pointer-events-none select-none hidden md:block"
        viewBox="0 0 1440 900" preserveAspectRatio="none" aria-hidden="true">
        <defs><path id="s-path-desktop" d="M 1380 0 C 1380 280, 60 280, 60 450 C 60 620, 1380 620, 1380 900" /></defs>
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

// ── Live stats bar ──────────────────────────────────────────────────────────────

function StatsBadge({ label, value, live }: { label: string; value: string; live?: boolean }) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.07]">
      {live && (
        <span className="relative flex h-1.5 w-1.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#28c840] opacity-75" />
          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#28c840]" />
        </span>
      )}
      <span className="font-mono text-[11px] text-white/30">{label}</span>
      <span className="font-mono text-[11px] text-white/70">{value}</span>
    </div>
  );
}

// ── Hero ────────────────────────────────────────────────────────────────────────

function Hero() {
  const stats = useLiveStats();
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
          <div className="flex flex-col lg:block">
            {/* Mobile logo */}
            <div className="flex justify-center mb-10 lg:hidden pointer-events-none select-none">
              <Image src="/logo.png" alt="" width={220} height={220} className="block" style={{ opacity: 0.88 }} priority />
            </div>

            <div className="max-w-xl">
              <h1 className="font-display font-bold text-white leading-[1.0] mb-8"
                style={{ fontSize: "clamp(48px, 6.5vw, 96px)", letterSpacing: "-0.03em" }}>
                Memory for AI,<br />
                <span className="gradient-text" style={{ fontStyle: "italic" }}>owned by no one.</span>
              </h1>
              <p className="text-[17px] text-white/40 leading-relaxed mb-8 max-w-lg font-light">
                Engram is a decentralized vector database on Bittensor. Store embeddings with cryptographic proofs — no AWS, no central authority.
              </p>

              {/* Live stats bar */}
              <div className="flex flex-wrap gap-2 mb-8">
                <StatsBadge label="subnet" value="450 · testnet" live />
                <StatsBadge label="vectors" value={stats ? stats.vectors.toLocaleString() : "1,088"} />
                <StatsBadge label="miners" value={stats ? `${stats.miners} online` : "2 online"} />
                <StatsBadge label="recall@K" value="1.0" />
              </div>

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

        {/* Desktop logo */}
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
  const items = ["recall@K scoring", "HMAC-SHA256 proofs", "Kademlia XOR routing", "HNSW indexing", "PyO3 Rust core", "TAO emissions", "content-addressed CIDs", "subnet · netuid 450", "FAISS · Qdrant"];
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
    n: "01", title: "Ingest",
    tag: "SHA-256 · deterministic · content-addressed", file: "ingest.py",
    summary: "Send any text or pre-computed vector. Engram hashes it into a permanent CID — identical inputs always yield the same identifier, forever.",
    detail: [
      "Works with raw text (auto-embedded) or pre-computed float vectors",
      "CID format: v1::<sha256-hex> — 100% reproducible from content",
      "Optional metadata stored alongside the embedding",
    ],
    code: `from engram.sdk.client import EngramClient

client = EngramClient("http://127.0.0.1:8091")

cid = client.ingest(
    "Transformers changed NLP in 2017",
    metadata={"source": "arxiv", "year": 2017}
)
# → "v1::a3f9d2e8c7b14f09d6e3..."

# Same input always → same CID
assert client.ingest("Transformers changed NLP in 2017") == cid`,
  },
  {
    n: "02", title: "Route & Replicate",
    tag: "Kademlia DHT · XOR distance · replication=3", file: "router.py",
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
    n: "03", title: "Query",
    tag: "HNSW · ANN · cosine similarity · <50ms", file: "query.py",
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
    n: "04", title: "Prove Storage",
    tag: "HMAC-SHA256 · challenge-response · slashable", file: "challenge.py",
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

        <div className="flex gap-px bg-white/[0.05] rounded-xl overflow-hidden mb-1 p-1">
          {STEPS.map((s, i) => (
            <button key={i} onClick={() => setActive(i)}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg text-[12px] font-mono transition-all ${
                active === i ? "bg-[#1a0f22] text-white border border-[#e040fb]/20" : "text-white/25 hover:text-white/50 hover:bg-white/[0.03]"
              }`}>
              <span className={`text-[10px] ${active === i ? "text-[#e040fb]/60" : "text-white/15"}`}>{s.n}</span>
              <span className="hidden sm:inline">{s.title}</span>
            </button>
          ))}
        </div>

        <div className="border border-white/[0.07] rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-6 py-3 bg-[#0d0b11] border-b border-white/[0.06]">
            <div className="flex items-center gap-3">
              <span className="font-mono text-[10px] text-[#e040fb]/50">{step.n}</span>
              <span className="w-px h-3 bg-white/10" />
              <span className="font-mono text-[10px] text-white/30 tracking-wide">{step.tag}</span>
            </div>
            <span className="font-mono text-[10px] text-white/20">{step.file}</span>
          </div>

          <div className="grid md:grid-cols-[1fr_1.3fr]">
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
              <div className="flex items-center gap-2 mt-8 pt-6 border-t border-white/[0.05]">
                <button onClick={() => setActive(Math.max(0, active - 1))} disabled={active === 0}
                  className="font-mono text-[11px] text-white/25 hover:text-white/60 disabled:opacity-20 transition-colors px-3 py-1.5 rounded border border-white/[0.06] hover:border-white/10 disabled:cursor-not-allowed">
                  ← prev
                </button>
                <div className="flex gap-1.5 mx-auto">
                  {STEPS.map((_, i) => (
                    <button key={i} onClick={() => setActive(i)}
                      className={`h-1.5 rounded-full transition-all ${active === i ? "bg-[#e040fb]/60 w-4" : "w-1.5 bg-white/15 hover:bg-white/30"}`} />
                  ))}
                </div>
                <button onClick={() => setActive(Math.min(STEPS.length - 1, active + 1))} disabled={active === STEPS.length - 1}
                  className="font-mono text-[11px] text-white/25 hover:text-white/60 disabled:opacity-20 transition-colors px-3 py-1.5 rounded border border-white/[0.06] hover:border-white/10 disabled:cursor-not-allowed">
                  next →
                </button>
              </div>
            </div>

            <div className="bg-[#0a0810]">
              <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/[0.06]">
                <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
                <span className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
                <span className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
                <span className="ml-2 font-mono text-[11px] text-white/20">{step.file}</span>
              </div>
              <div className="p-6"><PyCode code={step.code} /></div>
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

        <div className="border border-white/[0.06] rounded-xl overflow-hidden mb-10">
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
            { feat: "LangChain / LlamaIndex", desc: "Native adapters — swap your vector store to Engram in one line", status: "live", color: "#28c840" },
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

// ── Roadmap ─────────────────────────────────────────────────────────────────────

const PHASES = [
  {
    phase: "Phase 0",
    title: "Local Prototype",
    status: "done" as const,
    date: "Q1 2026",
    items: ["Rust core (CID + proofs)", "FAISS/Qdrant stores", "Validator scoring loop", "Python SDK", "CLI tooling"],
  },
  {
    phase: "Phase 1",
    title: "Testnet Alpha",
    status: "current" as const,
    date: "Q2 2026",
    items: ["Subnet 450 live", "Miner + validator running", "1,000+ ground truth vectors", "LangChain + LlamaIndex adapters", "Public GitHub + docs"],
  },
  {
    phase: "Phase 2",
    title: "Mainnet Launch",
    status: "upcoming" as const,
    date: "Q3 2026",
    items: ["Mainnet subnet registration", "VPS deployment guides", "Erasure coding replication", "Anti-spam staking", "Prometheus metrics"],
  },
  {
    phase: "Phase 3",
    title: "Ecosystem",
    status: "upcoming" as const,
    date: "Q4 2026",
    items: ["Native LangChain vectorstore", "LlamaIndex integration", "OpenAI-compatible endpoint", "Multi-model embedding support", "Dashboard v2"],
  },
  {
    phase: "Phase 4",
    title: "Scale & Moat",
    status: "upcoming" as const,
    date: "2027",
    items: ["Shared agent memory corpus", "Cross-subnet querying", "Embedding oracle for other subnets", "Enterprise SDK", "10M+ vector network"],
  },
];

function Roadmap() {
  return (
    <section id="roadmap" className="py-24 px-6 border-t border-white/[0.06]">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-16">
          <div>
            <p className="text-[10px] font-mono tracking-[0.2em] uppercase text-[#e040fb]/50 mb-3">// roadmap</p>
            <h2 className="font-display font-semibold text-[48px] md:text-[60px] text-white leading-[1.0]">
              Where we&apos;re going.
            </h2>
          </div>
          <p className="text-[14px] text-white/35 max-w-xs leading-relaxed md:text-right font-light">
            Testnet is live. Mainnet follows. The moat is permanent shared AI memory.
          </p>
        </div>

        {/* Desktop: horizontal timeline */}
        <div className="hidden md:block">
          {/* Phase cards */}
          <div className="grid grid-cols-5 gap-3 mb-0 relative">
            {/* connector line */}
            <div className="absolute top-[28px] left-[10%] right-[10%] h-px bg-white/[0.06] z-0" />

            {PHASES.map((p, i) => (
              <div key={i} className={`relative rounded-xl border overflow-hidden ${
                p.status === "current"
                  ? "border-[#e040fb]/30 bg-[#0e0913]"
                  : p.status === "done"
                  ? "border-[#28c840]/15 bg-[#0a0e09]"
                  : "border-white/[0.06] bg-[#0a0810]"
              }`}>
                {/* Phase top bar */}
                <div className={`flex items-center justify-between px-4 py-3 border-b ${
                  p.status === "current" ? "border-[#e040fb]/20" : "border-white/[0.06]"
                }`}>
                  <span className={`font-mono text-[10px] ${
                    p.status === "current" ? "text-[#e040fb]/70" : p.status === "done" ? "text-[#28c840]/60" : "text-white/25"
                  }`}>{p.phase}</span>
                  <span className={`flex items-center justify-center w-5 h-5 rounded-full ${
                    p.status === "done"
                      ? "bg-[#28c840]/20"
                      : p.status === "current"
                      ? "bg-[#e040fb]/20"
                      : "bg-white/5"
                  }`}>
                    {p.status === "done"
                      ? <Check className="w-3 h-3 text-[#28c840]" />
                      : p.status === "current"
                      ? <Zap className="w-3 h-3 text-[#e040fb]" />
                      : <Circle className="w-3 h-3 text-white/20" />
                    }
                  </span>
                </div>

                <div className="px-4 py-4">
                  <div className="font-mono text-[10px] text-white/25 mb-1.5">{p.date}</div>
                  <div className={`font-display font-semibold text-[18px] leading-tight mb-4 ${
                    p.status === "current" ? "text-white" : p.status === "done" ? "text-white/70" : "text-white/40"
                  }`}>{p.title}</div>
                  <div className="space-y-1.5">
                    {p.items.map((item, j) => (
                      <div key={j} className="flex items-start gap-2">
                        <span className={`font-mono text-[9px] mt-0.5 flex-shrink-0 ${
                          p.status === "done" ? "text-[#28c840]/50" : p.status === "current" ? "text-[#e040fb]/40" : "text-white/15"
                        }`}>→</span>
                        <span className={`text-[11px] leading-relaxed font-light ${
                          p.status === "done" ? "text-white/40" : p.status === "current" ? "text-white/55" : "text-white/25"
                        }`}>{item}</span>
                      </div>
                    ))}
                  </div>
                  {p.status === "current" && (
                    <div className="mt-4 pt-3 border-t border-[#e040fb]/10">
                      <span className="flex items-center gap-1.5">
                        <span className="relative flex h-1.5 w-1.5">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#e040fb] opacity-75" />
                          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#e040fb]" />
                        </span>
                        <span className="font-mono text-[10px] text-[#e040fb]/60">in progress</span>
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Mobile: vertical timeline */}
        <div className="md:hidden space-y-0">
          {PHASES.map((p, i) => (
            <div key={i} className="flex gap-4">
              {/* left column: line + dot */}
              <div className="flex flex-col items-center w-6 flex-shrink-0">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 z-10 ${
                  p.status === "done" ? "bg-[#28c840]/20" : p.status === "current" ? "bg-[#e040fb]/20" : "bg-white/5 border border-white/[0.08]"
                }`}>
                  {p.status === "done"
                    ? <Check className="w-3 h-3 text-[#28c840]" />
                    : p.status === "current"
                    ? <Zap className="w-3 h-3 text-[#e040fb]" />
                    : <Circle className="w-2.5 h-2.5 text-white/20" />
                  }
                </div>
                {i < PHASES.length - 1 && <div className="w-px flex-1 bg-white/[0.06] my-1" />}
              </div>

              {/* right column: content */}
              <div className={`pb-8 flex-1 min-w-0 ${i === PHASES.length - 1 ? "pb-0" : ""}`}>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`font-mono text-[10px] ${
                    p.status === "current" ? "text-[#e040fb]/70" : p.status === "done" ? "text-[#28c840]/60" : "text-white/25"
                  }`}>{p.phase}</span>
                  <span className="font-mono text-[10px] text-white/20">·</span>
                  <span className="font-mono text-[10px] text-white/20">{p.date}</span>
                  {p.status === "current" && (
                    <span className="font-mono text-[9px] text-[#e040fb]/60 bg-[#e040fb]/10 px-1.5 py-0.5 rounded">live</span>
                  )}
                </div>
                <div className={`font-display font-semibold text-[20px] mb-3 ${
                  p.status === "current" ? "text-white" : p.status === "done" ? "text-white/60" : "text-white/35"
                }`}>{p.title}</div>
                <div className="space-y-1.5">
                  {p.items.map((item, j) => (
                    <div key={j} className="flex items-start gap-2">
                      <span className={`font-mono text-[9px] mt-0.5 flex-shrink-0 ${
                        p.status === "done" ? "text-[#28c840]/50" : p.status === "current" ? "text-[#e040fb]/40" : "text-white/15"
                      }`}>→</span>
                      <span className={`text-[12px] font-light ${
                        p.status === "done" ? "text-white/40" : p.status === "current" ? "text-white/55" : "text-white/25"
                      }`}>{item}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
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
client = EngramClient("http://127.0.0.1:8091")

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
engram status --live --netuid 450`;

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

        <div className="grid md:grid-cols-3 gap-3 mb-8">
          {[
            {
              role: "Miner",
              badge: "41% pool",
              desc: "Store embeddings, serve queries, pass storage proof challenges.",
              specs: [["RAM", "4 GB minimum"], ["Storage", "100 GB SSD"], ["Runtime", "Python 3.10+"], ["Stake", "Not required"]],
              featured: true,
            },
            {
              role: "Validator",
              badge: "41% pool",
              desc: "Score miners on recall@K, latency, and proof rate. Set weights on-chain.",
              specs: [["RAM", "8 GB minimum"], ["Storage", "20 GB SSD"], ["Stake", "TAO required"], ["Uptime", "Always-on"]],
              featured: false,
            },
            {
              role: "Builder",
              badge: "Free · testnet",
              desc: "Integrate Engram as your vector store using the Python SDK or CLI.",
              specs: [["Install", "pip install engram-subnet"], ["Models", "Any embedding model"], ["Access", "Free during testnet"], ["Lang", "Python 3.10+"]],
              featured: false,
            },
          ].map((r) => (
            <div key={r.role} className={`border rounded-xl overflow-hidden ${r.featured ? "border-[#e040fb]/20 bg-[#0e0913]" : "border-white/[0.06] bg-[#0a0810]"}`}>
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

        {/* 3-step quickstart */}
        <div className="grid md:grid-cols-3 gap-3 mb-4">
          {[
            {
              step: "01", label: "Clone & install",
              code: `git clone https://github.com/Dipraise1/-Engram-.git
cd -Engram-
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .`,
            },
            {
              step: "02", label: "Configure wallet",
              code: `cp .env.miner.example .env.miner
# Edit .env.miner:
#   WALLET_NAME=your_wallet
#   WALLET_HOTKEY=your_hotkey
#   NETUID=450
#   EXTERNAL_IP=your_server_ip`,
            },
            {
              step: "03", label: "Register & run",
              code: `.venv/bin/python scripts/register_neurons_testnet.py --netuid 450

# Then start the miner
.venv/bin/python neurons/miner.py`,
            },
          ].map((s) => (
            <div key={s.step} className="border border-white/[0.06] rounded-xl overflow-hidden">
              <div className="flex items-center gap-3 px-4 py-2.5 bg-[#0d0b11] border-b border-white/[0.06]">
                <span className="font-mono text-[10px] text-[#e040fb]/50">{s.step}</span>
                <span className="font-mono text-[10px] text-white/30">{s.label}</span>
              </div>
              <div className="bg-[#0a0810] px-4 py-4">
                <CliCode code={s.code} />
              </div>
            </div>
          ))}
        </div>

        <div className="flex items-center gap-3 mt-6">
          <Link href="/docs" className="text-[13px] font-mono text-white/40 hover:text-white/70 transition-colors flex items-center gap-1.5">
            Full miner docs <ChevronRight className="w-3.5 h-3.5" />
          </Link>
          <span className="text-white/10">·</span>
          <a href="https://github.com/Dipraise1/-Engram-" target="_blank" rel="noopener noreferrer"
            className="text-[13px] font-mono text-white/40 hover:text-white/70 transition-colors flex items-center gap-1.5">
            View source <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>
    </section>
  );
}

// ── Community ───────────────────────────────────────────────────────────────────

function DiscordIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057c.002.022.013.043.031.057a19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.738l7.73-8.835L1.254 2.25H8.08l4.253 5.622 5.911-5.622zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  );
}

function Community() {
  return (
    <section id="community" className="py-24 px-6 border-t border-white/[0.06]">
      <div className="max-w-6xl mx-auto">
        <div className="mb-14">
          <p className="text-[10px] font-mono tracking-[0.2em] uppercase text-[#e040fb]/50 mb-3">// community</p>
          <h2 className="font-display font-semibold text-[48px] md:text-[60px] text-white leading-[1.0]">
            Building in public.<br />
            <span className="text-white/40">Join us.</span>
          </h2>
        </div>

        <div className="grid md:grid-cols-[1.6fr_1fr] gap-4">
          {/* Discord card */}
          <div className="relative rounded-2xl border border-[#e040fb]/25 bg-[#0e0913] overflow-hidden p-8 md:p-10 group hover:border-[#e040fb]/40 transition-colors">
            {/* glow */}
            <div className="absolute -top-20 -left-20 w-64 h-64 rounded-full bg-[#e040fb]/5 blur-3xl pointer-events-none" />
            <div className="relative z-10">
              <DiscordIcon className="w-10 h-10 text-[#5865F2] mb-6" />
              <h3 className="font-display font-semibold text-[32px] md:text-[40px] text-white leading-[1.05] mb-3">
                Join the Discord
              </h3>
              <p className="text-[15px] text-white/40 leading-relaxed mb-8 font-light max-w-md">
                We&apos;re building in public. Discuss the protocol, get help running a miner, share feedback, and be part of the earliest community on the subnet.
              </p>
              <a href="https://discord.gg/bittensor" target="_blank" rel="noopener noreferrer"
                className="group/btn inline-flex items-center gap-2 bg-[#5865F2] hover:bg-[#4752C4] text-white font-bold text-[13px] px-6 py-3 rounded-full transition-colors font-sans">
                <DiscordIcon className="w-4 h-4" />
                Join Discord
                <ArrowRight className="w-3.5 h-3.5 group-hover/btn:translate-x-0.5 transition-transform" />
              </a>
            </div>
          </div>

          {/* Right column: GitHub + Twitter */}
          <div className="flex flex-col gap-4">
            <a href="https://github.com/Dipraise1/-Engram-" target="_blank" rel="noopener noreferrer"
              className="flex-1 rounded-xl border border-white/[0.07] bg-[#0a0810] p-6 hover:border-white/[0.12] transition-colors group">
              <div className="flex items-center justify-between mb-4">
                <Github className="w-7 h-7 text-white/60 group-hover:text-white/80 transition-colors" />
                <ArrowUpRight className="w-4 h-4 text-white/20 group-hover:text-white/50 transition-colors" />
              </div>
              <div className="font-display font-semibold text-[22px] text-white mb-1.5">GitHub</div>
              <p className="text-[13px] text-white/35 font-light leading-relaxed">
                Star the repo, open issues, contribute. All development happens in the open.
              </p>
              <div className="mt-4 font-mono text-[11px] text-white/20">Dipraise1/-Engram-</div>
            </a>

            <a href="https://x.com" target="_blank" rel="noopener noreferrer"
              className="flex-1 rounded-xl border border-white/[0.07] bg-[#0a0810] p-6 hover:border-white/[0.12] transition-colors group">
              <div className="flex items-center justify-between mb-4">
                <XIcon className="w-6 h-6 text-white/60 group-hover:text-white/80 transition-colors" />
                <ArrowUpRight className="w-4 h-4 text-white/20 group-hover:text-white/50 transition-colors" />
              </div>
              <div className="font-display font-semibold text-[22px] text-white mb-1.5">Follow on X</div>
              <p className="text-[13px] text-white/35 font-light leading-relaxed">
                Updates, milestones, and announcements. Follow along as the subnet grows.
              </p>
            </a>
          </div>
        </div>
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
            <a href="#mine"
              className="flex items-center gap-2 border border-[#e040fb]/20 text-[#e040fb]/60 font-medium text-[13px] px-6 py-3 rounded-full hover:border-[#e040fb]/40 hover:text-[#e040fb]/80 transition-all justify-center font-sans">
              Start Mining <ChevronRight className="w-3.5 h-3.5" />
            </a>
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
              <p className="text-[11px] text-white/20 font-mono mt-0.5">decentralized vector database · bittensor subnet 450</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-[12px] text-white/25">
            <Link href="/dashboard" className="hover:text-white/60 transition-colors font-mono">dashboard</Link>
            <a href="#protocol" className="hover:text-white/60 transition-colors font-mono">protocol</a>
            <a href="#roadmap" className="hover:text-white/60 transition-colors font-mono">roadmap</a>
            <a href="#sdk" className="hover:text-white/60 transition-colors font-mono">sdk</a>
            <Link href="/docs" className="hover:text-white/60 transition-colors font-mono">docs</Link>
            <a href="https://discord.gg/bittensor" target="_blank" rel="noopener noreferrer"
              className="hover:text-white/60 transition-colors flex items-center gap-1 font-mono">
              discord <ExternalLink className="w-3 h-3" />
            </a>
            <a href="https://x.com" target="_blank" rel="noopener noreferrer"
              className="hover:text-white/60 transition-colors flex items-center gap-1 font-mono">
              twitter <ExternalLink className="w-3 h-3" />
            </a>
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
      <Roadmap />
      <SDK />
      <Mine />
      <Community />
      <CTA />
      <Footer />
    </main>
  );
}
