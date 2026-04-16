"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Search, Plus, Loader2, XCircle, Copy, Check, Code, Link2, Upload, FileText } from "lucide-react";

interface IngestResult {
  cid: string;
  text: string;
  error?: string;
}

interface QueryResult {
  cid: string;
  score: number;
  metadata: Record<string, string>;
}

export default function PlaygroundPage() {
  // ── Ingest state ────────────────────────────────────────────────────────────
  const [ingestTab, setIngestTab] = useState<"text" | "url" | "file">("text");
  const [ingestText, setIngestText] = useState("");
  const [ingestUrl, setIngestUrl] = useState("");
  const [ingestFilename, setIngestFilename] = useState<string | null>(null);
  const [ingestLoading, setIngestLoading] = useState(false);
  const [ingestHistory, setIngestHistory] = useState<IngestResult[]>([]);
  const [ingestError, setIngestError] = useState<string | null>(null);
  const [toastCid, setToastCid] = useState<string | null>(null);

  // ── Query state ─────────────────────────────────────────────────────────────
  const [queryText, setQueryText] = useState("");
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryResults, setQueryResults] = useState<QueryResult[] | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [queryLatency, setQueryLatency] = useState<number | null>(null);

  // ── Copy state ──────────────────────────────────────────────────────────────
  const [copiedCid, setCopiedCid] = useState<string | null>(null);
  const [copiedCode, setCopiedCode] = useState<"ingest" | "query" | null>(null);

  // ── SDK snippet state ────────────────────────────────────────────────────────
  const [lastIngestText, setLastIngestText] = useState<string | null>(null);
  const [lastQueryText, setLastQueryText] = useState<string | null>(null);

  // ── Toast helper ─────────────────────────────────────────────────────────────
  function showToast(cid: string) {
    setToastCid(cid);
    setTimeout(() => setToastCid(null), 3500);
  }

  // ── Ingest ──────────────────────────────────────────────────────────────────
  async function handleIngest() {
    setIngestLoading(true);
    setIngestError(null);

    try {
      let text = "";
      let source = "playground";

      if (ingestTab === "text") {
        text = ingestText.trim();
        if (!text) { setIngestLoading(false); return; }
      } else if (ingestTab === "url") {
        const url = ingestUrl.trim();
        if (!url) { setIngestLoading(false); return; }
        // Fetch via a simple proxy approach — fetch the URL server-side via ingest API
        const fetchRes = await fetch(url, { signal: AbortSignal.timeout(10000) });
        if (!fetchRes.ok) throw new Error(`Fetching URL failed (${fetchRes.status})`);
        const ct = fetchRes.headers.get("content-type") ?? "";
        text = ct.includes("json") ? JSON.stringify(await fetchRes.json(), null, 2) : await fetchRes.text();
        text = text.slice(0, 8192);
        source = url;
      } else if (ingestTab === "file") {
        text = ingestText.trim();
        if (!text) { setIngestLoading(false); return; }
        source = ingestFilename ?? "file";
      }

      const res = await fetch("/api/subnet/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, metadata: { source } }),
      });

      const data = await res.json();

      if (!res.ok || data.error) {
        setIngestError(data.error || "Ingest failed.");
      } else {
        setIngestHistory((prev) => [{ cid: data.cid, text }, ...prev]);
        setLastIngestText(text);
        if (ingestTab === "text") setIngestText("");
        else if (ingestTab === "url") setIngestUrl("");
        else { setIngestText(""); setIngestFilename(null); }
        showToast(data.cid);
      }
    } catch (err) {
      setIngestError(err instanceof Error ? err.message : "Could not reach the miner. Is it running?");
    } finally {
      setIngestLoading(false);
    }
  }

  // ── Query ───────────────────────────────────────────────────────────────────
  async function handleQuery() {
    const text = queryText.trim();
    if (!text) return;

    setQueryLoading(true);
    setQueryError(null);
    setQueryResults(null);

    const t0 = Date.now();

    try {
      const res = await fetch("/api/subnet/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query_text: text, top_k: 5 }),
      });

      const data = await res.json();
      setQueryLatency(Date.now() - t0);

      if (!res.ok || data.error) {
        setQueryError(data.error || "Query failed.");
      } else {
        setQueryResults(data.results || []);
        setLastQueryText(text);
      }
    } catch {
      setQueryError("Could not reach the miner. Is it running?");
    } finally {
      setQueryLoading(false);
    }
  }

  // ── Copy CID ─────────────────────────────────────────────────────────────────
  function copyCid(cid: string) {
    navigator.clipboard.writeText(cid).then(() => {
      setCopiedCid(cid);
      setTimeout(() => setCopiedCid(null), 1500);
    });
  }

  // ── Copy SDK snippet ─────────────────────────────────────────────────────────
  function copyCode(type: "ingest" | "query", code: string) {
    navigator.clipboard.writeText(code).then(() => {
      setCopiedCode(type);
      setTimeout(() => setCopiedCode(null), 1500);
    });
  }

  // ── Quick-fill query from ingested text ─────────────────────────────────────
  function prefillQuery(text: string) {
    setQueryText(text.slice(0, 80));
    setQueryResults(null);
    setQueryError(null);
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Toast */}
      {toastCid && (
        <div className="fixed top-4 right-4 z-50 flex items-center gap-2.5 bg-[#0f0f1a] border border-green-500/30 rounded-xl px-4 py-3 shadow-2xl animate-in slide-in-from-top-2">
          <Check className="w-4 h-4 text-green-400 shrink-0" />
          <div>
            <p className="text-sm text-white font-medium">Stored on Engram</p>
            <p className="text-xs font-mono text-purple-300">{toastCid.slice(0, 10)}…{toastCid.slice(-8)}</p>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="border-b border-white/10 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-2 text-white/50 hover:text-white transition-colors text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            Home
          </Link>
          <span className="text-white/20">/</span>
          <span className="text-white font-medium">Playground</span>
          <span className="ml-auto text-xs bg-purple-500/20 text-purple-300 border border-purple-500/30 px-2 py-0.5 rounded-full">
            Live Network
          </span>
        </div>
      </div>

      {/* Hero */}
      <div className="max-w-5xl mx-auto px-6 pt-12 pb-8">
        <h1 className="text-3xl font-bold text-white mb-2">
          Try Engram
        </h1>
        <p className="text-white/50 text-base">
          Store and search semantic memory on the decentralized network — no install required.
        </p>
      </div>

      {/* Main grid */}
      <div className="max-w-5xl mx-auto px-6 pb-16 grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* ── Ingest panel ─────────────────────────────────────────────────── */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6 flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <Plus className="w-5 h-5 text-purple-400" />
            <h2 className="font-semibold text-white">Store Text</h2>
          </div>

          <p className="text-white/40 text-sm">
            Text is embedded and stored as a permanent content-addressed vector on the network.
          </p>

          {/* Tabs */}
          <div className="flex gap-1 bg-black/30 border border-white/10 rounded-lg p-1">
            {([["text", "Text", FileText], ["url", "URL", Link2], ["file", "File", Upload]] as const).map(([id, label, Icon]) => (
              <button
                key={id}
                onClick={() => setIngestTab(id)}
                className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md transition-colors flex-1 justify-center ${
                  ingestTab === id
                    ? "bg-purple-600 text-white"
                    : "text-white/40 hover:text-white/70"
                }`}
              >
                <Icon className="w-3 h-3" />
                {label}
              </button>
            ))}
          </div>

          {/* Text input */}
          {ingestTab === "text" && (
            <textarea
              className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-white/30 resize-none focus:outline-none focus:border-purple-500/60 transition-colors"
              rows={4}
              placeholder="Paste any text — a concept, a note, a paragraph…"
              value={ingestText}
              onChange={(e) => setIngestText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleIngest(); }}
              maxLength={8192}
            />
          )}

          {/* URL input */}
          {ingestTab === "url" && (
            <div className="flex flex-col gap-2">
              <input
                className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-white/30 focus:outline-none focus:border-purple-500/60 transition-colors"
                placeholder="https://example.com/article"
                value={ingestUrl}
                onChange={(e) => setIngestUrl(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") handleIngest(); }}
              />
              <p className="text-xs text-white/25">Fetches the URL and stores its text content (max 8192 chars)</p>
            </div>
          )}

          {/* File input */}
          {ingestTab === "file" && (
            <div className="flex flex-col gap-2">
              <label className="flex flex-col items-center gap-2 border border-dashed border-white/20 rounded-xl px-4 py-5 cursor-pointer hover:border-purple-500/40 hover:bg-purple-500/5 transition-colors">
                <Upload className="w-5 h-5 text-white/30" />
                <span className="text-sm text-white/40">
                  {ingestFilename ? ingestFilename : "Click to upload a .txt or .md file"}
                </span>
                <input
                  type="file"
                  accept=".txt,.md,.csv,.json"
                  className="sr-only"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    setIngestFilename(file.name);
                    const reader = new FileReader();
                    reader.onload = (ev) => setIngestText((ev.target?.result as string).slice(0, 8192));
                    reader.readAsText(file);
                  }}
                />
              </label>
              {ingestText && (
                <p className="text-xs text-white/30">{ingestText.length} chars loaded from {ingestFilename}</p>
              )}
            </div>
          )}

          <div className="flex items-center justify-between">
            <span className="text-xs text-white/30">
              {ingestTab === "text" ? `${ingestText.length}/8192` : ingestTab === "url" ? "fetches on store" : ingestFilename ? `${ingestText.length}/8192` : ""}
            </span>
            <button
              onClick={handleIngest}
              disabled={ingestLoading || (ingestTab === "text" && !ingestText.trim()) || (ingestTab === "url" && !ingestUrl.trim()) || (ingestTab === "file" && !ingestText.trim())}
              className="flex items-center gap-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
            >
              {ingestLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Plus className="w-4 h-4" />
              )}
              Store
            </button>
          </div>

          {ingestError && (
            <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 text-sm text-red-400">
              <XCircle className="w-4 h-4 mt-0.5 shrink-0" />
              {ingestError}
            </div>
          )}

          {/* History */}
          {ingestHistory.length > 0 && (
            <div className="flex flex-col gap-2 mt-1">
              <span className="text-xs text-white/30 uppercase tracking-wider">Stored this session</span>
              {ingestHistory.map((item) => (
                <div
                  key={item.cid}
                  className="bg-black/30 border border-white/10 rounded-lg px-3 py-2 group"
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="font-mono text-xs text-purple-300 truncate">
                      {item.cid.slice(0, 8)}…{item.cid.slice(-6)}
                    </span>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => copyCid(item.cid)}
                        className="text-white/40 hover:text-white p-1 rounded"
                        title="Copy CID"
                      >
                        {copiedCid === item.cid ? (
                          <Check className="w-3 h-3 text-green-400" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                      </button>
                      <button
                        onClick={() => prefillQuery(item.text)}
                        className="text-white/40 hover:text-white p-1 rounded text-xs"
                        title="Search for similar"
                      >
                        <Search className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                  <p className="text-white/50 text-xs truncate">{item.text}</p>
                </div>
              ))}
            </div>
          )}

          {/* SDK snippet */}
          {lastIngestText && (() => {
            const escaped = lastIngestText.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
            const code = `from engram.sdk import EngramClient\n\nclient = EngramClient("http://your-miner:8091")\ncid = client.ingest("${escaped}")\nprint(cid)  # v1::...`;
            return (
              <div className="mt-1 bg-black/50 border border-white/10 rounded-xl overflow-hidden">
                <div className="flex items-center justify-between px-3 py-2 border-b border-white/10">
                  <div className="flex items-center gap-1.5 text-xs text-white/40">
                    <Code className="w-3.5 h-3.5" />
                    SDK equivalent
                  </div>
                  <button
                    onClick={() => copyCode("ingest", code)}
                    className="flex items-center gap-1 text-xs text-white/40 hover:text-white transition-colors"
                  >
                    {copiedCode === "ingest" ? (
                      <><Check className="w-3 h-3 text-green-400" /><span className="text-green-400">Copied</span></>
                    ) : (
                      <><Copy className="w-3 h-3" />Copy</>
                    )}
                  </button>
                </div>
                <pre className="px-3 py-3 text-xs text-purple-200 font-mono overflow-x-auto leading-relaxed">{code}</pre>
              </div>
            );
          })()}
        </div>

        {/* ── Query panel ──────────────────────────────────────────────────── */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6 flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <Search className="w-5 h-5 text-purple-400" />
            <h2 className="font-semibold text-white">Semantic Search</h2>
          </div>

          <p className="text-white/40 text-sm">
            Search by meaning — returns the most semantically similar vectors across all miners.
          </p>

          <div className="flex gap-2">
            <input
              className="flex-1 bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-white/30 focus:outline-none focus:border-purple-500/60 transition-colors"
              placeholder="Ask anything…"
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleQuery(); }}
            />
            <button
              onClick={handleQuery}
              disabled={!queryText.trim() || queryLoading}
              className="flex items-center gap-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-3 rounded-xl transition-colors"
            >
              {queryLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Search className="w-4 h-4" />
              )}
            </button>
          </div>

          {queryError && (
            <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 text-sm text-red-400">
              <XCircle className="w-4 h-4 mt-0.5 shrink-0" />
              {queryError}
            </div>
          )}

          {queryResults !== null && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-white/30 uppercase tracking-wider">
                  {queryResults.length} result{queryResults.length !== 1 ? "s" : ""}
                </span>
                {queryLatency !== null && (
                  <span className="text-xs text-white/30">{queryLatency}ms</span>
                )}
              </div>

              {queryResults.length === 0 ? (
                <div className="text-center py-8 text-white/30 text-sm">
                  No results found. Try storing some text first.
                </div>
              ) : (
                queryResults.map((r, i) => {
                  const text = typeof r.metadata?.text === "string" ? r.metadata.text : null;
                  return (
                    <div
                      key={r.cid + i}
                      className="bg-black/30 border border-white/10 rounded-lg px-3 py-2.5"
                    >
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <a
                          href={`/cid/${encodeURIComponent(r.cid)}`}
                          className="font-mono text-xs text-purple-300 hover:text-purple-200 truncate underline-offset-2 hover:underline"
                          title="View CID details"
                        >
                          {r.cid.slice(0, 8)}…{r.cid.slice(-6)}
                        </a>
                        <div className="flex items-center gap-2">
                          <span className={`text-xs font-medium ${
                            r.score > 0.85 ? "text-green-400" :
                            r.score > 0.65 ? "text-yellow-400" : "text-white/40"
                          }`}>
                            {(r.score * 100).toFixed(1)}%
                          </span>
                          <button
                            onClick={() => copyCid(r.cid)}
                            className="text-white/30 hover:text-white transition-colors"
                            title="Copy CID"
                          >
                            {copiedCid === r.cid ? (
                              <Check className="w-3 h-3 text-green-400" />
                            ) : (
                              <Copy className="w-3 h-3" />
                            )}
                          </button>
                        </div>
                      </div>
                      {text && (
                        <p className="text-white/60 text-xs leading-relaxed mt-1 line-clamp-2">{text}</p>
                      )}
                      {!text && Object.keys(r.metadata).length > 0 && (
                        <p className="text-white/25 text-xs font-mono truncate mt-1">
                          {JSON.stringify(r.metadata)}
                        </p>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}

          {/* Idle state hint */}
          {queryResults === null && !queryLoading && !queryError && (
            <div className="flex-1 flex items-center justify-center py-8 text-center">
              <div>
                <Search className="w-8 h-8 text-white/10 mx-auto mb-3" />
                <p className="text-white/20 text-sm">
                  Results appear here.<br />
                  Try: <button
                    onClick={() => { setQueryText("how does attention work?"); }}
                    className="text-purple-400 hover:text-purple-300 underline underline-offset-2"
                  >
                    how does attention work?
                  </button>
                </p>
              </div>
            </div>
          )}

          {/* SDK snippet */}
          {lastQueryText && (() => {
            const escaped = lastQueryText.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
            const code = `from engram.sdk import EngramClient\n\nclient = EngramClient("http://your-miner:8091")\nresults = client.query("${escaped}", top_k=5)\nfor r in results:\n    print(r["score"], r["cid"])`;
            return (
              <div className="mt-1 bg-black/50 border border-white/10 rounded-xl overflow-hidden">
                <div className="flex items-center justify-between px-3 py-2 border-b border-white/10">
                  <div className="flex items-center gap-1.5 text-xs text-white/40">
                    <Code className="w-3.5 h-3.5" />
                    SDK equivalent
                  </div>
                  <button
                    onClick={() => copyCode("query", code)}
                    className="flex items-center gap-1 text-xs text-white/40 hover:text-white transition-colors"
                  >
                    {copiedCode === "query" ? (
                      <><Check className="w-3 h-3 text-green-400" /><span className="text-green-400">Copied</span></>
                    ) : (
                      <><Copy className="w-3 h-3" />Copy</>
                    )}
                  </button>
                </div>
                <pre className="px-3 py-3 text-xs text-purple-200 font-mono overflow-x-auto leading-relaxed">{code}</pre>
              </div>
            );
          })()}
        </div>

      </div>

      {/* Footer hint */}
      <div className="max-w-5xl mx-auto px-6 pb-12 text-center">
        <p className="text-white/20 text-sm">
          Every CID is permanent and content-addressed — the same text always maps to the same CID, regardless of which miner stores it.
        </p>
        <div className="flex items-center justify-center gap-6 mt-4 text-xs text-white/30">
          <Link href="/docs" className="hover:text-white/60 transition-colors">Docs</Link>
          <Link href="/dashboard" className="hover:text-white/60 transition-colors">Dashboard</Link>
          <a href="https://github.com/Dipraise1/-Engram-" target="_blank" rel="noopener noreferrer" className="hover:text-white/60 transition-colors">GitHub</a>
        </div>
      </div>
    </div>
  );
}
