"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Brain,
  Send,
  Loader2,
  Database,
  Sparkles,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Zap,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────────

interface Memory {
  cid: string;
  score: number;
  role?: string;
  text?: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  retrievedMemories?: Memory[];
  storedCid?: string | null;
  userCid?: string | null;
  isStreaming?: boolean;
}

// ── Session ID (stable per browser tab) ───────────────────────────────────────

function getSessionId(): string {
  if (typeof window === "undefined") return "ssr";
  let id = sessionStorage.getItem("engram_session");
  if (!id) {
    id = `s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}`;
    sessionStorage.setItem("engram_session", id);
  }
  return id;
}

// ── Memory pill ────────────────────────────────────────────────────────────────

function MemoryPill({ memory }: { memory: Memory }) {
  const label = memory.text
    ? memory.text.slice(0, 60) + (memory.text.length > 60 ? "…" : "")
    : memory.cid.slice(0, 8) + "…" + memory.cid.slice(-6);

  const roleColor =
    memory.role === "assistant"
      ? "border-violet-500/30 text-violet-300 bg-violet-500/5"
      : "border-fuchsia-500/30 text-fuchsia-300 bg-fuchsia-500/5";

  const scorePct = Math.min(100, Math.round((memory.score ?? 0) * 100));

  return (
    <div
      className={`flex items-start gap-2 rounded-lg border px-2.5 py-1.5 text-xs ${roleColor}`}
      title={`CID: ${memory.cid}\nScore: ${scorePct}%`}
    >
      <Database className="w-3 h-3 mt-0.5 shrink-0 opacity-60" />
      <span className="leading-snug">{label}</span>
      <span className="ml-auto shrink-0 opacity-50 font-mono">{scorePct}%</span>
    </div>
  );
}

