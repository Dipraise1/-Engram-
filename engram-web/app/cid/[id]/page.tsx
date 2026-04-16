"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Database, Copy, Check, AlertCircle, Loader2, ExternalLink } from "lucide-react";

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

  const text = record?.metadata?.text ?? null;
  const role = record?.metadata?.role ?? null;
  const session = record?.metadata?.session ?? null;
  const ts = record?.metadata?.ts ? parseInt(record.metadata.ts) : null;

  const otherMeta = record
    ? Object.entries(record.metadata).filter(([k]) => !["text", "role", "session", "ts", "source"].includes(k))
    : [];

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Header */}
      <div className="border-b border-white/10 px-6 py-4 sticky top-0 bg-[#0a0a0f]/95 backdrop-blur z-10">
        <div className="max-w-3xl mx-auto flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-white/40 hover:text-white transition-colors text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            Home
          </Link>
          <span className="text-white/20">/</span>
          <span className="text-white/40 text-sm">CID Lookup</span>
          <span className="ml-auto text-xs bg-purple-500/20 text-purple-300 border border-purple-500/30 px-2 py-0.5 rounded-full">
            Content-Addressed
          </span>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-6 py-12">

        {/* CID display */}
        <div className="mb-8">
          <p className="text-xs text-white/30 uppercase tracking-wider font-mono mb-2">Content Identifier</p>
          <div className="flex items-center gap-3 bg-white/5 border border-white/10 rounded-xl px-4 py-3">
            <Database className="w-4 h-4 text-purple-400 shrink-0" />
            <span className="font-mono text-sm text-purple-200 flex-1 break-all">{cid}</span>
            <button
              onClick={copyCid}
              className="shrink-0 text-white/30 hover:text-white transition-colors p-1"
              title="Copy CID"
            >
              {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-xs text-white/25 mt-2 font-mono">
            SHA-256 content hash — the same text always maps to the same CID
          </p>
        </div>

        {/* Content */}
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
                This CID may not be stored on the connected miner, or it may be held by a different peer on the network.
              </p>
            </div>
          </div>
        )}

        {record && !loading && (
          <div className="flex flex-col gap-6">

            {/* Stored text */}
            {text && (
              <div>
                <p className="text-xs text-white/30 uppercase tracking-wider font-mono mb-3">Stored Content</p>
                <div className="bg-white/5 border border-white/10 rounded-xl px-5 py-4">
                  <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{text}</p>
                </div>
              </div>
            )}

            {/* Metadata */}
            <div>
              <p className="text-xs text-white/30 uppercase tracking-wider font-mono mb-3">Metadata</p>
              <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden divide-y divide-white/[0.06]">

                {role && (
                  <div className="flex items-center justify-between px-5 py-3">
                    <span className="text-xs font-mono text-white/40">role</span>
                    <span className={`text-xs font-mono px-2 py-0.5 rounded-full border ${
                      role === "assistant"
                        ? "text-violet-300 border-violet-500/30 bg-violet-500/10"
                        : "text-fuchsia-300 border-fuchsia-500/30 bg-fuchsia-500/10"
                    }`}>
                      {role}
                    </span>
                  </div>
                )}

                {ts && (
                  <div className="flex items-center justify-between px-5 py-3">
                    <span className="text-xs font-mono text-white/40">stored at</span>
                    <span className="text-xs font-mono text-white/60">
                      {new Date(ts).toLocaleString()}
                    </span>
                  </div>
                )}

                {session && (
                  <div className="flex items-center justify-between px-5 py-3">
                    <span className="text-xs font-mono text-white/40">session</span>
                    <span className="text-xs font-mono text-white/40 truncate max-w-[200px]">{session}</span>
                  </div>
                )}

                {record.metadata.source && (
                  <div className="flex items-center justify-between px-5 py-3">
                    <span className="text-xs font-mono text-white/40">source</span>
                    <span className="text-xs font-mono text-white/60">{record.metadata.source}</span>
                  </div>
                )}

                {otherMeta.map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between px-5 py-3">
                    <span className="text-xs font-mono text-white/40">{k}</span>
                    <span className="text-xs font-mono text-white/60 truncate max-w-[240px]">{v}</span>
                  </div>
                ))}

                {!text && !role && !ts && !session && otherMeta.length === 0 && (
                  <div className="px-5 py-4 text-xs text-white/30 font-mono">no metadata stored</div>
                )}
              </div>
            </div>

            {/* Proof note */}
            <div className="flex items-start gap-3 bg-white/[0.03] border border-white/[0.06] rounded-xl px-5 py-4">
              <ExternalLink className="w-4 h-4 text-white/20 mt-0.5 shrink-0" />
              <p className="text-xs text-white/30 leading-relaxed">
                This CID is derived from a SHA-256 hash of the content — the same text will always
                produce the same identifier, regardless of which miner stores it. Validators
                continuously challenge miners to prove they hold each CID.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
