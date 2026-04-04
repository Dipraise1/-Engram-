"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { ArrowLeft, ChevronRight, Copy, Check } from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Section {
  id: string;
  label: string;
  children?: { id: string; label: string }[];
}

// ── Nav structure ─────────────────────────────────────────────────────────────

const NAV: Section[] = [
  { id: "overview", label: "Overview" },
  {
    id: "quickstart",
    label: "Quick Start",
    children: [
      { id: "qs-install", label: "Install" },
      { id: "qs-ingest", label: "Ingest" },
      { id: "qs-query", label: "Query" },
    ],
  },
  {
    id: "sdk",
    label: "Python SDK",
    children: [
      { id: "sdk-client", label: "EngramClient" },
      { id: "sdk-methods", label: "Methods" },
      { id: "sdk-errors", label: "Exceptions" },
      { id: "sdk-langchain", label: "LangChain" },
      { id: "sdk-llama", label: "LlamaIndex" },
    ],
  },
  {
    id: "cli",
    label: "CLI Reference",
    children: [
      { id: "cli-ingest", label: "engram ingest" },
      { id: "cli-query", label: "engram query" },
      { id: "cli-status", label: "engram status" },
    ],
  },
  { id: "protocol", label: "Protocol" },
  { id: "miner", label: "Run a Miner" },
  { id: "validator", label: "Run a Validator" },
];

// ── Copy button ───────────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1800);
      }}
      className="flex items-center gap-1 text-[11px] font-mono text-[#6b5a7e] hover:text-[#c4b5d4] transition-colors"
    >
      {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
      {copied ? "copied" : "copy"}
    </button>
  );
}

// ── Code block ────────────────────────────────────────────────────────────────

