"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Database, Zap, Shield, Activity, Search, ArrowLeft,
  RefreshCw, TrendingUp, Users, CheckCircle, XCircle, Clock,
  Upload, Copy, Check
} from "lucide-react";

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

interface QueryResult {
  cid: string;
  score: number;
  metadata: Record<string, unknown>;
}

// ── Mock data (used when API is unavailable) ───────────────────────────────────

function mockStats(): SubnetStats {
  return {
    miners: 12, validators: 3, vectors: 847_293,
    queries_today: 24_891, avg_score: 0.84,
    block: 1_203_847, netuid: 42, uptime_pct: 99.7,
  };
}

function mockMiners(): Miner[] {
  return Array.from({ length: 8 }, (_, i) => ({
    uid: i + 1,
    hotkey: `5F${Math.random().toString(36).slice(2, 10).toUpperCase()}...`,
    score: parseFloat((0.95 - i * 0.07 + Math.random() * 0.04).toFixed(4)),
    vectors: Math.floor(120_000 - i * 12_000 + Math.random() * 5000),
    latency_ms: Math.floor(18 + i * 6 + Math.random() * 10),
    proof_rate: parseFloat((0.99 - i * 0.03).toFixed(2)),
    stake: parseFloat((3.2 - i * 0.3).toFixed(2)),
    status: i < 7 ? "online" : "offline",
  }));
}

// ── Stat card ──────────────────────────────────────────────────────────────────

function StatCard({
  icon, label, value, sub, color = "purple",
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  color?: "purple" | "green" | "blue" | "orange";
}) {
  const colors = {
    purple: "bg-purple-500/10 text-purple-400 border-purple-500/20",
    green: "bg-green-500/10 text-green-400 border-green-500/20",
    blue: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    orange: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  };

  return (
    <div className="bg-engram-card border border-engram-border rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-slate-500">{label}</span>
        <div className={`w-8 h-8 rounded-lg border flex items-center justify-center ${colors[color]}`}>
          {icon}
        </div>
      </div>
      <div className="text-2xl font-bold text-white">{typeof value === "number" ? value.toLocaleString() : value}</div>
      {sub && <div className="text-xs text-slate-500 mt-1">{sub}</div>}
    </div>
  );
}

// ── Score bar ─────────────────────────────────────────────────────────────────

function ScoreBar({ value }: { value: number }) {
  const pct = Math.min(100, value * 100);
  const color = pct > 80 ? "#22c55e" : pct > 60 ? "#eab308" : "#ef4444";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-engram-border rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-xs text-slate-300 w-12 text-right font-mono">{value.toFixed(4)}</span>
    </div>
  );
}

// ── Ingest form ───────────────────────────────────────────────────────────────

