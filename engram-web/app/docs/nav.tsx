"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search, X, Menu, Github, ChevronRight, ExternalLink } from "lucide-react";
import Image from "next/image";

const NAV = [
  {
    group: "Getting Started",
    items: [
      { href: "/docs", label: "Introduction" },
      { href: "/docs/quickstart", label: "Quick Start" },
      { href: "/docs/memory-ai", label: "Memory AI ✦" },
    ],
  },
  {
    group: "Python SDK",
    items: [
      { href: "/docs/sdk", label: "EngramClient" },
      { href: "/docs/namespaces", label: "Private Namespaces 🔒" },
      { href: "/docs/sdk-langchain", label: "LangChain" },
      { href: "/docs/sdk-llama", label: "LlamaIndex" },
      { href: "/docs/sdk-errors", label: "Exceptions" },
    ],
  },
  {
    group: "CLI",
    items: [
      { href: "/docs/cli", label: "CLI Reference" },
    ],
  },
  {
    group: "Running Nodes",
    items: [
      { href: "/docs/miner", label: "Run a Miner" },
      { href: "/docs/validator", label: "Run a Validator" },
    ],
  },
  {
    group: "Protocol",
    items: [
      { href: "/docs/protocol", label: "Protocol Reference" },
      { href: "/docs/architecture", label: "Architecture" },
    ],
  },
];

const SEARCH_INDEX = [
  { title: "Quick Start", href: "/docs/quickstart", desc: "Install and run your first ingest + query" },
  { title: "Memory AI", href: "/docs/memory-ai", desc: "Permanent per-user AI memory — how it works and how to build it" },
  { title: "EngramClient", href: "/docs/sdk", desc: "Python SDK — ingest, query, batch, auto-discovery" },
  { title: "Private Namespaces", href: "/docs/namespaces", desc: "Encrypted, access-controlled private collections" },
  { title: "LangChain Integration", href: "/docs/sdk-langchain", desc: "Use Engram as a LangChain VectorStore" },
  { title: "LlamaIndex Integration", href: "/docs/sdk-llama", desc: "Use Engram with LlamaIndex" },
  { title: "CLI Reference", href: "/docs/cli", desc: "engram init, ingest, query, status — all commands" },
  { title: "Run a Miner", href: "/docs/miner", desc: "Wallet, registration, config, start" },
  { title: "Run a Validator", href: "/docs/validator", desc: "Scoring loop, weight setting" },
  { title: "Protocol", href: "/docs/protocol", desc: "IngestSynapse, QuerySynapse, CID spec" },
  { title: "Architecture", href: "/docs/architecture", desc: "System design and data flows" },
];

function SearchModal({ onClose }: { onClose: () => void }) {
  const [q, setQ] = useState("");
  const results = q.trim()
    ? SEARCH_INDEX.filter(
        (r) =>
          r.title.toLowerCase().includes(q.toLowerCase()) ||
          r.desc.toLowerCase().includes(q.toLowerCase())
      )
    : SEARCH_INDEX.slice(0, 5);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4 bg-black/60" onClick={onClose}>
      <div
        className="w-full max-w-xl bg-[#0e0b12] border border-[#1e1525] rounded-2xl overflow-hidden shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 py-3 border-b border-[#1e1525]">
          <Search className="w-4 h-4 text-[#6b5a7e] flex-shrink-0" />
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search docs..."
            className="flex-1 bg-transparent text-sm text-white placeholder-[#3a2845] focus:outline-none"
          />
          <button onClick={onClose} className="text-[#6b5a7e] hover:text-[#c4b5d4]">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="max-h-80 overflow-y-auto">
          {results.map((r) => (
            <Link
              key={r.href}
              href={r.href}
              onClick={onClose}
              className="flex items-start gap-3 px-4 py-3 hover:bg-[#1a1022] transition-colors border-b border-[#1a1022] last:border-0"
            >
              <div className="flex-1">
                <div className="text-sm text-white font-medium">{r.title}</div>
                <div className="text-xs text-[#6b5a7e] mt-0.5">{r.desc}</div>
              </div>
              <ChevronRight className="w-4 h-4 text-[#3a2845] flex-shrink-0 mt-0.5" />
            </Link>
          ))}
        </div>
        <div className="px-4 py-2 border-t border-[#1e1525] flex items-center gap-3 text-[10px] text-[#3a2845] font-mono">
          <span>↵ open</span>
          <span>esc close</span>
        </div>
      </div>
    </div>
  );
}

function SidebarLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="space-y-6 py-6">
      {NAV.map((group) => (
        <div key={group.group}>
          <div className="px-3 mb-1.5 text-[10px] uppercase tracking-[0.12em] font-semibold text-[#3a2845]">
            {group.group}
          </div>
          <div className="space-y-0.5">
            {group.items.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onNavigate}
                  className={`block px-3 py-1.5 rounded-lg text-[13px] transition-colors ${
                    active
                      ? "bg-[#1a1022] text-white font-medium"
                      : "text-[#6b5a7e] hover:text-[#c4b5d4] hover:bg-[#0e0b12]"
                  }`}
                >
                  {active && <span className="text-[#e040fb] mr-1.5">·</span>}
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
      <div className="pt-4 border-t border-[#1e1525] space-y-1">
        <a
          href="https://github.com/Dipraise1/-Engram-"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 px-3 py-1.5 text-[13px] text-[#6b5a7e] hover:text-[#c4b5d4] transition-colors"
        >
          <Github className="w-3.5 h-3.5" />
          GitHub
          <ExternalLink className="w-3 h-3 ml-auto" />
        </a>
        <Link
          href="/dashboard"
          className="flex items-center gap-2 px-3 py-1.5 text-[13px] text-[#6b5a7e] hover:text-[#c4b5d4] transition-colors"
        >
          Dashboard
          <ExternalLink className="w-3 h-3 ml-auto" />
        </Link>
      </div>
    </nav>
  );
}

export function DocsNav() {
  const [searching, setSearching] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearching(true);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => setMobileOpen(false), [pathname]);

  return (
    <>
      {searching && <SearchModal onClose={() => setSearching(false)} />}

      {/* Top bar */}
      <header className="fixed top-0 left-0 right-0 z-40 h-14 border-b border-[#1e1525] bg-[#080608]/95 backdrop-blur-xl flex items-center">
        <div className="w-full flex items-center px-4 gap-4">
          <Link href="/" className="flex items-center gap-2.5 flex-shrink-0">
            <Image src="/logo.png" alt="Engram" width={22} height={22} />
            <span className="font-display font-semibold text-white text-[15px]">Engram</span>
            <span className="text-[10px] font-mono text-[#6b5a7e] border border-[#1e1525] px-1.5 py-0.5 rounded">
              Docs
            </span>
          </Link>

          <button
            onClick={() => setSearching(true)}
            className="flex-1 max-w-sm flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[#1e1525] bg-[#0e0b12] text-[13px] text-[#3a2845] hover:border-[#3a2845] transition-colors ml-4"
          >
            <Search className="w-3.5 h-3.5" />
            <span className="flex-1 text-left">Search docs...</span>
            <kbd className="text-[10px] font-mono border border-[#1e1525] px-1.5 py-0.5 rounded text-[#3a2845]">⌘K</kbd>
          </button>

          <div className="ml-auto flex items-center gap-3">
            <a href="https://github.com/Dipraise1/-Engram-" target="_blank" rel="noopener noreferrer"
              className="text-[#6b5a7e] hover:text-[#c4b5d4] transition-colors hidden sm:block">
              <Github className="w-4 h-4" />
            </a>
            <Link href="/dashboard"
              className="hidden sm:flex items-center gap-1.5 text-[12px] font-medium bg-white text-[#080608] px-3 py-1.5 rounded-full hover:bg-white/90 transition-colors">
              Dashboard
            </Link>
            <button className="lg:hidden text-[#6b5a7e] hover:text-white" onClick={() => setMobileOpen((v) => !v)}>
              {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </header>

      {/* Mobile sidebar */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-30 pt-14">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
          <div className="relative bg-[#080608] border-r border-[#1e1525] w-64 h-full overflow-y-auto px-3">
            <SidebarLinks onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      {/* Desktop sidebar */}
      <aside className="hidden lg:block fixed left-0 top-14 bottom-0 w-60 border-r border-[#1e1525] overflow-y-auto px-3 bg-[#080608]">
        <SidebarLinks />
      </aside>
    </>
  );
}
