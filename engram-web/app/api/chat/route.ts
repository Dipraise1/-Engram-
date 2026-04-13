import { NextResponse } from "next/server";

const MINER_URL = process.env.MINER_API_URL || "http://98.97.76.65:8091";
const XAI_API_KEY = process.env.XAI_API_KEY || "";

// Fetch extra candidates — filter to this session after
const MEMORY_FETCH_K = 40;
const MEMORY_USE_K = 12;
// How many recent messages to include as direct conversation context
const RECENT_HISTORY_N = 20;

export const runtime = "nodejs";

// ── Helpers ────────────────────────────────────────────────────────────────────

async function ingestToEngram(text: string, metadata: Record<string, string>): Promise<string | null> {
  try {
    const res = await fetch(`${MINER_URL}/IngestSynapse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, metadata }),
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.cid ?? null;
  } catch {
    return null;
  }
}

interface MemoryResult {
  cid: string;
  score: number;
  metadata: Record<string, string>;
  text?: string;
}

async function queryEngram(queryText: string, sessionId: string): Promise<MemoryResult[]> {
  try {
    const res = await fetch(`${MINER_URL}/QuerySynapse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query_text: queryText, top_k: MEMORY_FETCH_K }),
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) return [];
    const data = await res.json();
    const all: MemoryResult[] = data.results ?? [];
    // Strict session isolation — discard any memory not belonging to this user
    return all
      .filter((m) => m.metadata?.session === sessionId && m.metadata?.text)
      .slice(0, MEMORY_USE_K);
  } catch {
    return [];
  }
}

// Load recent chat history from our SQLite store (ordered, full text)
async function loadRecentHistory(
  sessionId: string,
  baseUrl: string
): Promise<{ role: "user" | "assistant"; content: string }[]> {
  try {
    const res = await fetch(
      `${baseUrl}/api/history?uid=${encodeURIComponent(sessionId)}`,
      { signal: AbortSignal.timeout(5000) }
    );
    if (!res.ok) return [];
    const data = await res.json();
    const msgs: { role: string; content: string }[] = data.messages ?? [];
    return msgs
      .slice(-(RECENT_HISTORY_N))
      .map((m) => ({
        role: m.role === "assistant" ? "assistant" : "user",
        content: m.content,
      }));
  } catch {
    return [];
  }
}

// ── POST /api/chat ─────────────────────────────────────────────────────────────

export async function POST(req: Request) {
  if (!XAI_API_KEY) {
    return NextResponse.json(
      { error: "XAI_API_KEY is not configured on this server." },
      { status: 503 }
    );
  }

  const body = await req.json();
  const userMessage: string = (body.message ?? "").trim();
  const sessionId: string = body.sessionId ?? "default";

  if (!userMessage) {
    return NextResponse.json({ error: "message is required" }, { status: 400 });
  }

  // Derive the base URL from the incoming request (works on Vercel + local)
  const reqUrl = new URL(req.url);
  const baseUrl = `${reqUrl.protocol}//${reqUrl.host}`;

  // ── Run memory recall + history load + user message storage in parallel ──────
  const [memories, recentHistory, userCid] = await Promise.all([
    queryEngram(userMessage, sessionId),
    loadRecentHistory(sessionId, baseUrl),
    ingestToEngram(userMessage, {
      role: "user",
      session: sessionId,
      text: userMessage.slice(0, 500),
      ts: String(Date.now()),
    }),
  ]);

  // ── Build system prompt ───────────────────────────────────────────────────────
  // Semantic memories (things from older sessions, distant parts of conversation)
  const semanticLines = memories
    .filter((m) => m.metadata?.text)
    .map((m) => {
      const role = m.metadata.role === "assistant" ? "Assistant" : "User";
      return `[${role}]: ${m.metadata.text}`;
    });

  const semanticContext =
    semanticLines.length > 0
      ? `\nSEMANTIC MEMORIES (most relevant past excerpts from Engram network):\n${semanticLines.join("\n")}`
      : "";

  const systemPrompt = `You are Engram AI — a highly intelligent AI assistant with permanent, decentralized memory powered by the Engram network on Bittensor. Every conversation turn is stored as a vector embedding across a decentralized network of miners with cryptographic proof.

You remember everything the user has ever told you — their name, age, preferences, past questions, projects, and anything else they've shared. Recall this naturally in conversation.

Personality: sharp, warm, direct, and technically curious. Give thorough answers. Be honest about uncertainty. Never be evasive.
${semanticContext}

INSTRUCTIONS:
- The semantic memories above are real excerpts from past sessions — treat them as absolute facts
- The conversation messages below are the current session in order — they are the ground truth for what was just said
- If the user asks what you remember, list the key facts from their memories clearly
- Never claim you don't remember something that appears in the memories or conversation history above`;

  // ── Build messages array: history + current message ───────────────────────────
  // We pass the last N turns of history as real messages — this gives Grok
  // the full local conversation context, not just semantic search snippets.
  // Then add the current user message at the end.
  const historyMessages = recentHistory.slice(0, -1); // exclude the very last (current msg already in history via storage race)
  const messages = [
    ...historyMessages,
    { role: "user" as const, content: userMessage },
  ];

  // ── Call xAI Grok ─────────────────────────────────────────────────────────────
  const grokRes = await fetch("https://api.x.ai/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${XAI_API_KEY}`,
    },
    body: JSON.stringify({
      model: "grok-3-fast-beta",
      max_tokens: 1500,
      stream: true,
      messages: [
        { role: "system", content: systemPrompt },
        ...messages,
      ],
    }),
    signal: AbortSignal.timeout(60000),
  });

  if (!grokRes.ok) {
    const errText = await grokRes.text();
    console.error("xAI Grok API error:", errText);
    return NextResponse.json({ error: "AI service error." }, { status: 502 });
  }

  // ── Stream response ───────────────────────────────────────────────────────────
  const encoder = new TextEncoder();
  let fullResponse = "";

  const stream = new ReadableStream({
    async start(controller) {
      // First event: memory metadata for the UI
      controller.enqueue(
        encoder.encode(
          `data: ${JSON.stringify({
            type: "memory_context",
            memories: memories.map((m) => ({
              cid: m.cid,
              score: m.score,
              role: m.metadata?.role,
              text: m.metadata?.text,
            })),
            userCid,
          })}\n\n`
        )
      );

      const reader = grokRes.body!.getReader();
      const dec = new TextDecoder();

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = dec.decode(value, { stream: true });
          for (const line of chunk.split("\n")) {
            if (!line.startsWith("data: ")) continue;
            const raw = line.slice(6).trim();
            if (raw === "[DONE]") continue;
            try {
              const delta = JSON.parse(raw).choices?.[0]?.delta?.content;
              if (typeof delta === "string" && delta.length > 0) {
                fullResponse += delta;
                controller.enqueue(
                  encoder.encode(`data: ${JSON.stringify({ type: "token", text: delta })}\n\n`)
                );
              }
            } catch { /* skip */ }
          }
        }
      } finally {
        reader.releaseLock();
      }

      // Store AI response on Engram
      if (fullResponse) {
        const aiCid = await ingestToEngram(fullResponse, {
          role: "assistant",
          session: sessionId,
          text: fullResponse.slice(0, 500),
          ts: String(Date.now()),
        });
        controller.enqueue(
          encoder.encode(`data: ${JSON.stringify({ type: "stored", aiCid })}\n\n`)
        );
      }

      controller.enqueue(encoder.encode("data: [DONE]\n\n"));
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