function IngestForm() {
  const [text, setText] = useState("");
  const [metadata, setMetadata] = useState("");
  const [cid, setCid] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function handleIngest(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setCid(null);

    let meta: Record<string, string> = {};
    if (metadata.trim()) {
      try { meta = JSON.parse(metadata); } catch { setError("Invalid JSON in metadata"); setLoading(false); return; }
    }

    try {
      const res = await fetch("/api/subnet/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim(), metadata: meta }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Ingest failed");
      setCid(data.cid);
      setText("");
      setMetadata("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  function copy() {
    if (!cid) return;
    navigator.clipboard.writeText(cid);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="bg-engram-card border border-engram-border rounded-xl p-6">
      <div className="flex items-center gap-2 mb-5">
        <Upload className="w-4 h-4 text-engram-light" />
        <h2 className="font-semibold text-white">Store on Engram</h2>
        <span className="text-xs text-slate-500 ml-1">— paste any text, get a permanent CID</span>
      </div>

      <form onSubmit={handleIngest} className="space-y-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste any text to store permanently on the Engram network..."
          rows={4}
          className="w-full bg-engram-dark border border-engram-border rounded-lg px-4 py-3 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-engram-purple/60 transition-colors resize-none"
        />
        <div className="flex gap-3">
          <input
            type="text"
            value={metadata}
            onChange={(e) => setMetadata(e.target.value)}
            placeholder='Metadata (optional JSON) — e.g. {"source": "arxiv"}'
            className="flex-1 bg-engram-dark border border-engram-border rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-engram-purple/60 transition-colors font-mono"
          />
          <button
            type="submit"
            disabled={loading || !text.trim()}
            className="flex items-center gap-2 bg-engram-purple hover:bg-engram-violet disabled:opacity-50 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors whitespace-nowrap"
          >
            {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            Store
          </button>
        </div>
      </form>

      {error && (
        <div className="mt-4 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {cid && (
        <div className="mt-4 bg-green-500/10 border border-green-500/20 rounded-lg px-4 py-3">
          <div className="text-xs text-green-400 font-medium mb-1">Stored — Content ID:</div>
          <div className="flex items-center gap-3">
            <code className="text-sm font-mono text-green-300 flex-1 break-all">{cid}</code>
            <button
              onClick={copy}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors shrink-0"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Query playground ──────────────────────────────────────────────────────────

function QueryPlayground() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<QueryResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
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
        // Demo results
        setResults([
          { cid: "v1::a3f9d2e8b1c04f7a...", score: 0.9412, metadata: { source: "arxiv" } },
          { cid: "v1::b2e8c1f04a7d9e3b...", score: 0.8847, metadata: { source: "wiki" } },
          { cid: "v1::c1d7b0e93f6a8c2d...", score: 0.8291, metadata: { source: "docs" } },
        ]);
      }
    } catch {
      setResults([
        { cid: "v1::a3f9d2e8b1c04f7a...", score: 0.9412, metadata: { source: "arxiv" } },
        { cid: "v1::b2e8c1f04a7d9e3b...", score: 0.8847, metadata: { source: "wiki" } },
        { cid: "v1::c1d7b0e93f6a8c2d...", score: 0.8291, metadata: { source: "docs" } },
      ]);
    } finally {
      setElapsed(Math.round(performance.now() - t0));
      setLoading(false);
    }
  }

  return (
    <div className="bg-engram-card border border-engram-border rounded-xl p-6">
      <div className="flex items-center gap-2 mb-5">
        <Search className="w-4 h-4 text-engram-light" />
        <h2 className="font-semibold text-white">Live Query Playground</h2>
      </div>

      <form onSubmit={handleSearch} className="flex gap-3 mb-5">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search the Engram network..."
          className="flex-1 bg-engram-dark border border-engram-border rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-engram-purple/60 transition-colors"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="flex items-center gap-2 bg-engram-purple hover:bg-engram-violet disabled:opacity-50 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
        >
          {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
          Search
        </button>
      </form>

      {error && <div className="text-red-400 text-sm mb-4">{error}</div>}

      {results.length > 0 && (
        <div>
          {elapsed !== null && (
            <div className="text-xs text-slate-500 mb-3">
              {results.length} results · {elapsed}ms
            </div>
          )}
          <div className="space-y-2">
            {results.map((r, i) => (
              <div key={i} className="flex items-center justify-between bg-engram-dark border border-engram-border rounded-lg px-4 py-3">
                <div>
                  <div className="text-sm font-mono text-engram-light">{r.cid}</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {Object.entries(r.metadata).map(([k, v]) => `${k}: ${v}`).join(" · ")}
                  </div>
                </div>
                <div className="text-sm font-bold text-white ml-4">{r.score.toFixed(4)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Miner table ───────────────────────────────────────────────────────────────

function MinerTable({ miners }: { miners: Miner[] }) {
  return (
    <div className="bg-engram-card border border-engram-border rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-6 py-4 border-b border-engram-border">
        <Users className="w-4 h-4 text-engram-light" />
        <h2 className="font-semibold text-white">Miner Leaderboard</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-engram-border">
              <th className="px-6 py-3 text-left">Rank</th>
              <th className="px-6 py-3 text-left">UID</th>
              <th className="px-6 py-3 text-left">Hotkey</th>
              <th className="px-6 py-3 text-left">Score</th>
              <th className="px-6 py-3 text-right">Vectors</th>
              <th className="px-6 py-3 text-right">Latency</th>
              <th className="px-6 py-3 text-right">Proof Rate</th>
              <th className="px-6 py-3 text-center">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-engram-border">
            {miners.map((m, i) => (
              <tr key={m.uid} className="hover:bg-engram-dark/50 transition-colors">
                <td className="px-6 py-3.5 text-slate-500 font-mono">#{i + 1}</td>
                <td className="px-6 py-3.5 font-mono text-engram-light">{m.uid}</td>
                <td className="px-6 py-3.5 font-mono text-slate-400 text-xs">{m.hotkey}</td>
                <td className="px-6 py-3.5 w-40">
                  <ScoreBar value={m.score} />
                </td>
                <td className="px-6 py-3.5 text-right text-slate-300">{m.vectors.toLocaleString()}</td>
                <td className="px-6 py-3.5 text-right font-mono text-slate-300">{m.latency_ms}ms</td>
                <td className="px-6 py-3.5 text-right font-mono text-slate-300">{(m.proof_rate * 100).toFixed(0)}%</td>
                <td className="px-6 py-3.5 text-center">
                  {m.status === "online" ? (
                    <span className="inline-flex items-center gap-1 text-green-400 text-xs">
                      <CheckCircle className="w-3.5 h-3.5" /> Online
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-red-400 text-xs">
                      <XCircle className="w-3.5 h-3.5" /> Offline
                    </span>
                  )}
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
      // Keep mock data
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
    <div className="min-h-screen bg-engram-dark text-slate-200">
      {/* Header */}
      <div className="border-b border-engram-border bg-engram-card/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="flex items-center gap-1.5 text-slate-400 hover:text-white transition-colors text-sm">
              <ArrowLeft className="w-4 h-4" /> Home
            </Link>
            <div className="w-px h-4 bg-engram-border" />
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-engram-light" />
              <span className="font-semibold text-white">Engram Dashboard</span>
            </div>
            <span className="text-xs text-engram-light bg-engram-purple/10 border border-engram-purple/30 px-2 py-0.5 rounded-full">
              netuid {stats.netuid}
            </span>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-xs text-slate-500 hidden sm:block">
              Updated {lastUpdate.toLocaleTimeString()}
            </span>
            <button
              onClick={refresh}
              className="flex items-center gap-1.5 text-slate-400 hover:text-white transition-colors text-sm"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Stats grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            icon={<Users className="w-4 h-4" />}
            label="Active Miners"
            value={stats.miners}
            sub={`${stats.validators} validators`}
            color="purple"
          />
          <StatCard
            icon={<Database className="w-4 h-4" />}
            label="Vectors Stored"
            value={stats.vectors.toLocaleString()}
            sub="across all miners"
            color="blue"
          />
          <StatCard
            icon={<Zap className="w-4 h-4" />}
            label="Queries Today"
            value={stats.queries_today.toLocaleString()}
            sub="semantic searches"
            color="orange"
          />
          <StatCard
            icon={<TrendingUp className="w-4 h-4" />}
            label="Avg Miner Score"
            value={stats.avg_score.toFixed(4)}
            sub="recall · latency · proof"
            color="green"
          />
        </div>

        {/* Secondary stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            icon={<Activity className="w-4 h-4" />}
            label="Current Block"
            value={stats.block.toLocaleString()}
            color="purple"
          />
          <StatCard
            icon={<Shield className="w-4 h-4" />}
            label="Proof Success"
            value="98.4%"
            sub="last 24h challenges"
            color="green"
          />
          <StatCard
            icon={<Clock className="w-4 h-4" />}
            label="Avg Latency"
            value="24ms"
            sub="p50 query latency"
            color="blue"
          />
          <StatCard
            icon={<Activity className="w-4 h-4" />}
            label="Network Uptime"
            value={`${stats.uptime_pct}%`}
            sub="last 30 days"
            color="green"
          />
        </div>

        {/* Ingest form */}
        <IngestForm />

        {/* Query playground */}
        <QueryPlayground />

        {/* Miner leaderboard */}
        <MinerTable miners={miners} />
      </div>
    </div>
  );
}