function Code({ children, lang = "bash" }: { children: string; lang?: string }) {
  const lines = children.trim().split("\n");

  function colorize(line: string) {
    if (lang === "bash") {
      if (line.trim().startsWith("#")) return <span className="text-[#5c6370]">{line}</span>;
      const parts = line.split(" ");
      const cmd = parts[0];
      if (["pip", "engram", "python", "git", "uvicorn", "btcli"].includes(cmd)) {
        return (
          <>
            <span className="text-[#61afef]">{cmd}</span>
            {parts[1] && <span className="text-[#e06c75]"> {parts[1]}</span>}
            {parts.length > 2 && <span className="text-white/45"> {parts.slice(2).join(" ")}</span>}
          </>
        );
      }
      if (line.startsWith("export ") || line.startsWith("NETUID") || line.includes("=")) {
        return <span className="text-[#d19a66]">{line}</span>;
      }
      return <span className="text-white/60">{line}</span>;
    }

    if (lang === "python") {
      if (line.trim().startsWith("#")) return <span className="text-[#5c6370]">{line}</span>;
      const styled = line
        .replace(/(from|import|def|class|return|for|in|if|not|and|or|True|False|None|async|await|with|as|try|except|print)\b/g, "§kw§$1§/kw§")
        .replace(/(".*?"|'.*?')/g, "§str§$1§/str§")
        .replace(/\b(\d+\.?\d*)\b/g, "§num§$1§/num§")
        .replace(/([a-zA-Z_]\w*)\s*(?=\()/g, "§fn§$1§/fn§")
        .replace(/#.*/g, "§cmt§$&§/cmt§");
      return (
        <span
          dangerouslySetInnerHTML={{
            __html: styled
              .replace(/§kw§(.*?)§\/kw§/g, '<span style="color:#c678dd">$1</span>')
              .replace(/§str§(.*?)§\/str§/g, '<span style="color:#98c379">$1</span>')
              .replace(/§num§(.*?)§\/num§/g, '<span style="color:#d19a66">$1</span>')
              .replace(/§fn§(.*?)§\/fn§/g, '<span style="color:#61afef">$1</span>')
              .replace(/§cmt§(.*?)§\/cmt§/g, '<span style="color:#5c6370">$1</span>'),
          }}
        />
      );
    }

    return <span className="text-white/60">{line}</span>;
  }

  const raw = children.trim();

  return (
    <div className="rounded-xl overflow-hidden border border-[#1e1525] my-4">
      <div className="flex items-center justify-between px-4 py-2 bg-[#0d0b11] border-b border-[#1e1525]">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-[#ff5f57]" />
          <span className="w-2 h-2 rounded-full bg-[#febc2e]" />
          <span className="w-2 h-2 rounded-full bg-[#28c840]" />
          <span className="ml-2 text-[10px] font-mono text-white/20 uppercase tracking-wider">{lang}</span>
        </div>
        <CopyButton text={raw} />
      </div>
      <div className="bg-[#0a0810] px-5 py-4 overflow-x-auto">
        <pre className="text-[12.5px] font-mono leading-[1.85]">
          {lines.map((line, i) => (
            <div key={i}>{colorize(line)}</div>
          ))}
        </pre>
      </div>
    </div>
  );
}

// ── Inline code ───────────────────────────────────────────────────────────────

function Ic({ children }: { children: string }) {
  return (
    <code className="text-[#e040fb] bg-[#1a0d22] px-1.5 py-0.5 rounded text-[12px] font-mono">
      {children}
    </code>
  );
}

// ── Section heading ───────────────────────────────────────────────────────────

function H2({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2
      id={id}
      className="font-display font-light text-white mt-14 mb-4 scroll-mt-20"
      style={{ fontSize: "clamp(24px, 3vw, 36px)", letterSpacing: "-0.01em" }}
    >
      {children}
    </h2>
  );
}

function H3({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h3
      id={id}
      className="text-white font-medium text-lg mt-10 mb-3 scroll-mt-20 font-sans"
    >
      {children}
    </h3>
  );
}

function P({ children }: { children: React.ReactNode }) {
  return <p className="text-[15px] text-[#c4b5d4] leading-relaxed mb-4">{children}</p>;
}

// ── Table ─────────────────────────────────────────────────────────────────────

function Table({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto my-4 rounded-xl border border-[#1e1525]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#1e1525] bg-[#0e0b12]">
            {headers.map((h) => (
              <th key={h} className="px-4 py-3 text-left text-[10px] uppercase tracking-widest font-medium text-[#6b5a7e]">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-[#1a1022] last:border-0">
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-3 text-[#c4b5d4] font-mono text-[12px]">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Callout ───────────────────────────────────────────────────────────────────

function Note({ children }: { children: React.ReactNode }) {
  return (
    <div className="border-l-2 border-[#7c3aed] bg-[#0e0b12] rounded-r-xl px-5 py-4 my-4 text-[14px] text-[#c4b5d4]">
      {children}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function DocsPage() {
  const [active, setActive] = useState("overview");
  const [open, setOpen] = useState<Record<string, boolean>>({ quickstart: true, sdk: true, cli: true });
  const contentRef = useRef<HTMLDivElement>(null);

  // Intersection observer for active section tracking
  useEffect(() => {
    const ids = NAV.flatMap((s) => [s.id, ...(s.children?.map((c) => c.id) ?? [])]);
    const els = ids.map((id) => document.getElementById(id)).filter(Boolean) as HTMLElement[];

    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) setActive(e.target.id);
        }
      },
      { rootMargin: "-20% 0px -75% 0px" }
    );

    els.forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, []);

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    setActive(id);
  }

  return (
    <div className="min-h-screen bg-[#080608] text-[#c4b5d4]">
      {/* Top bar */}
      <header className="fixed top-0 left-0 right-0 z-40 border-b border-[#1e1525] bg-[#080608]/95 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 h-12 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="flex items-center gap-1.5 text-[#6b5a7e] hover:text-[#c4b5d4] transition-colors text-xs font-mono">
              <ArrowLeft className="w-3.5 h-3.5" />
              home
            </Link>
            <span className="w-px h-3.5 bg-[#1e1525]" />
            <span className="font-display font-light text-white text-base">Docs</span>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono text-[#6b5a7e]">
            <a href="https://github.com/Dipraise1/-Engram-" target="_blank" rel="noopener noreferrer"
              className="hover:text-[#c4b5d4] transition-colors">GitHub</a>
            <Link href="/dashboard" className="hover:text-[#c4b5d4] transition-colors">Dashboard</Link>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 pt-12 flex gap-10">
        {/* Sidebar */}
        <aside className="hidden lg:block w-56 flex-shrink-0 pt-10 sticky top-12 self-start h-[calc(100vh-48px)] overflow-y-auto pb-10">
          <nav className="space-y-0.5">
            {NAV.map((section) => (
              <div key={section.id}>
                <button
                  onClick={() => {
                    scrollTo(section.id);
                    if (section.children) setOpen((p) => ({ ...p, [section.id]: !p[section.id] }));
                  }}
                  className={`w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-[13px] transition-colors text-left ${
                    active === section.id
                      ? "text-white bg-[#1a1022]"
                      : "text-[#6b5a7e] hover:text-[#c4b5d4] hover:bg-[#0e0b12]"
                  }`}
                >
                  {section.label}
                  {section.children && (
                    <ChevronRight className={`w-3 h-3 transition-transform ${open[section.id] ? "rotate-90" : ""}`} />
                  )}
                </button>
                {section.children && open[section.id] && (
                  <div className="ml-3 pl-3 border-l border-[#1e1525] mt-0.5 mb-1 space-y-0.5">
                    {section.children.map((child) => (
                      <button
                        key={child.id}
                        onClick={() => scrollTo(child.id)}
                        className={`w-full text-left px-2 py-1 rounded text-[12px] transition-colors ${
                          active === child.id
                            ? "text-[#e040fb]"
                            : "text-[#6b5a7e] hover:text-[#c4b5d4]"
                        }`}
                      >
                        {child.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </nav>
        </aside>

        {/* Content */}
        <main ref={contentRef} className="flex-1 min-w-0 pt-10 pb-24 max-w-3xl">

          {/* ── Overview ─────────────────────────────────────────────────── */}
          <H2 id="overview">Overview</H2>
          <P>
            Engram is a decentralized, content-addressed vector database built on{" "}
            <a href="https://bittensor.com" target="_blank" rel="noopener noreferrer" className="text-[#e040fb] hover:underline">
              Bittensor
            </a>
            . It lets AI applications store and retrieve embeddings without relying on any central server — miners compete to store your vectors, and validators enforce cryptographic storage proofs.
          </P>
          <P>
            Every piece of text produces a deterministic CID (<Ic>v1::a3f2b1...</Ic>) derived from its embedding. The same text always maps to the same CID, regardless of which miner stores it.
          </P>

          <div className="grid grid-cols-3 gap-3 my-6">
            {[
              { label: "Decentralized", desc: "No single point of failure — vectors spread across many miners" },
              { label: "Content-Addressed", desc: "CIDs are derived from embedding content, not location" },
              { label: "Incentivized", desc: "Miners earn TAO for provably storing and serving vectors" },
            ].map(({ label, desc }) => (
              <div key={label} className="rounded-xl border border-[#1e1525] bg-[#0e0b12] p-4">
                <div className="text-[11px] uppercase tracking-widest text-[#e040fb] font-mono mb-1.5">{label}</div>
                <div className="text-[12px] text-[#6b5a7e] leading-relaxed">{desc}</div>
              </div>
            ))}
          </div>

          {/* ── Quick Start ───────────────────────────────────────────────── */}
          <H2 id="quickstart">Quick Start</H2>

          <H3 id="qs-install">Install</H3>
          <Code lang="bash">{`pip install engram-subnet`}</Code>
          <P>Or install from source:</P>
          <Code lang="bash">{`git clone https://github.com/Dipraise1/-Engram-.git
cd -Engram-
pip install -e .`}</Code>

          <H3 id="qs-ingest">Ingest</H3>
          <Code lang="python">{`from engram.sdk import EngramClient

client = EngramClient("http://127.0.0.1:8091")

cid = client.ingest("The transformer architecture changed everything.")
print(cid)  # v1::a3f2b1...`}</Code>

          <H3 id="qs-query">Query</H3>
          <Code lang="python">{`results = client.query("attention mechanisms in deep learning", top_k=5)

for r in results:
    print(f"{r['score']:.4f}  {r['cid']}")`}</Code>

          <Note>
            The CLI defaults to a local FAISS store and sentence-transformers embedder — no OpenAI key required. Set <Ic>USE_LOCAL_EMBEDDER=false</Ic> and provide <Ic>OPENAI_API_KEY</Ic> to use OpenAI embeddings.
          </Note>

          {/* ── SDK ───────────────────────────────────────────────────────── */}
          <H2 id="sdk">Python SDK</H2>
          <P>
            <Ic>EngramClient</Ic> is a lightweight HTTP client for a single Engram miner. It handles embedding, storage, and retrieval through a clean Python interface.
          </P>

          <H3 id="sdk-client">EngramClient</H3>
          <Code lang="python">{`EngramClient(miner_url: str = "http://127.0.0.1:8091", timeout: float = 30.0)`}</Code>

          <Table
            headers={["Parameter", "Type", "Description"]}
            rows={[
              ["miner_url", "str", "Base URL of the miner's HTTP server"],
              ["timeout", "float", "Request timeout in seconds (default 30)"],
            ]}
          />

          <H3 id="sdk-methods">Methods</H3>

          <div className="space-y-8">
            {[
              {
                sig: "ingest(text, metadata=None) → str",
                desc: "Embed and store text on the miner. Returns a CID string.",
                code: `cid = client.ingest(
    "BERT uses bidirectional encoder representations.",
    metadata={"source": "arxiv", "year": "2018"}
)`,
              },
              {
                sig: "query(text, top_k=10) → list[dict]",
                desc: "Semantic search over the miner's stored embeddings.",
                code: `results = client.query("how does self-attention work?", top_k=10)
# [{"cid": "v1::...", "score": 0.9821, "metadata": {...}}, ...]`,
              },
              {
                sig: "batch_ingest_file(path, return_errors=False)",
                desc: "Ingest all records from a JSONL file. Each line must have a \"text\" key.",
                code: `cids = client.batch_ingest_file("data/corpus.jsonl")
print(f"Ingested {len(cids)} records")`,
              },
              {
                sig: "health() → dict",
                desc: "Check miner liveness. Raises MinerOfflineError if unreachable.",
                code: `info = client.health()
# {"status": "ok", "vectors": 42156, "uid": 7}`,
              },
              {
                sig: "is_online() → bool",
                desc: "Returns True if the miner responds to a health check. Never raises.",
                code: `if client.is_online():
    cid = client.ingest("...")`,
              },
            ].map(({ sig, desc, code }) => (
              <div key={sig} className="border border-[#1e1525] rounded-xl overflow-hidden">
                <div className="px-4 py-3 bg-[#0e0b12] border-b border-[#1e1525]">
                  <code className="text-[13px] font-mono text-[#e040fb]">{sig}</code>
                </div>
                <div className="px-4 pt-3 pb-1">
                  <p className="text-[13px] text-[#6b5a7e] mb-0">{desc}</p>
                  <Code lang="python">{code}</Code>
                </div>
              </div>
            ))}
          </div>

          <H3 id="sdk-errors">Exceptions</H3>
          <P>All exceptions inherit from <Ic>EngramError</Ic>:</P>
          <Code lang="python">{`from engram.sdk import (
    EngramError,
    MinerOfflineError,  # miner unreachable
    IngestError,        # miner rejected the request
    QueryError,         # query failed
    InvalidCIDError,    # malformed CID returned
)

try:
    cid = client.ingest("Some important text")
except MinerOfflineError as e:
    print(f"Miner is down: {e}")
except IngestError as e:
    print(f"Ingest rejected: {e}")  # rate limit, low stake, etc.`}</Code>

          <H3 id="sdk-langchain">LangChain Integration</H3>
          <P><Ic>EngramVectorStore</Ic> implements the LangChain <Ic>VectorStore</Ic> interface.</P>
          <Code lang="bash">{`pip install langchain-core engram-subnet`}</Code>
          <Code lang="python">{`from langchain_openai import OpenAIEmbeddings
from engram.sdk.langchain import EngramVectorStore

embeddings = OpenAIEmbeddings()
store = EngramVectorStore(miner_url="http://127.0.0.1:8091", embeddings=embeddings)

# Store documents
store.add_texts(["BERT uses bidirectional transformers."], metadatas=[{"source": "paper"}])

# Similarity search
docs = store.similarity_search("how does attention work?", k=5)

# Use as a retriever in any chain
retriever = store.as_retriever(search_kwargs={"k": 5})

from langchain.chains import RetrievalQA
chain = RetrievalQA.from_chain_type(llm=your_llm, retriever=retriever)
answer = chain.run("What is Bittensor?")`}</Code>

          <H3 id="sdk-llama">LlamaIndex Integration</H3>
          <P><Ic>EngramVectorStore</Ic> from <Ic>engram.sdk.llama_index</Ic> implements <Ic>BasePydanticVectorStore</Ic>.</P>
          <Code lang="bash">{`pip install llama-index-core engram-subnet`}</Code>
          <Code lang="python">{`from llama_index.core import VectorStoreIndex, Document
from llama_index.core.storage.storage_context import StorageContext
from engram.sdk.llama_index import EngramVectorStore

store = EngramVectorStore(miner_url="http://127.0.0.1:8091")
storage_context = StorageContext.from_defaults(vector_store=store)

documents = [Document(text="Bittensor is a decentralised ML network.")]
index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)

response = index.as_query_engine().query("How does Bittensor distribute rewards?")
print(response)`}</Code>

          {/* ── CLI ───────────────────────────────────────────────────────── */}
          <H2 id="cli">CLI Reference</H2>
          <P>The <Ic>engram</Ic> CLI provides a local interface for ingesting text, querying the store, and checking subnet status.</P>
          <Code lang="bash">{`pip install engram-subnet
engram --help`}</Code>

          <H3 id="cli-ingest">engram ingest</H3>
          <Code lang="bash">{`# Basic ingest
engram ingest "The transformer architecture changed everything."

# With metadata
engram ingest "BERT uses bidirectional representations." --meta '{"source":"arxiv"}'

# From a JSONL file
engram ingest --file data/corpus.jsonl

# Ingest a whole directory recursively
engram ingest --dir ./docs`}</Code>

          <Table
            headers={["Flag", "Description"]}
            rows={[
              ["TEXT", "Text to embed and store (positional)"],
              ["--file, -f PATH", "Path to a .txt or .jsonl file to ingest"],
              ["--dir PATH", "Recursively ingest all .txt files in a directory"],
              ["--meta, -m JSON", "JSON metadata string"],
              ["--source, -s STR", 'Source label added to metadata (default "cli")'],
            ]}
          />

          <H3 id="cli-query">engram query</H3>
          <Code lang="bash">{`engram query "how does self-attention work?"
engram query "neural network training" --top-k 10
engram query "vector databases" --meta`}</Code>

          <Table
            headers={["Flag", "Description"]}
            rows={[
              ["TEXT", "Search query (required)"],
              ["--top-k, -k INT", "Number of results (default 5)"],
              ["--meta", "Show metadata column in results"],
            ]}
          />

          <H3 id="cli-status">engram status</H3>
          <Code lang="bash">{`# Local status
engram status

# Live metagraph (connects to chain)
engram status --live --netuid 42`}</Code>

          <Table
            headers={["Variable", "Default", "Description"]}
            rows={[
              ["FAISS_INDEX_PATH", "./data/engram.index", "Local FAISS index file"],
              ["USE_LOCAL_EMBEDDER", "true", "Use sentence-transformers instead of OpenAI"],
              ["OPENAI_API_KEY", "—", "Required if USE_LOCAL_EMBEDDER=false"],
              ["SUBTENSOR_NETWORK", "—", "Network for --live (e.g. finney, test)"],
              ["NETUID", "99", "Default subnet UID"],
            ]}
          />

          {/* ── Protocol ─────────────────────────────────────────────────── */}
          <H2 id="protocol">Protocol</H2>
          <P>
            Engram uses two Bittensor synapse types to coordinate between neurons:
          </P>

          <div className="grid grid-cols-2 gap-4 my-6">
            {[
              {
                name: "IngestSynapse",
                role: "Miner",
                desc: "Carry text + metadata from validator to miner. Miner embeds the text, assigns a CID, stores the vector, and returns the CID.",
                fields: ["text: str", "metadata: dict", "→ cid: str", "→ error: str | None"],
              },
              {
                name: "QuerySynapse",
                role: "Validator",
                desc: "Carry a query text + top_k from validator to miner. Miner embeds the query, runs ANN search over its FAISS index, and returns ranked results.",
                fields: ["query_text: str", "top_k: int", "→ results: list[dict]", "→ error: str | None"],
              },
            ].map(({ name, role, desc, fields }) => (
              <div key={name} className="border border-[#1e1525] rounded-xl overflow-hidden">
                <div className="px-4 py-3 bg-[#0e0b12] border-b border-[#1e1525] flex items-center justify-between">
                  <code className="text-[13px] font-mono text-[#e040fb]">{name}</code>
                  <span className="text-[10px] font-mono uppercase tracking-widest text-[#6b5a7e]">{role}</span>
                </div>
                <div className="px-4 py-3 space-y-2">
                  <p className="text-[12px] text-[#6b5a7e]">{desc}</p>
                  <div className="space-y-0.5">
                    {fields.map((f) => (
                      <div key={f} className="text-[11px] font-mono text-[#c4b5d4]">{f}</div>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <P>
            CIDs are deterministically derived from the embedding vector — <Ic>v1::{"{sha256_hex[:32]}"}</Ic>. The same text always produces the same CID regardless of which miner stores it.
          </P>

          <Note>
            Validators issue random-subset recall challenges to miners. A miner must return the correct vector for a given CID within the challenge window. Proof rate and recall accuracy are the primary scoring signals.
          </Note>

          {/* ── Miner ─────────────────────────────────────────────────────── */}
          <H2 id="miner">Run a Miner</H2>

          <P>Miners store embedding vectors and serve them to validators and SDK clients.</P>

          <Code lang="bash">{`# 1. Clone and install
git clone https://github.com/Dipraise1/-Engram-.git
cd -Engram-
pip install -e .

# 2. Create wallet
btcli wallet new_coldkey --wallet.name engram
btcli wallet new_hotkey --wallet.name engram --wallet.hotkey miner

# 3. Register on subnet
btcli subnet register --netuid 42 --wallet.name engram --wallet.hotkey miner

# 4. Configure .env
cp .env.example .env
# Set SUBTENSOR_NETWORK, NETUID, WALLET_NAME, WALLET_HOTKEY

# 5. Start miner
python neurons/miner.py --wallet.name engram --wallet.hotkey miner --netuid 42`}</Code>

          <Table
            headers={["Variable", "Description"]}
            rows={[
              ["NETUID", "Subnet UID (42 on testnet)"],
              ["SUBTENSOR_NETWORK", "test | finney | ws://..."],
              ["WALLET_NAME", "Coldkey wallet name"],
              ["WALLET_HOTKEY", "Hotkey name"],
              ["MINER_PORT", "Port for miner HTTP server (default 8091)"],
              ["USE_LOCAL_EMBEDDER", "true = sentence-transformers, false = OpenAI"],
              ["FAISS_INDEX_PATH", "Path to persist the vector index"],
            ]}
          />

          <Note>
            Minimum stake to pass the validator&apos;s stake check is configurable (<Ic>MIN_STAKE_TAO</Ic>, default 0.001 τ). On testnet, request test TAO from the faucet or use <Ic>btcli wallet faucet</Ic>.
          </Note>

          {/* ── Validator ─────────────────────────────────────────────────── */}
          <H2 id="validator">Run a Validator</H2>

          <P>Validators score miners by issuing storage proof challenges and measuring recall accuracy, latency, and proof rate.</P>

          <Code lang="bash">{`# Register validator hotkey
btcli subnet register --netuid 42 --wallet.name engram --wallet.hotkey validator

# Start validator
python neurons/validator.py --wallet.name engram --wallet.hotkey validator --netuid 42`}</Code>

          <P>The validator loop:</P>

          <div className="space-y-2 my-4">
            {[
              ["Sync metagraph", "Fetch current neuron list from chain every N blocks"],
              ["Issue challenges", "Send random CIDs to miners and verify returned vectors"],
              ["Score miners", "Composite score = recall accuracy + latency + proof rate"],
              ["Set weights", "Commit scores to chain via btcli / substrate extrinsic"],
            ].map(([step, desc], i) => (
              <div key={step} className="flex items-start gap-4 px-4 py-3 rounded-xl border border-[#1e1525] bg-[#0e0b12]">
                <span className="text-[11px] font-mono text-[#e040fb] w-4 flex-shrink-0 mt-0.5">{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <div className="text-[13px] text-white font-medium mb-0.5">{step}</div>
                  <div className="text-[12px] text-[#6b5a7e]">{desc}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Footer */}
          <div className="mt-16 pt-8 border-t border-[#1e1525] flex items-center justify-between">
            <span className="text-[11px] font-mono text-[#3a2845]">engram docs · v0.1</span>
            <a
              href="https://github.com/Dipraise1/-Engram-"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] font-mono text-[#6b5a7e] hover:text-[#c4b5d4] transition-colors"
            >
              edit on github →
            </a>
          </div>
        </main>
      </div>
    </div>
  );
}
