"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { ArrowLeft, RefreshCw, Search, ChevronRight } from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────────

interface Miner {
  uid: number;
  hotkey: string;
  score: number;
  vectors: number;
  latency_ms: number;
  proof_rate: number;
  stake: number;
  status: "online" | "offline";
}

interface SubnetStats {
  miners: number;
  validators: number;
  vectors: number;
  queries_today: number;
  avg_score: number;
  block: number;
  netuid: number;
  uptime_pct: number;
}

// ── Mock data ─────────────────────────────────────────────────────────────────

function mockStats(): SubnetStats {
  return {
    miners: 12, validators: 3, vectors: 847_293,
    queries_today: 24_891, avg_score: 0.8402,
    block: 1_203_847, netuid: 2, uptime_pct: 99.7,
  };
}

function mockMiners(): Miner[] {
  return Array.from({ length: 8 }, (_, i) => ({
    uid: i + 1,
    hotkey: `5F${Math.random().toString(36).slice(2, 10).toUpperCase()}...xK9`,
    score: parseFloat((0.9538 - i * 0.067 + Math.random() * 0.04).toFixed(4)),
    vectors: Math.floor(120_000 - i * 12_000 + Math.random() * 5000),
    latency_ms: Math.floor(18 + i * 6 + Math.random() * 10),
    proof_rate: parseFloat((0.99 - i * 0.03).toFixed(2)),
    stake: parseFloat((3.2 - i * 0.3).toFixed(2)),
    status: i < 7 ? "online" : "offline",
  }));
}

// ── Pulse dot ─────────────────────────────────────────────────────────────────

function PulseDot({ active }: { active: boolean }) {
  return (
    <span className="relative inline-flex items-center justify-center w-4 h-4">
      {active ? (
        <>
          <span className="absolute inline-flex h-2 w-2 rounded-full bg-emerald-400 opacity-75 animate-ping" />
          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-400" />
        </>
      ) : (
        <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#3a2845]" />
      )}
    </span>
  );
}

// ── Score bar ─────────────────────────────────────────────────────────────────

function ScoreBar({ value }: { value: number }) {
  const pct = Math.min(100, value * 100);
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-px bg-[#1e1525] rounded-full overflow-hidden relative">
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{
            width: `${pct}%`,
            background:
              pct > 80
                ? "linear-gradient(90deg, #7c3aed, #e040fb)"
                : pct > 60
                ? "linear-gradient(90deg, #d97706, #f59e0b)"
                : "#ef4444",
          }}
        />
      </div>
      <span className="text-xs font-mono text-[#c4b5d4] w-14 text-right tabular-nums">
        {value.toFixed(4)}
      </span>
    </div>
  );
}

// ── Stat block ────────────────────────────────────────────────────────────────

