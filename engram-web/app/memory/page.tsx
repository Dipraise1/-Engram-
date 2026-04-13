"use client";

import { useState, useRef, useEffect, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
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
  Share2,
  Check,
  Copy,
  ExternalLink,
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

// ── Share encode/decode ────────────────────────────────────────────────────────

function encodeShare(messages: Message[]): string {
  const slim = messages.map((m) => ({ r: m.role === "user" ? "u" : "a", c: m.content }));
  return btoa(unescape(encodeURIComponent(JSON.stringify(slim))));
}

function decodeShare(encoded: string): { role: "user" | "assistant"; content: string }[] | null {
  try {
    const raw = decodeURIComponent(escape(atob(encoded)));
    const parsed = JSON.parse(raw) as { r: string; c: string }[];
    return parsed.map((m) => ({ role: m.r === "u" ? "user" : "assistant", content: m.c }));
  } catch {
    return null;
  }
}

// ── Session ID ─────────────────────────────────────────────────────────────────

function getSessionId(): string {
  if (typeof window === "undefined") return "ssr";
  let id = localStorage.getItem("engram_session");
  if (!id) {
    id = `s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}`;
    localStorage.setItem("engram_session", id);
  }
  return id;
}

// ── Local cache (localStorage) ────────────────────────────────────────────────

function localLoad(uid: string): Message[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(`engram_msgs_${uid}`);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function localSave(uid: string, messages: Message[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(`engram_msgs_${uid}`, JSON.stringify(messages.slice(-200)));
  } catch { /* quota exceeded */ }
}

// ── Server sync ───────────────────────────────────────────────────────────────

async function serverLoad(uid: string): Promise<Message[]> {
  try {
    const res = await fetch(`/api/history?uid=${encodeURIComponent(uid)}`);
    if (!res.ok) return [];
    const data = await res.json();
    return (data.messages ?? []).map(
      (m: { role: string; content: string }, i: number) => ({
        id: `srv_${i}`,
        role: m.role as "user" | "assistant",
        content: m.content,
      })
    );
  } catch {
    return [];
  }
}

async function serverSave(uid: string, messages: Message[]) {
  try {
    await fetch("/api/history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        uid,
        messages: messages.map((m) => ({ role: m.role, content: m.content })),
      }),
    });
  } catch { /* best-effort */ }
}

// ── Memory pill ────────────────────────────────────────────────────────────────

function MemoryPill({ memory }: { memory: Memory }) {
  const label = memory.text
    ? memory.text.slice(0, 55) + (memory.text.length > 55 ? "…" : "")
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
      <span className="leading-snug min-w-0 break-words">{label}</span>
      <span className="ml-auto shrink-0 opacity-50 font-mono">{scorePct}%</span>
    </div>
  );
}

// ── Message bubble ─────────────────────────────────────────────────────────────