// ── Message bubble ─────────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: Message }) {
  const [showMem, setShowMem] = useState(false);
  const isUser = msg.role === "user";

  return (
    <div className={`flex flex-col gap-1.5 ${isUser ? "items-end" : "items-start"}`}>
      {/* Memory context (assistant only, shown above bubble) */}
      {!isUser && msg.retrievedMemories && msg.retrievedMemories.length > 0 && (
        <div className="w-full max-w-[85%]">
          <button
            onClick={() => setShowMem((v) => !v)}
            className="flex items-center gap-1.5 text-[11px] text-white/30 hover:text-white/60 transition-colors mb-1"
          >
            <Brain className="w-3 h-3" />
            {msg.retrievedMemories.length} memor{msg.retrievedMemories.length === 1 ? "y" : "ies"} recalled
            {showMem ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
          {showMem && (
            <div className="flex flex-col gap-1 mb-2">
              {msg.retrievedMemories.map((m) => (
                <MemoryPill key={m.cid} memory={m} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Bubble */}
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
          isUser
            ? "bg-fuchsia-600/80 text-white rounded-br-sm"
            : "bg-white/8 border border-white/10 text-slate-100 rounded-bl-sm"
        }`}
      >
        {msg.content}
        {msg.isStreaming && (
          <span className="inline-block w-1.5 h-4 bg-fuchsia-400 ml-1 animate-pulse rounded-sm" />
        )}
      </div>

      {/* Storage indicator */}
      {!isUser && msg.storedCid && (
        <div className="flex items-center gap-1 text-[11px] text-white/25">
          <Zap className="w-2.5 h-2.5" />
          stored on Engram ·{" "}
          <span className="font-mono">
            {msg.storedCid.slice(0, 8)}…{msg.storedCid.slice(-6)}
          </span>
        </div>
      )}
      {isUser && msg.userCid && (
        <div className="flex items-center gap-1 text-[11px] text-white/25">
          <Zap className="w-2.5 h-2.5" />
          <span className="font-mono">
            {msg.userCid.slice(0, 8)}…{msg.userCid.slice(-6)}
          </span>
        </div>
      )}
    </div>
  );
}

// ── Typing indicator ───────────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div className="flex items-start gap-3">
      <div className="flex items-center gap-1 bg-white/8 border border-white/10 rounded-2xl rounded-bl-sm px-4 py-3">
        <span className="w-1.5 h-1.5 bg-white/40 rounded-full animate-bounce [animation-delay:-0.3s]" />
        <span className="w-1.5 h-1.5 bg-white/40 rounded-full animate-bounce [animation-delay:-0.15s]" />
        <span className="w-1.5 h-1.5 bg-white/40 rounded-full animate-bounce" />
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function MemoryPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [noApiKey, setNoApiKey] = useState(false);

  const sessionId = useRef<string>("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    sessionId.current = getSessionId();
  }, []);

  // Auto-scroll on new content
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
  }, [input]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setError(null);

    const userMsg: Message = {
      id: `u_${Date.now()}`,
      role: "user",
      content: text,
    };

    const aiMsgId = `a_${Date.now()}`;
    const aiMsg: Message = {
      id: aiMsgId,
      role: "assistant",
      content: "",
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, aiMsg]);
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, sessionId: sessionId.current }),
      });

      if (res.status === 503) {
        const data = await res.json();
        if (data.error?.includes("XAI_API_KEY")) {
          setNoApiKey(true);
        }
        setError(data.error ?? "Service unavailable.");
        setMessages((prev) => prev.filter((m) => m.id !== aiMsgId));
        setLoading(false);
        return;
      }

      if (!res.ok || !res.body) {
        throw new Error("Chat request failed");
      }

      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += dec.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (raw === "[DONE]") continue;

          try {
            const event = JSON.parse(raw);

            if (event.type === "memory_context") {
              // Update user message CID and prep AI message with memories
              setMessages((prev) =>
                prev.map((m) => {
                  if (m.id === userMsg.id) return { ...m, userCid: event.userCid };
                  if (m.id === aiMsgId) return { ...m, retrievedMemories: event.memories };
                  return m;
                })
              );
            } else if (event.type === "token") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === aiMsgId ? { ...m, content: m.content + event.text } : m
                )
              );
            } else if (event.type === "stored") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === aiMsgId
                    ? { ...m, storedCid: event.aiCid, isStreaming: false }
                    : m
                )
              );
            }
          } catch {
            // malformed SSE chunk
          }
        }
      }

      // Ensure streaming indicator is cleared
      setMessages((prev) =>
        prev.map((m) => (m.id === aiMsgId ? { ...m, isStreaming: false } : m))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setMessages((prev) => prev.filter((m) => m.id !== aiMsgId));
    } finally {
      setLoading(false);
    }
  }, [input, loading]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex flex-col h-screen bg-[#080608] text-slate-200">
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="shrink-0 border-b border-white/10 px-4 py-3">
        <div className="max-w-3xl mx-auto flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-white/40 hover:text-white transition-colors text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            Home
          </Link>
          <span className="text-white/20">/</span>

          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-fuchsia-400" />
            <span className="font-medium text-white text-sm">Engram Memory</span>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <span className="text-[11px] bg-fuchsia-500/15 text-fuchsia-300 border border-fuchsia-500/25 px-2 py-0.5 rounded-full">
              Permanent Memory
            </span>
            <Link
              href="/playground"
              className="text-[11px] text-white/30 hover:text-white/60 transition-colors hidden sm:block"
            >
              Playground
            </Link>
          </div>
        </div>
      </div>

      {/* ── No API Key banner ────────────────────────────────────────────────── */}
      {noApiKey && (
        <div className="shrink-0 bg-amber-500/10 border-b border-amber-500/20 px-4 py-3">
          <div className="max-w-3xl mx-auto flex items-start gap-2 text-sm text-amber-300">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <div>
              <span className="font-medium">API key not configured.</span> Add{" "}
              <code className="bg-black/30 px-1 rounded font-mono text-xs">XAI_API_KEY=xai-…</code>{" "}
              to <code className="bg-black/30 px-1 rounded font-mono text-xs">.env.local</code> and restart the server.
              Get one at <span className="font-mono text-xs">console.x.ai</span>.
            </div>
          </div>
        </div>
      )}

      {/* ── Messages ────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6 flex flex-col gap-6">

          {/* Empty state */}
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-center gap-5">
              <div className="relative">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-fuchsia-600/30 to-violet-600/30 border border-fuchsia-500/20 flex items-center justify-center">
                  <Brain className="w-8 h-8 text-fuchsia-400" />
                </div>
                <Sparkles className="w-4 h-4 text-fuchsia-300 absolute -top-1.5 -right-1.5" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-white mb-2">
                  AI that never forgets
                </h2>
                <p className="text-white/40 text-sm max-w-sm leading-relaxed">
                  Every message is stored as a vector embedding on the Engram
                  decentralized network. Recalled across sessions — permanently.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-2 w-full max-w-lg">
                {[
                  "What is Engram and how does it store memories?",
                  "Explain proof of storage in simple terms",
                  "How is this different from a normal chatbot?",
                ].map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => setInput(prompt)}
                    className="text-left text-xs text-white/40 hover:text-white/70 bg-white/4 hover:bg-white/8 border border-white/10 hover:border-white/20 rounded-xl px-3 py-2.5 transition-all leading-snug"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages */}
          {messages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} />
          ))}

          {/* Typing indicator while waiting for first token */}
          {loading && messages[messages.length - 1]?.role === "user" && (
            <TypingIndicator />
          )}

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 text-sm text-red-400 max-w-[85%]">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* ── Input bar ───────────────────────────────────────────────────────── */}
      <div className="shrink-0 border-t border-white/10 bg-[#080608]/95 backdrop-blur px-4 py-4">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-end gap-2 bg-white/5 border border-white/10 rounded-2xl px-4 py-3 focus-within:border-fuchsia-500/40 transition-colors">
            <textarea
              ref={textareaRef}
              className="flex-1 bg-transparent text-sm text-white placeholder-white/30 resize-none focus:outline-none min-h-[24px] max-h-[160px] leading-relaxed"
              placeholder="Say something — I'll remember it forever…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={loading}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              className="shrink-0 w-8 h-8 flex items-center justify-center rounded-xl bg-fuchsia-600 hover:bg-fuchsia-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 text-white animate-spin" />
              ) : (
                <Send className="w-4 h-4 text-white" />
              )}
            </button>
          </div>
          <p className="text-[11px] text-white/20 text-center mt-2">
            Each message is stored on Engram · retrieved by semantic similarity · powered by Bittensor
          </p>
        </div>
      </div>
    </div>
  );
}
