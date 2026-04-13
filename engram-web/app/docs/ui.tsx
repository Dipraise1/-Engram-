"use client";

import { useState } from "react";
import Link from "next/link";
import { Copy, Check, ChevronLeft, ChevronRight } from "lucide-react";

// ── Copy button ───────────────────────────────────────────────────────────────

export function CopyButton({ text }: { text: string }) {
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

function colorizeLine(line: string, lang: string): React.ReactNode {
  if (lang === "bash") {
    if (line.trim().startsWith("#")) return <span className="text-[#5c6370]">{line}</span>;
    const parts = line.split(" ");
    if (["pip", "engram", "python", "git", "uvicorn", "btcli", "curl", "cargo"].includes(parts[0])) {
      return (
        <>
          <span className="text-[#61afef]">{parts[0]}</span>
          {parts[1] && <span className="text-[#e06c75]"> {parts[1]}</span>}
          {parts.length > 2 && <span className="text-white/45"> {parts.slice(2).join(" ")}</span>}
        </>
      );
    }
    if (line.includes("=") && !line.includes("==")) return <span className="text-[#d19a66]">{line}</span>;
    return <span className="text-white/60">{line}</span>;
  }
  if (lang === "python") {
    if (line.trim().startsWith("#")) return <span className="text-[#5c6370]">{line}</span>;
    const styled = line
      .replace(/(from|import|def|class|return|for|in|if|not|and|or|True|False|None|async|await|with|as|try|except|print|raise)\b/g, "§kw§$1§/kw§")
      .replace(/(".*?"|'.*?')/g, "§str§$1§/str§")
      .replace(/\b(\d+\.?\d*)\b/g, "§num§$1§/num§")
      .replace(/([a-zA-Z_]\w*)\s*(?=\()/g, "§fn§$1§/fn§")
      .replace(/#.*/g, "§cmt§$&§/cmt§");
    return (
      <span dangerouslySetInnerHTML={{
        __html: styled
          .replace(/§kw§(.*?)§\/kw§/g, '<span style="color:#c678dd">$1</span>')
          .replace(/§str§(.*?)§\/str§/g, '<span style="color:#98c379">$1</span>')
          .replace(/§num§(.*?)§\/num§/g, '<span style="color:#d19a66">$1</span>')
          .replace(/§fn§(.*?)§\/fn§/g, '<span style="color:#61afef">$1</span>')
          .replace(/§cmt§(.*?)§\/cmt§/g, '<span style="color:#5c6370">$1</span>'),
      }} />
    );
  }
  return <span className="text-white/60">{line}</span>;
}

export function Code({ children, lang = "bash", title }: { children: string; lang?: string; title?: string }) {
  const raw = children.trim();
  const lines = raw.split("\n");
  return (
    <div className="rounded-xl overflow-hidden border border-[#1e1525] my-5">
      <div className="flex items-center justify-between px-4 py-2 bg-[#0d0b11] border-b border-[#1e1525]">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#ff5f57]" />
          <span className="w-2 h-2 rounded-full bg-[#febc2e]" />
          <span className="w-2 h-2 rounded-full bg-[#28c840]" />
          {title
            ? <span className="ml-2 text-[11px] font-mono text-white/25">{title}</span>
            : <span className="ml-2 text-[10px] font-mono text-white/20 uppercase tracking-wider">{lang}</span>
          }
        </div>
        <CopyButton text={raw} />
      </div>
      <div className="bg-[#0a0810] px-5 py-4 overflow-x-auto">
        <pre className="text-[12.5px] font-mono leading-[1.85]">
          {lines.map((line, i) => (
            <div key={i}>{colorizeLine(line, lang)}</div>
          ))}
        </pre>
      </div>
    </div>
  );
}

// ── Inline code ───────────────────────────────────────────────────────────────

export function Ic({ children }: { children: string }) {
  return (
    <code className="text-[#e040fb] bg-[#1a0d22] px-1.5 py-0.5 rounded text-[12px] font-mono">
      {children}
    </code>
  );
}

// ── Typography ────────────────────────────────────────────────────────────────

export function H1({ children }: { children: React.ReactNode }) {
  return (
    <h1 className="font-display font-light text-white mb-3 leading-tight"
      style={{ fontSize: "clamp(28px, 3.5vw, 44px)", letterSpacing: "-0.01em" }}>
      {children}
    </h1>
  );
}

export function H2({ id, children }: { id?: string; children: React.ReactNode }) {
  return (
    <h2 id={id} className="font-display font-light text-white mt-12 mb-3 scroll-mt-20"
      style={{ fontSize: "clamp(20px, 2.5vw, 28px)", letterSpacing: "-0.01em" }}>
      {children}
    </h2>
  );
}

export function H3({ id, children }: { id?: string; children: React.ReactNode }) {
  return (
    <h3 id={id} className="text-white font-semibold text-[16px] mt-8 mb-2 scroll-mt-20 font-sans">
      {children}
    </h3>
  );
}

export function P({ children }: { children: React.ReactNode }) {
  return <p className="text-[15px] text-[#c4b5d4] leading-relaxed mb-4">{children}</p>;
}

export function Lead({ children }: { children: React.ReactNode }) {
  return <p className="text-[17px] text-[#8b7a9e] leading-relaxed mb-6 font-light">{children}</p>;
}

// ── Table ─────────────────────────────────────────────────────────────────────

export function Table({ headers, rows }: { headers: string[]; rows: (string | React.ReactNode)[][] }) {
  return (
    <div className="overflow-x-auto my-5 rounded-xl border border-[#1e1525]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#1e1525] bg-[#0e0b12]">
            {headers.map((h) => (
              <th key={h} className="px-4 py-2.5 text-left text-[10px] uppercase tracking-widest font-semibold text-[#6b5a7e]">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-[#1a1022] last:border-0 hover:bg-[#0a0810]/40">
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-2.5 text-[#c4b5d4] text-[13px]">
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

export function Note({ children, type = "info" }: { children: React.ReactNode; type?: "info" | "warn" | "tip" }) {
  const colors = {
    info: "border-[#7c3aed] bg-[#7c3aed]/5",
    warn: "border-[#f59e0b] bg-[#f59e0b]/5",
    tip:  "border-[#34d399] bg-[#34d399]/5",
  };
  const labels = { info: "Note", warn: "Warning", tip: "Tip" };
  const labelColors = { info: "text-[#a78bfa]", warn: "text-[#fbbf24]", tip: "text-[#34d399]" };
  return (
    <div className={`border-l-2 ${colors[type]} rounded-r-xl px-5 py-4 my-5`}>
      <div className={`text-[11px] font-mono uppercase tracking-widest font-bold mb-1.5 ${labelColors[type]}`}>
        {labels[type]}
      </div>
      <div className="text-[14px] text-[#c4b5d4] leading-relaxed">{children}</div>
    </div>
  );
}

// ── Step list (array style) ───────────────────────────────────────────────────

export function Steps({ steps, children }: {
  steps?: { title: string; desc?: string; code?: string; lang?: string }[];
  children?: React.ReactNode;
}) {
  return (
    <div className="relative my-6">
      <div className="absolute left-[19px] top-6 bottom-6 w-px bg-[#1e1525]" />
      <div className="space-y-6">
        {steps
          ? steps.map((step, i) => (
              <div key={i} className="flex gap-4">
                <div className="flex-shrink-0 w-10 h-10 rounded-full border border-[#1e1525] bg-[#0e0b12] flex items-center justify-center z-10">
                  <span className="text-[12px] font-mono text-[#e040fb]">{String(i + 1).padStart(2, "0")}</span>
                </div>
                <div className="flex-1 pt-2 pb-2">
                  <div className="text-[15px] font-semibold text-white mb-1">{step.title}</div>
                  {step.desc && <p className="text-[13px] text-[#6b5a7e] mb-0">{step.desc}</p>}
                  {step.code && <Code lang={step.lang ?? "bash"}>{step.code}</Code>}
                </div>
              </div>
            ))
          : children}
      </div>
    </div>
  );
}

// ── Individual step (for JSX children style) ──────────────────────────────────

export function Step({ n, title, children }: { n: number; title: string; children?: React.ReactNode }) {
  return (
    <div className="flex gap-4">
      <div className="flex-shrink-0 w-10 h-10 rounded-full border border-[#1e1525] bg-[#0e0b12] flex items-center justify-center z-10">
        <span className="text-[12px] font-mono text-[#e040fb]">{String(n).padStart(2, "0")}</span>
      </div>
      <div className="flex-1 pt-2 pb-2">
        <div className="text-[15px] font-semibold text-white mb-1">{title}</div>
        {children && <div className="text-[13px] text-[#6b5a7e]">{children}</div>}
      </div>
    </div>
  );
}

// ── CodeBlock alias (same as Code) ────────────────────────────────────────────

export function CodeBlock({ code, lang, title }: { code: string; lang?: string; title?: string }) {
  return <Code lang={lang} title={title}>{code}</Code>;
}

// ── Page shell ────────────────────────────────────────────────────────────────

export function DocPage({
  children,
  prev,
  next,
  toc,
}: {
  children: React.ReactNode;
  prev?: { href: string; label: string };
  next?: { href: string; label: string };
  toc?: { id: string; label: string; depth?: number }[];
}) {
  return (
    <div className="flex gap-8 max-w-5xl mx-auto">
      {/* Content */}
      <article className="flex-1 min-w-0 px-8 py-10">
        {children}

        {/* Prev / Next */}
        {(prev || next) && (
          <div className="flex items-center justify-between mt-16 pt-8 border-t border-[#1e1525]">
            {prev ? (
              <Link href={prev.href} className="flex items-center gap-2 text-[13px] text-[#6b5a7e] hover:text-[#c4b5d4] transition-colors group">
                <ChevronLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
                <div>
                  <div className="text-[10px] uppercase tracking-widest mb-0.5 text-[#3a2845]">Previous</div>
                  {prev.label}
                </div>
              </Link>
            ) : <span />}
            {next ? (
              <Link href={next.href} className="flex items-center gap-2 text-[13px] text-[#6b5a7e] hover:text-[#c4b5d4] transition-colors text-right group">
                <div>
                  <div className="text-[10px] uppercase tracking-widest mb-0.5 text-[#3a2845]">Next</div>
                  {next.label}
                </div>
                <ChevronRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
              </Link>
            ) : <span />}
          </div>
        )}

        <div className="mt-8 pb-16 text-[11px] font-mono text-[#3a2845] flex items-center justify-between">
          <span>engram docs · v0.1</span>
          <a href="https://github.com/Dipraise1/-Engram-" target="_blank" rel="noopener noreferrer"
            className="hover:text-[#6b5a7e] transition-colors">
            edit on github →
          </a>
        </div>
      </article>

      {/* Right TOC */}
      {toc && toc.length > 0 && (
        <aside className="hidden xl:block w-48 flex-shrink-0 pt-10">
          <div className="sticky top-20">
            <div className="text-[10px] uppercase tracking-widest font-semibold text-[#3a2845] mb-3 px-1">
              On this page
            </div>
            <nav className="space-y-0.5">
              {toc.map((item) => (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  className={`block text-[12px] text-[#6b5a7e] hover:text-[#c4b5d4] transition-colors py-0.5 ${
                    item.depth === 3 ? "pl-4" : "pl-1"
                  }`}
                >
                  {item.label}
                </a>
              ))}
            </nav>
          </div>
        </aside>
      )}
    </div>
  );
}