function MessageBubble({ msg, readOnly }: { msg: Message; readOnly: boolean }) {
  const [showMem, setShowMem] = useState(false);
  const isUser = msg.role === "user";

  return (
    <div className={`flex flex-col gap-1.5 ${isUser ? "items-end" : "items-start"}`}>
      {/* Memory context toggle (assistant only) */}
      {!isUser && !readOnly && msg.retrievedMemories && msg.retrievedMemories.length > 0 && (
        <div className="w-full max-w-[88%]">
          <button
            onClick={() => setShowMem((v) => !v)}
            className="flex items-center gap-1.5 text-[11px] text-white/30 hover:text-white/60 transition-colors mb-1 touch-manipulation"
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
        className={`max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words ${
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

      {/* Storage CID indicator */}
      {!readOnly && !isUser && msg.storedCid && (
        <div className="flex items-center gap-1 text-[11px] text-white/20">
          <Zap className="w-2.5 h-2.5" />
          <span className="font-mono truncate max-w-[160px]">
            {msg.storedCid.slice(0, 8)}…{msg.storedCid.slice(-6)}
          </span>
        </div>
      )}
    </div>
  );
}

// ── Typing indicator ───────────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div className="flex items-start">
      <div className="flex items-center gap-1 bg-white/8 border border-white/10 rounded-2xl rounded-bl-sm px-4 py-3">
        <span className="w-2 h-2 bg-white/40 rounded-full animate-bounce [animation-delay:-0.3s]" />
        <span className="w-2 h-2 bg-white/40 rounded-full animate-bounce [animation-delay:-0.15s]" />
        <span className="w-2 h-2 bg-white/40 rounded-full animate-bounce" />
      </div>
    </div>
  );
}

// ── Share button ───────────────────────────────────────────────────────────────

function ShareButton({ messages }: { messages: Message[] }) {
  const [state, setState] = useState<"idle" | "copied">("idle");

  function handleShare() {
    if (messages.length === 0) return;
    const encoded = encodeShare(messages);
    const url = `${window.location.origin}/memory?view=${encoded}`;
    navigator.clipboard.writeText(url).then(() => {
      setState("copied");
      setTimeout(() => setState("idle"), 2000);
    });
  }

  return (
    <button
      onClick={handleShare}
      disabled={messages.length === 0}
      title="Copy shareable link"
      className="flex items-center gap-1.5 text-xs text-white/40 hover:text-white/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors px-3 py-2 rounded-lg hover:bg-white/5 touch-manipulation"
    >
      {state === "copied" ? (
        <>
          <Check className="w-3.5 h-3.5 text-green-400" />
          <span className="text-green-400">Copied!</span>
        </>
      ) : (
        <>
          <Share2 className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Share</span>
        </>
      )}
    </button>
  );
}

// ── Read-only view banner ──────────────────────────────────────────────────────

function ReadOnlyBanner() {
  const router = useRouter();
  return (
    <div className="shrink-0 bg-violet-500/10 border-b border-violet-500/20 px-4 py-2.5">
      <div className="max-w-3xl mx-auto flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs text-violet-300">
          <ExternalLink className="w-3.5 h-3.5 shrink-0" />
          <span>You&apos;re viewing a shared conversation</span>
        </div>
        <button
          onClick={() => router.push("/memory")}
          className="shrink-0 text-xs bg-fuchsia-600 hover:bg-fuchsia-500 text-white px-3 py-1.5 rounded-lg transition-colors touch-manipulation"
        >
          Start your own
        </button>
      </div>
    </div>
  );
}

// ── Inner page (needs useSearchParams, wrapped in Suspense) ───────────────────

function MemoryPageInner() {
  const searchParams = useSearchParams();
  const viewParam = searchParams.get("view");
  const readOnly = viewParam !== null;

  const sessionId = useRef<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [noApiKey, setNoApiKey] = useState(false);
  const [initialized, setInitialized] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesRef = useRef<Message[]>([]);

  // Initialize: load from server (source of truth), fall back to localStorage
  useEffect(() => {
    if (readOnly && viewParam) {
      const shared = decodeShare(viewParam);
      if (shared) {
        setMessages(shared.map((m, i) => ({ id: `shared_${i}`, role: m.role, content: m.content })));
      }
      setInitialized(true);
      return;
    }

    sessionId.current = getSessionId();
    const uid = sessionId.current;

    // Show local cache immediately (instant), then hydrate from server
    const local = localLoad(uid);
    if (local.length > 0) setMessages(local);

    serverLoad(uid).then((serverMsgs) => {
      if (serverMsgs.length > 0) {
        // Server has more messages (e.g. different device) — prefer server
        setMessages(serverMsgs);
        localSave(uid, serverMsgs);
      }
      setInitialized(true);
    });
  }, [readOnly, viewParam]);

  // Keep both caches in sync whenever messages change
  useEffect(() => {
    messagesRef.current = messages;
    if (!readOnly && initialized && sessionId.current) {
      localSave(sessionId.current, messages);
      serverSave(sessionId.current, messages);
    }
  }, [messages, readOnly, initialized]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 120) + "px";
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
        if (data.error?.includes("XAI_API_KEY")) setNoApiKey(true);
        setError(data.error ?? "Service unavailable.");
        setMessages((prev) => prev.filter((m) => m.id !== aiMsgId));
        setLoading(false);
        return;
      }

      if (!res.ok || !res.body) throw new Error("Chat request failed");

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
                  m.id === aiMsgId ? { ...m, storedCid: event.aiCid, isStreaming: false } : m
                )
              );
            }
          } catch { /* skip malformed */ }
        }
      }

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
    <div
      className="flex flex-col bg-[#080608] text-slate-200"
      style={{ height: "100dvh" }}
    >
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="shrink-0 border-b border-white/10 px-4 py-3 safe-area-top">
        <div className="max-w-3xl mx-auto flex items-center gap-2">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-white/40 hover:text-white transition-colors p-1 -ml-1 touch-manipulation"
            aria-label="Home"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="text-sm hidden sm:inline">Home</span>
          </Link>
          <span className="text-white/20 hidden sm:inline">/</span>

          <div className="flex items-center gap-1.5 ml-1 sm:ml-0">
            <Brain className="w-4 h-4 text-fuchsia-400 shrink-0" />
            <span className="font-medium text-white text-sm">Engram Memory</span>
          </div>

          <div className="ml-auto flex items-center gap-1">
            {!readOnly && <ShareButton messages={messages} />}
            <span className="text-[11px] bg-fuchsia-500/15 text-fuchsia-300 border border-fuchsia-500/25 px-2 py-0.5 rounded-full hidden sm:inline">
              Permanent Memory
            </span>
          </div>
        </div>
      </div>

      {/* ── Read-only banner ─────────────────────────────────────────────────── */}
      {readOnly && <ReadOnlyBanner />}

      {/* ── API key banner ───────────────────────────────────────────────────── */}
      {noApiKey && (
        <div className="shrink-0 bg-amber-500/10 border-b border-amber-500/20 px-4 py-2.5">
          <div className="max-w-3xl mx-auto flex items-start gap-2 text-xs text-amber-300">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>
              <span className="font-medium">API key not configured.</span> Add{" "}
              <code className="bg-black/30 px-1 rounded font-mono">XAI_API_KEY=xai-…</code>{" "}
              to <code className="bg-black/30 px-1 rounded font-mono">.env.local</code>.
            </span>
          </div>
        </div>
      )}

      {/* ── Messages ─────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto overscroll-contain">
        <div className="max-w-3xl mx-auto px-4 py-5 flex flex-col gap-5">

          {/* Empty state */}
          {messages.length === 0 && initialized && !readOnly && (
            <div className="flex flex-col items-center justify-center py-16 text-center gap-5 px-2">
              <div className="relative">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-fuchsia-600/30 to-violet-600/30 border border-fuchsia-500/20 flex items-center justify-center">
                  <Brain className="w-7 h-7 text-fuchsia-400" />
                </div>
                <Sparkles className="w-4 h-4 text-fuchsia-300 absolute -top-1.5 -right-1.5" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white mb-1.5">AI that never forgets</h2>
                <p className="text-white/40 text-sm max-w-xs leading-relaxed">
                  Every message is permanently stored as a vector embedding on the
                  Engram decentralized network.
                </p>
              </div>
              <div className="grid grid-cols-1 gap-2 w-full max-w-sm">
                {[
                  "What is Engram and how does it store memories?",
                  "Explain proof of storage in simple terms",
                  "How is this different from a normal chatbot?",
                ].map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => setInput(prompt)}
                    className="text-left text-xs text-white/50 hover:text-white/80 bg-white/4 hover:bg-white/8 border border-white/10 hover:border-white/20 rounded-xl px-3 py-3 transition-all leading-snug touch-manipulation active:scale-[0.98]"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Empty shared state */}
          {messages.length === 0 && initialized && readOnly && (
            <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
              <Brain className="w-8 h-8 text-white/20" />
              <p className="text-white/30 text-sm">This shared conversation is empty or the link is invalid.</p>
            </div>
          )}

          {/* Messages */}
          {messages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} readOnly={readOnly} />
          ))}

          {/* Typing indicator */}
          {loading && messages[messages.length - 1]?.role === "user" && (
            <TypingIndicator />
          )}

          {/* Error */}
          {error && !noApiKey && (
            <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 text-sm text-red-400 max-w-[88%]">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* ── Input bar (hidden in read-only mode) ─────────────────────────────── */}
      {!readOnly && (
        <div
          className="shrink-0 border-t border-white/10 bg-[#080608]/95 backdrop-blur px-3 pt-3 pb-3"
          style={{ paddingBottom: "max(12px, env(safe-area-inset-bottom))" }}
        >
          <div className="max-w-3xl mx-auto">
            <div className="flex items-end gap-2 bg-white/5 border border-white/10 rounded-2xl px-3 py-2.5 focus-within:border-fuchsia-500/40 transition-colors">
              <textarea
                ref={textareaRef}
                className="flex-1 bg-transparent text-[16px] leading-snug text-white placeholder-white/30 resize-none focus:outline-none min-h-[24px] max-h-[120px]"
                placeholder="Say something — I'll remember it forever…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={1}
                disabled={loading}
                autoComplete="off"
                autoCorrect="on"
                spellCheck
              />
              <button
                onClick={sendMessage}
                disabled={!input.trim() || loading}
                className="shrink-0 w-9 h-9 flex items-center justify-center rounded-xl bg-fuchsia-600 hover:bg-fuchsia-500 active:bg-fuchsia-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors touch-manipulation"
                aria-label="Send"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 text-white animate-spin" />
                ) : (
                  <Send className="w-4 h-4 text-white" />
                )}
              </button>
            </div>
            <p className="text-[10px] text-white/15 text-center mt-2 px-2">
              Stored on Engram · recalled by semantic similarity · powered by Bittensor
            </p>
          </div>
        </div>
      )}

      {/* Read-only bottom bar */}
      {readOnly && (
        <div
          className="shrink-0 border-t border-white/10 bg-[#080608]/95 backdrop-blur px-4 py-3"
          style={{ paddingBottom: "max(12px, env(safe-area-inset-bottom))" }}
        >
          <div className="max-w-3xl mx-auto flex items-center justify-between gap-3">
            <p className="text-xs text-white/30">
              {messages.length} message{messages.length !== 1 ? "s" : ""} in this conversation
            </p>
            <Link
              href="/memory"
              className="flex items-center gap-1.5 text-xs bg-fuchsia-600 hover:bg-fuchsia-500 text-white px-4 py-2 rounded-xl transition-colors touch-manipulation"
            >
              <Brain className="w-3.5 h-3.5" />
              Start your own
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Page (Suspense boundary for useSearchParams) ───────────────────────────────

export default function MemoryPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-[100dvh] bg-[#080608]">
          <Loader2 className="w-6 h-6 text-fuchsia-400 animate-spin" />
        </div>
      }
    >
      <MemoryPageInner />
    </Suspense>
  );
}
