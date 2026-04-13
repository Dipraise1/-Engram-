"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import Image from "next/image";
import { ArrowLeft, RefreshCw, Search, ChevronRight, ExternalLink } from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────────

interface Miner {
  uid: number;
  hotkey: string | null;
  score: number | null;
  vectors: number;
  latency_ms: number | null;
  proof_rate: number | null;
  stake: number | null;
  status: "online" | "offline";
  peers: number;
}

interface SubnetStats {
  netuid: number;
  vectors: number | null;
  miners: number | null;
  validators: number | null;
  block: number | null;
  avg_score: number | null;
  queries_today: number | null;
  uptime_pct: number | null;
  p50_latency_ms: number | null;
  proof_rate: number | null;
  hotkey: string | null;
  uid: number | null;
  status: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmt(val: number | null, fn: (n: number) => string, fallback = "—"): string {
  return val === null || val === undefined ? fallback : fn(val);
}

// ── Pulse dot ─────────────────────────────────────────────────────────────────

function PulseDot({ active }: { active: boolean }) {
  return (
    <span className="relative inline-flex items-center justify-center w-4 h-4">
      {active ? (
        <>
          <span className="absolute inline-flex h-2 w-2 rounded-full bg-[#28c840] opacity-75 animate-ping" />
          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#28c840]" />
        </>
      ) : (
        <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-white/10" />
      )}
    </span>
  );
}

// ── Score bar ─────────────────────────────────────────────────────────────────

function ScoreBar({ value }: { value: number | null }) {
  if (value === null) {
    return (
      <div className="flex items-center gap-3">
        <div className="flex-1 h-px bg-white/[0.06] rounded-full" />
        <span className="text-[11px] font-mono text-white/20 w-14 text-right">—</span>
      </div>
    );
  }
  const pct = Math.min(100, value * 100);
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-px bg-white/[0.06] rounded-full overflow-hidden relative">
        <div className="absolute inset-y-0 left-0 rounded-full transition-all duration-500"
          style={{
            width: `${pct}%`,
            background: pct > 80
              ? "linear-gradient(90deg, #7c3aed, #e040fb)"
              : pct > 60
              ? "linear-gradient(90deg, #d97706, #f59e0b)"
              : "#ef4444",
          }} />
      </div>
      <span className="text-[11px] font-mono text-white/60 w-14 text-right tabular-nums">
        {value.toFixed(4)}
      </span>
    </div>
  );
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({
  label, value, sub, accent = false, loading = false,
}: {
  label: string; value: string; sub?: string; accent?: boolean; loading?: boolean;
}) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-[10px] uppercase tracking-[0.15em] font-mono text-white/25">{label}</span>
      {loading ? (
        <div className="h-8 w-24 bg-white/[0.04] rounded animate-pulse" />
      ) : (
        <span className={`font-display font-semibold text-[32px] leading-none tracking-tight ${
          accent ? "gradient-text" : "text-white"
        }`}>
          {value}
        </span>
      )}
      {sub && <span className="text-[11px] font-mono text-white/25">{sub}</span>}
    </div>
  );
}

// ── Query playground ──────────────────────────────────────────────────────────

interface QueryResult {
  cid: string;
  score: number;
  metadata: Record<string, unknown>;
}