function Stat({
  label,
  value,
  sub,
  accent = false,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[10px] uppercase tracking-widest font-medium text-[#6b5a7e]">
        {label}
      </span>
      <span
        className={`font-display text-3xl font-light leading-none tracking-tight ${
          accent
            ? "bg-gradient-to-r from-[#f87171] via-[#e040fb] to-[#7c3aed] bg-clip-text text-transparent"
            : "text-white"
        }`}
      >
        {value}
      </span>
      {sub && <span className="text-[11px] text-[#6b5a7e]">{sub}</span>}
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
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState<number | null>(null);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    const t0 = performance.now();
    try {
      const res = await fetch("/api/subnet/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query_text: query, top_k: 5 }),
      });
      if (res.ok) {
        const data = await res.json();
        setResults(data.results ?? []);
      } else {
        throw new Error("not ok");
      }
    } catch {
      setResults([
        { cid: "v1::a3f9d2e8b1c04f7a9832dc561b2e0f8d", score: 0.9412, metadata: { source: "arxiv", dim: 1536 } },
        { cid: "v1::b2e8c1f04a7d9e3b6541fc872a3d1e09", score: 0.8847, metadata: { source: "wiki", dim: 1536 } },
        { cid: "v1::c1d7b0e93f6a8c2d4320eb981f4c2a71", score: 0.8291, metadata: { source: "docs", dim: 768 } },
      ]);
    } finally {
      setElapsed(Math.round(performance.now() - t0));
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl overflow-hidden border border-[#1e1525]">
      {/* Terminal chrome */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-[#0d0b11] border-b border-[#1e1525]">
        <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
        <span className="ml-2 text-[11px] text-white/25 font-mono tracking-wide">
          engram — query playground
        </span>
      </div>

      <div className="bg-[#0a0810] p-5 space-y-4">
        <form onSubmit={handleSearch} className="flex items-center gap-3">
          <span className="text-[#6b5a7e] font-mono text-sm select-none">$</span>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder='engram query --text "..." --top-k 5'
            className="flex-1 bg-transparent text-sm font-mono text-[#c4b5d4] placeholder-[#3a2845] focus:outline-none"
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="flex items-center gap-1.5 text-[#e040fb] hover:text-white disabled:opacity-30 text-sm font-mono transition-colors"
          >
            {loading ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5" />
            )}
            {loading ? "running" : "run"}
          </button>
        </form>

        {results.length > 0 && (
          <div className="space-y-0 pt-2 border-t border-[#1e1525]">
            {elapsed !== null && (
              <div className="text-[11px] font-mono text-[#6b5a7e] mb-3">
                → {results.length} results in {elapsed}ms
              </div>
            )}
            {results.map((r, i) => (
              <div
                key={i}
                className="flex items-start justify-between py-2.5 border-b border-[#1a1022] last:border-0"
              >
                <div className="flex-1 min-w-0 space-y-0.5">
                  <div className="text-[11px] font-mono text-[#e040fb] truncate">{r.cid}</div>
                  <div className="text-[10px] font-mono text-[#6b5a7e]">
                    {Object.entries(r.metadata).map(([k, v]) => (
                      <span key={k} className="mr-3">
                        <span className="text-[#7c3aed]">{k}</span>
                        <span className="text-[#3a2845]">=</span>
                        <span>{String(v)}</span>
                      </span>
                    ))}
                  </div>
                </div>
                <span className="ml-4 text-sm font-mono font-medium text-white tabular-nums flex-shrink-0">
                  {r.score.toFixed(4)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Miner table ───────────────────────────────────────────────────────────────

function MinerTable({ miners }: { miners: Miner[] }) {
  return (
    <div className="rounded-xl border border-[#1e1525] overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 border-b border-[#1e1525] bg-[#0e0b12]">
        <div>
          <h2 className="font-display text-lg font-light text-white">
            Miner Leaderboard
          </h2>
          <p className="text-[11px] text-[#6b5a7e] mt-0.5">
            ranked by composite score · 30s refresh
          </p>
        </div>
        <span className="text-[10px] uppercase tracking-widest text-[#6b5a7e] font-medium">
          {miners.filter((m) => m.status === "online").length}/{miners.length} online
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1e1525]">
              {[
                { label: "#", align: "left" },
                { label: "UID", align: "left" },
                { label: "Hotkey", align: "left" },
                { label: "Score", align: "left" },
                { label: "Vectors", align: "right" },
                { label: "Latency", align: "right" },
                { label: "Proof", align: "right" },
                { label: "", align: "center" },
              ].map(({ label, align }, i) => (
                <th
                  key={i}
                  className={`px-5 py-3 text-[10px] uppercase tracking-widest font-medium text-[#6b5a7e] text-${align}`}
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {miners.map((m, i) => (
              <tr
                key={m.uid}
                className="border-b border-[#1a1022] last:border-0 hover:bg-[#0e0b12]/60 transition-colors"
              >
                <td className="px-5 py-3.5">
                  <span
                    className="text-xs font-mono"
                    style={{
                      color:
                        i === 0
                          ? "#e040fb"
                          : i === 1
                          ? "#c4b5d4"
                          : i === 2
                          ? "#7c6a5a"
                          : "#3a2845",
                    }}
                  >
                    {String(i + 1).padStart(2, "0")}
                  </span>
                </td>
                <td className="px-5 py-3.5 font-mono text-xs text-[#7c3aed]">{m.uid}</td>
                <td className="px-5 py-3.5 font-mono text-[11px] text-[#6b5a7e] max-w-[140px] truncate">
                  {m.hotkey}
                </td>
                <td className="px-5 py-3.5 w-44">
                  <ScoreBar value={m.score} />
                </td>
                <td className="px-5 py-3.5 text-right font-mono text-xs text-[#c4b5d4] tabular-nums">
                  {m.vectors.toLocaleString()}
                </td>
                <td
                  className="px-5 py-3.5 text-right font-mono text-xs tabular-nums"
                  style={{
                    color:
                      m.latency_ms < 30
                        ? "#34d399"
                        : m.latency_ms < 60
                        ? "#fbbf24"
                        : "#f87171",
                  }}
                >
                  {m.latency_ms}ms
                </td>
                <td className="px-5 py-3.5 text-right font-mono text-xs text-[#c4b5d4] tabular-nums">
                  {(m.proof_rate * 100).toFixed(0)}%
                </td>
                <td className="px-5 py-3.5 text-center">
                  <PulseDot active={m.status === "online"} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Dashboard page ────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [stats, setStats] = useState<SubnetStats>(mockStats());
  const [miners, setMiners] = useState<Miner[]>(mockMiners());
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const [statsRes, minersRes] = await Promise.all([
        fetch("/api/subnet/stats"),
        fetch("/api/subnet/miners"),
      ]);
      if (statsRes.ok) setStats(await statsRes.json());
      if (minersRes.ok) setMiners(await minersRes.json());
    } catch {
      /* keep mock data */
    } finally {
      setLastUpdate(new Date());
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <div className="min-h-screen bg-[#080608] text-[#c4b5d4]">
      {/* Nav */}
      <header className="border-b border-[#1e1525] bg-[#080608]/90 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 h-12 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="flex items-center gap-1.5 text-[#6b5a7e] hover:text-[#c4b5d4] transition-colors text-xs font-mono"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              home
            </Link>
            <span className="w-px h-3.5 bg-[#1e1525]" />
            <span className="font-display text-white font-light text-base">
              Engram
            </span>
            <span className="text-[10px] font-mono text-[#e040fb] border border-[#3a1a45] bg-[#e040fb]/5 px-2 py-0.5 rounded-full">
              netuid {stats.netuid}
            </span>
            <span className="text-[10px] font-mono text-[#6b5a7e] hidden sm:inline">
              block #{stats.block.toLocaleString()}
            </span>
          </div>

          <button
            onClick={refresh}
            className="flex items-center gap-1.5 text-[#6b5a7e] hover:text-[#c4b5d4] transition-colors text-xs font-mono"
          >
            <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} />
            <span className="hidden sm:inline" suppressHydrationWarning>
              {lastUpdate.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </span>
          </button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-10 space-y-10">
        {/* Title */}
        <div className="space-y-1">
          <h1 className="font-display font-light text-white" style={{ fontSize: "clamp(36px, 4vw, 56px)", letterSpacing: "-0.01em", lineHeight: 1 }}>
            Network Overview
          </h1>
          <p className="text-sm text-[#6b5a7e]">
            Live state of the Engram subnet — decentralized vector storage on Bittensor
          </p>
        </div>

        {/* Primary stats — flush grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-[#1e1525] rounded-xl overflow-hidden">
          {[
            {
              label: "Vectors stored",
              value: stats.vectors.toLocaleString(),
              sub: `${stats.miners} miners · ${stats.validators} validators`,
              accent: true,
            },
            {
              label: "Queries today",
              value: stats.queries_today.toLocaleString(),
              sub: "semantic searches",
              accent: false,
            },
            {
              label: "Avg miner score",
              value: stats.avg_score.toFixed(4),
              sub: "recall · latency · proof",
              accent: true,
            },
            {
              label: "Network uptime",
              value: `${stats.uptime_pct}%`,
              sub: "30-day average",
              accent: false,
            },
          ].map(({ label, value, sub, accent }) => (
            <div key={label} className="bg-[#080608] p-6">
              <Stat label={label} value={value} sub={sub} accent={accent} />
            </div>
          ))}
        </div>

        {/* Secondary stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: "Proof success", value: "98.4%", sub: "last 24h challenges" },
            { label: "P50 latency", value: "24ms", sub: "across all miners" },
            {
              label: "Online miners",
              value: String(miners.filter((m) => m.status === "online").length),
              sub: `of ${miners.length} registered`,
            },
            { label: "Current block", value: `#${stats.block.toLocaleString()}`, sub: "~12s per block" },
          ].map(({ label, value, sub }) => (
            <div
              key={label}
              className="rounded-xl border border-[#1e1525] bg-[#0e0b12] px-5 py-4"
            >
              <Stat label={label} value={value} sub={sub} />
            </div>
          ))}
        </div>

        {/* Query playground */}
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Search className="w-3.5 h-3.5 text-[#6b5a7e]" />
            <h2 className="font-display text-lg font-light text-white">
              Query Playground
            </h2>
          </div>
          <QueryPlayground />
        </div>

        {/* Leaderboard */}
        <MinerTable miners={miners} />

        {/* Footer */}
        <div className="flex items-center justify-between pt-4 pb-8 border-t border-[#1e1525]">
          <span className="text-[11px] font-mono text-[#3a2845]">
            engram subnet · netuid {stats.netuid}
          </span>
          <a
            href="https://github.com/dipraise1/engram"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] font-mono text-[#6b5a7e] hover:text-[#c4b5d4] transition-colors"
          >
            github →
          </a>
        </div>
      </div>
    </div>
  );
}
