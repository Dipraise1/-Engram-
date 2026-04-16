"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Database, Copy, Check, AlertCircle, Loader2, ExternalLink, ImageIcon, FileText } from "lucide-react";

interface CIDRecord {
  cid: string;
  metadata: Record<string, string>;
}

export default function CIDPage() {
  const params = useParams();
  const cid = typeof params.id === "string" ? params.id : Array.isArray(params.id) ? params.id[0] : "";

  const [record, setRecord] = useState<CIDRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [imgError, setImgError] = useState(false);

  useEffect(() => {
    if (!cid) return;
    setLoading(true);
    fetch(`/api/subnet/cid/${encodeURIComponent(cid)}`)
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Not found");
        setRecord(data);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [cid]);

  function copyCid() {
    navigator.clipboard.writeText(cid).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  const meta = record?.metadata ?? {};
  const type = meta.type ?? null;
  const isImage = type === "image";
  const isPdf = type === "pdf";

  const text = meta.text ?? null;
  const role = meta.role ?? null;
  const session = meta.session ?? null;
  const ts = meta.ts ? parseInt(meta.ts) : null;
  const arweave_tx_id = meta.arweave_tx_id ?? null;
  const arweave_url = meta.arweave_url ?? (arweave_tx_id ? `https://arweave.net/${arweave_tx_id}` : null);
  const content_cid = meta.content_cid ?? null;
  const thumbnail = meta.thumbnail ?? null;
  const source = meta.source ?? null;
  const pages = meta.pages ?? null;

  const hiddenKeys = new Set(["text", "role", "session", "ts", "source", "type",
    "arweave_tx_id", "arweave_url", "content_cid", "thumbnail", "pages"]);
  const otherMeta = record
    ? Object.entries(meta).filter(([k]) => !hiddenKeys.has(k))
    : [];

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Header */}
      <div className="border-b border-white/10 px-6 py-4 sticky top-0 bg-[#0a0a0f]/95 backdrop-blur z-10">
        <div className="max-w-3xl mx-auto flex items-center gap-3">
          <Link href="/" className="flex items-center gap-1.5 text-white/40 hover:text-white transition-colors text-sm">
            <ArrowLeft className="w-4 h-4" />
            Home
          </Link>
          <span className="text-white/20">/</span>
          <span className="text-white/40 text-sm">CID Lookup</span>
          <div className="ml-auto flex items-center gap-2">
            {isImage && (
              <span className="text-xs bg-blue-500/20 text-blue-300 border border-blue-500/30 px-2 py-0.5 rounded-full flex items-center gap-1">
                <ImageIcon className="w-3 h-3" /> Image
              </span>
            )}
            {isPdf && (
              <span className="text-xs bg-orange-500/20 text-orange-300 border border-orange-500/30 px-2 py-0.5 rounded-full flex items-center gap-1">
                <FileText className="w-3 h-3" /> PDF
              </span>
            )}
            <span className="text-xs bg-purple-500/20 text-purple-300 border border-purple-500/30 px-2 py-0.5 rounded-full">
              Content-Addressed
            </span>
          </div>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-6 py-12">

        {/* CID display */}
        <div className="mb-8">
          <p className="text-xs text-white/30 uppercase tracking-wider font-mono mb-2">Engram CID</p>
          <div className="flex items-center gap-3 bg-white/5 border border-white/10 rounded-xl px-4 py-3">
            <Database className="w-4 h-4 text-purple-400 shrink-0" />
            <span className="font-mono text-sm text-purple-200 flex-1 break-all">{cid}</span>
            <button onClick={copyCid} className="shrink-0 text-white/30 hover:text-white transition-colors p-1" title="Copy CID">
              {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-xs text-white/25 mt-2 font-mono">
            hash(embedding + metadata) — semantic identifier for this stored memory
          </p>
        </div>

        {loading && (
          <div className="flex items-center gap-3 py-16 justify-center text-white/30">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm">Looking up on miner…</span>
          </div>
        )}

        {error && !loading && (
          <div className="flex items-start gap-3 bg-red-500/10 border border-red-500/20 rounded-xl px-5 py-4">
            <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm text-red-300 font-medium mb-1">{error}</p>
              <p className="text-xs text-red-400/60">
                This CID may not be stored on the connected miner, or held by a different peer on the network.
              </p>
            </div>
          </div>
        )}

        {record && !loading && (
          <div className="flex flex-col gap-6">

            {/* ── Image preview ───────────────────────────────────────────── */}
            {isImage && (arweave_url || thumbnail) && (
              <div>
                <div className="flex items-center justify-between mb-3">
                  <p className="text-xs text-white/30 uppercase tracking-wider font-mono">Original Image</p>
                  {arweave_url && (
                    <a
                      href={arweave_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 text-xs text-green-400 hover:text-green-300 transition-colors"
                    >
                      <ExternalLink className="w-3 h-3" />
                      Full res on Arweave
                    </a>
                  )}
                </div>
                <div className="bg-black/40 border border-white/10 rounded-xl overflow-hidden flex items-center justify-center min-h-[200px]">
                  {!imgError ? (
                    <img
                      src={arweave_url ?? thumbnail!}
                      alt={source ?? "stored image"}
                      className="max-w-full max-h-[480px] object-contain"
                      onError={() => {
                        // Arweave may take a few mins to propagate — fall back to thumbnail
                        if (arweave_url && thumbnail) setImgError(true);
                      }}
                    />
                  ) : (
                    <img
                      src={thumbnail!}
                      alt={source ?? "stored image (thumbnail)"}
                      className="max-w-full max-h-[480px] object-contain opacity-70"
                    />
                  )}
                </div>
                {imgError && (
                  <p className="text-xs text-white/30 mt-2 text-center">
                    Showing thumbnail — Arweave propagation can take a few minutes.{" "}
                    <a href={arweave_url!} target="_blank" rel="noopener noreferrer" className="text-green-400 hover:underline">
                      Check full res
                    </a>
                  </p>
                )}
              </div>
            )}

            {/* ── PDF link ─────────────────────────────────────────────────── */}
            {isPdf && arweave_url && (
              <div>
                <p className="text-xs text-white/30 uppercase tracking-wider font-mono mb-3">Original File</p>
                <a
                  href={arweave_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 bg-orange-500/10 border border-orange-500/20 rounded-xl px-5 py-4 hover:bg-orange-500/15 transition-colors"
                >
                  <FileText className="w-5 h-5 text-orange-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-orange-300 font-medium truncate">{source ?? "document.pdf"}</p>
                    <p className="text-xs text-orange-400/60">{pages ? `${pages} pages · ` : ""}Permanently stored on Arweave</p>
                  </div>
                  <ExternalLink className="w-4 h-4 text-orange-400/60 shrink-0" />
                </a>
              </div>
            )}

            {/* ── Stored description / text ─────────────────────────────── */}
            {text && (
              <div>
                <p className="text-xs text-white/30 uppercase tracking-wider font-mono mb-3">
                  {isImage ? "AI Description" : "Stored Content"}
                </p>
                <div className="bg-white/5 border border-white/10 rounded-xl px-5 py-4">
                  <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{text}</p>
                </div>
              </div>
            )}

            {/* ── Storage proof ─────────────────────────────────────────── */}
            <div>
              <p className="text-xs text-white/30 uppercase tracking-wider font-mono mb-3">Storage</p>
              <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden divide-y divide-white/[0.06]">

                {content_cid && (
                  <div className="flex items-start justify-between px-5 py-3 gap-4">
                    <span className="text-xs font-mono text-white/40 shrink-0">content CID</span>
                    <span className="text-xs font-mono text-white/60 break-all text-right">{content_cid}</span>
                  </div>
                )}

                {arweave_tx_id && (
                  <div className="flex items-center justify-between px-5 py-3 gap-4">
                    <span className="text-xs font-mono text-white/40 shrink-0">arweave tx</span>
                    <a
                      href={`https://viewblock.io/arweave/tx/${arweave_tx_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs font-mono text-green-400 hover:text-green-300 truncate flex items-center gap-1"
                    >
                      {arweave_tx_id.slice(0, 12)}…{arweave_tx_id.slice(-8)}
                      <ExternalLink className="w-3 h-3 shrink-0" />
                    </a>
                  </div>
                )}

                {source && (
                  <div className="flex items-center justify-between px-5 py-3">
                    <span className="text-xs font-mono text-white/40">filename</span>
                    <span className="text-xs font-mono text-white/60 truncate max-w-[240px]">{source}</span>
                  </div>
                )}

                {role && (
                  <div className="flex items-center justify-between px-5 py-3">
                    <span className="text-xs font-mono text-white/40">role</span>
                    <span className={`text-xs font-mono px-2 py-0.5 rounded-full border ${
                      role === "assistant"
                        ? "text-violet-300 border-violet-500/30 bg-violet-500/10"
                        : "text-fuchsia-300 border-fuchsia-500/30 bg-fuchsia-500/10"
                    }`}>{role}</span>
                  </div>
                )}

                {ts && (
                  <div className="flex items-center justify-between px-5 py-3">
                    <span className="text-xs font-mono text-white/40">stored at</span>
                    <span className="text-xs font-mono text-white/60">{new Date(ts).toLocaleString()}</span>
                  </div>
                )}

                {otherMeta.map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between px-5 py-3">
                    <span className="text-xs font-mono text-white/40">{k}</span>
                    <span className="text-xs font-mono text-white/60 truncate max-w-[240px]">{v}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Proof note */}
            <div className="flex items-start gap-3 bg-white/[0.03] border border-white/[0.06] rounded-xl px-5 py-4">
              <ExternalLink className="w-4 h-4 text-white/20 mt-0.5 shrink-0" />
              <p className="text-xs text-white/30 leading-relaxed">
                The Engram CID is derived from a hash of the vector embedding — the semantic fingerprint of this content.
                {arweave_tx_id
                  ? " The original file is permanently stored on Arweave — verifiable by anyone, forever."
                  : " Validators continuously challenge miners to prove they hold each CID."}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