function QueryPlayground() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<QueryResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState<number | null>(null);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResults([]);
    const t0 = performance.now();
    try {
      const res = await fetch("/api/subnet/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query_text: query, top_k: 5 }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        setError(data.error || "Query failed");
      } else {
        setResults(data.results ?? []);
      }
    } catch {
      setError("Miner unreachable");
    } finally {
      setElapsed(Math.round(performance.now() - t0));
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl overflow-hidden border border-white/[0.07]">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-[#0d0b11] border-b border-white/[0.06]">
        <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
        <span className="ml-2 text-[11px] text-white/25 font-mono tracking-wide">engram — query playground</span>
      </div>

      <div className="bg-[#0a0810] p-5 space-y-4">
        <form onSubmit={handleSearch} className="flex items-center gap-3">
          <span className="text-white/25 font-mono text-sm select-none">$</span>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder='engram query --text "..." --top-k 5'
            className="flex-1 bg-transparent text-[13px] font-mono text-white/70 placeholder-white/15 focus:outline-none"
          />
          <button type="submit" disabled={loading || !query.trim()}
            className="flex items-center gap-1.5 text-[#e040fb] hover:text-white disabled:opacity-30 text-[12px] font-mono transition-colors">
            {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <ChevronRight className="w-3.5 h-3.5" />}
            {loading ? "running" : "run"}
          </button>
        </form>

        {error && (
          <div className="pt-2 border-t border-white/[0.06]">
            <p className="text-[12px] font-mono text-[#f87171]/70">→ {error}</p>
          </div>
        )}

        {results.length > 0 && (
          <div className="pt-2 border-t border-white/[0.06] space-y-0">
            {elapsed !== null && (
              <p className="text-[11px] font-mono text-white/25 mb-3">→ {results.length} results in {elapsed}ms</p>
            )}
            {results.map((r, i) => (
              <div key={i} className="flex items-start justify-between py-2.5 border-b border-white/[0.04] last:border-0">
                <div className="flex-1 min-w-0 space-y-0.5">
                  <div className="text-[11px] font-mono text-[#e040fb]/80 truncate">{r.cid}</div>
                  {Object.keys(r.metadata).length > 0 && (
                    <div className="text-[10px] font-mono text-white/20">
                      {Object.entries(r.metadata).map(([k, v]) => (
                        <span key={k} className="mr-3">
                          <span className="text-[#7c3aed]/60">{k}</span>
                          <span className="text-white/10">=</span>
                          <span className="text-white/30">{String(v)}</span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <span className="ml-4 text-[12px] font-mono text-white/70 tabular-nums flex-shrink-0">
                  {r.score.toFixed(4)}
                </span>
              </div>
            ))}
          </div>
        )}

        {!loading && results.length === 0 && !error && (
          <p className="text-[11px] font-mono text-white/15 pt-1">
            type a query and press enter — runs semantic search against the live miner
          </p>
        )}
      </div>
    </div>
  );
}

// ── Miner table ───────────────────────────────────────────────────────────────

function MinerTable({ miners, loading }: { miners: Miner[]; loading: boolean }) {
  const cols = ["#", "UID", "Hotkey", "Score", "Vectors", "Latency", "Proof", ""];

  return (
    <div className="rounded-xl border border-white/[0.07] overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06] bg-[#0d0b11]">
        <div>
          <h2 className="font-display font-semibold text-[18px] text-white leading-tight">Miner Leaderboard</h2>
          <p className="text-[11px] font-mono text-white/25 mt-0.5">ranked by composite score · 30s refresh</p>
        </div>
        {miners.length > 0 && (
          <span className="text-[10px] font-mono text-white/25 uppercase tracking-widest">
            {miners.filter(m => m.status === "online").length}/{miners.length} online
          </span>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-white/[0.06]">
              {cols.map((col, i) => (
                <th key={i} className={`px-5 py-3 text-[10px] uppercase tracking-[0.15em] font-mono text-white/25 ${i >= 4 ? "text-right" : "text-left"}`}>
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && miners.length === 0 ? (
              Array.from({ length: 3 }).map((_, i) => (
                <tr key={i} className="border-b border-white/[0.04]">
                  {cols.map((_, j) => (
                    <td key={j} className="px-5 py-4">
                      <div className="h-3 bg-white/[0.04] rounded animate-pulse" style={{ width: `${40 + Math.random() * 40}%` }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : miners.length === 0 ? (
              <tr>
                <td colSpan={cols.length} className="px-6 py-10 text-center">
                  <p className="text-[13px] font-mono text-white/20">no miners registered yet</p>
                  <p className="text-[11px] font-mono text-white/10 mt-1">register on subnet 450 to appear here</p>
                </td>
              </tr>
            ) : (
              miners.map((m, i) => (
                <tr key={m.uid} className="border-b border-white/[0.04] last:border-0 hover:bg-white/[0.02] transition-colors">
                  <td className="px-5 py-3.5">
                    <span className="text-[11px] font-mono" style={{
                      color: i === 0 ? "#e040fb" : i === 1 ? "rgba(255,255,255,0.5)" : "rgba(255,255,255,0.2)"
                    }}>
                      {String(i + 1).padStart(2, "0")}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 font-mono text-[12px] text-[#7c3aed]/80">{m.uid}</td>
                  <td className="px-5 py-3.5 font-mono text-[11px] text-white/30 max-w-[140px] truncate">
                    {m.hotkey ? `${m.hotkey.slice(0, 8)}…${m.hotkey.slice(-4)}` : "—"}
                  </td>
                  <td className="px-5 py-3.5 w-44"><ScoreBar value={m.score} /></td>
                  <td className="px-5 py-3.5 text-right font-mono text-[12px] text-white/50 tabular-nums">
                    {m.vectors.toLocaleString()}
                  </td>
                  <td className="px-5 py-3.5 text-right font-mono text-[12px] tabular-nums"
                    style={{ color: m.latency_ms === null ? "rgba(255,255,255,0.2)" : m.latency_ms < 30 ? "#28c840" : m.latency_ms < 100 ? "#febc2e" : "#f87171" }}>
                    {m.latency_ms === null ? "—" : `${m.latency_ms}ms`}
                  </td>
                  <td className="px-5 py-3.5 text-right font-mono text-[12px] text-white/40 tabular-nums">
                    {m.proof_rate === null ? "—" : `${(m.proof_rate * 100).toFixed(0)}%`}
                  </td>
                  <td className="px-5 py-3.5 text-center"><PulseDot active={m.status === "online"} /></td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Dashboard page ────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [stats, setStats] = useState<SubnetStats | null>(null);
  const [miners, setMiners] = useState<Miner[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true);
    try {
      const [statsRes, minersRes] = await Promise.allSettled([
        fetch("/api/subnet/stats"),
        fetch("/api/subnet/miners"),
      ]);
      if (statsRes.status === "fulfilled" && statsRes.value.ok) {
        setStats(await statsRes.value.json());
      }
      if (minersRes.status === "fulfilled" && minersRes.value.ok) {
        setMiners(await minersRes.value.json());
      }
    } finally {
      setLastUpdate(new Date());
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => clearInterval(id);
  }, [refresh]);

  const isLive = stats?.status === "ok";

  return (
    <div className="min-h-screen bg-[#080608] font-sans">
      {/* Nav */}
      <header className="border-b border-white/[0.06] bg-[#080608]/90 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 h-[56px] flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="flex items-center gap-1.5 text-white/25 hover:text-white/60 transition-colors text-[12px] font-mono">
              <ArrowLeft className="w-3.5 h-3.5" /> home
            </Link>
            <span className="w-px h-3.5 bg-white/[0.06]" />
            <div className="flex items-center gap-2">
              <Image src="/logo.png" alt="Engram" width={20} height={20} />
              <span className="font-display font-semibold text-[15px] text-white tracking-tight">Engram</span>
            </div>
            <span className="text-[10px] font-mono text-[#e040fb]/60 border border-[#e040fb]/15 px-2 py-0.5 rounded-full">
              netuid {stats?.netuid ?? 450}
            </span>
            {/* Live indicator */}
            <span className="hidden sm:flex items-center gap-1.5">
              <span className={`relative flex h-1.5 w-1.5 ${isLive ? "" : "opacity-30"}`}>
                {isLive && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#28c840] opacity-75" />}
                <span className={`relative inline-flex rounded-full h-1.5 w-1.5 ${isLive ? "bg-[#28c840]" : "bg-white/20"}`} />
              </span>
              <span className="text-[11px] font-mono text-white/25">{isLive ? "live" : "connecting…"}</span>
            </span>
          </div>

          <button onClick={() => refresh(true)}
            className="flex items-center gap-1.5 text-white/25 hover:text-white/60 transition-colors text-[12px] font-mono">
            <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} />
            {lastUpdate && (
              <span className="hidden sm:inline" suppressHydrationWarning>
                {lastUpdate.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </span>
            )}
          </button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-10 space-y-10">

        {/* Title */}
        <div>
          <h1 className="font-display font-bold text-white leading-[1.0] mb-2"
            style={{ fontSize: "clamp(36px, 4vw, 56px)", letterSpacing: "-0.02em" }}>
            Network Overview
          </h1>
          <p className="text-[14px] font-sans text-white/35 font-light">
            Live state of the Engram subnet — decentralized vector storage on Bittensor
          </p>
        </div>

        {/* Primary stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-white/[0.05] rounded-xl overflow-hidden">
          {[
            {
              label: "Vectors stored",
              value: fmt(stats?.vectors ?? null, n => n.toLocaleString()),
              sub: stats ? `subnet ${stats.netuid}` : "subnet 450",
              accent: true,
            },
            {
              label: "Miners online",
              value: fmt(stats?.miners ?? null, n => String(n)),
              sub: "registered neurons",
              accent: false,
            },
            {
              label: "Avg miner score",
              value: fmt(stats?.avg_score ?? null, n => n.toFixed(4)),
              sub: "recall · latency · proof",
              accent: true,
            },
            {
              label: "Network uptime",
              value: fmt(stats?.uptime_pct ?? null, n => `${(n * 100).toFixed(1)}%`),
              sub: "this process, last 24h",
              accent: false,
            },
          ].map(({ label, value, sub, accent }) => (
            <div key={label} className="bg-[#080608] p-6">
              <StatCard label={label} value={value} sub={sub} accent={accent} loading={loading} />
            </div>
          ))}
        </div>

        {/* Secondary stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { label: "Proof success", value: fmt(stats?.proof_rate ?? null, n => `${(n * 100).toFixed(0)}%`), sub: "last 24h challenges" },
            { label: "P50 latency", value: fmt(stats?.p50_latency_ms ?? null, n => `${n.toFixed(0)}ms`), sub: "query latency" },
            { label: "Queries today", value: fmt(stats?.queries_today ?? null, n => n.toLocaleString()), sub: "semantic searches" },
            { label: "Current block", value: fmt(stats?.block ?? null, n => `#${n.toLocaleString()}`), sub: "~12s per block" },
          ].map(({ label, value, sub }) => (
            <div key={label} className="rounded-xl border border-white/[0.06] bg-[#0a0810] px-5 py-4">
              <StatCard label={label} value={value} sub={sub} loading={loading} />
            </div>
          ))}
        </div>

        {/* Query playground */}
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Search className="w-3.5 h-3.5 text-white/25" />
            <h2 className="font-display font-semibold text-[18px] text-white">Query Playground</h2>
          </div>
          <QueryPlayground />
        </div>

        {/* Miner leaderboard */}
        <MinerTable miners={miners} loading={loading} />

        {/* Footer */}
        <div className="flex items-center justify-between pt-4 pb-8 border-t border-white/[0.06]">
          <span className="text-[11px] font-mono text-white/15">
            engram · netuid {stats?.netuid ?? 450} · bittensor testnet
          </span>
          <a href="https://github.com/Dipraise1/-Engram-" target="_blank" rel="noopener noreferrer"
            className="text-[11px] font-mono text-white/25 hover:text-white/60 transition-colors flex items-center gap-1">
            github <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>
    </div>
  );
}
