import { NextResponse } from "next/server";

const MINER_URL = process.env.MINER_API_URL || "http://98.97.76.65:8091";
const XAI_API_KEY = process.env.XAI_API_KEY || "";

// How many past memories to inject as context
const MEMORY_TOP_K = 12;

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

async function queryEngram(queryText: string): Promise<MemoryResult[]> {
  try {
    const res = await fetch(`${MINER_URL}/QuerySynapse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query_text: queryText, top_k: MEMORY_TOP_K }),
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.results ?? [];
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

  // ── 1. Retrieve relevant memories from Engram ────────────────────────────────
  const memories = await queryEngram(userMessage);

  // ── 2. Store the user's message in Engram ────────────────────────────────────
  const userCid = await ingestToEngram(userMessage, {
    role: "user",
    session: sessionId,
    text: userMessage.slice(0, 500),  // stored so recall can read the actual content
    ts: String(Date.now()),
  });

  // ── 3. Build system prompt with memory context ───────────────────────────────
  const memoryLines = memories
    .filter((m) => m.metadata?.role && m.metadata?.text)  // only include if we have actual text
    .map((m) => {
      const role = m.metadata.role === "assistant" ? "Assistant" : "User";
      return `[${role}]: ${m.metadata.text}`;
    });

  const memoryContext =
    memoryLines.length > 0
      ? `\n\nPAST CONVERSATION MEMORIES (retrieved from Engram network — these are real things the user said or you replied):\n${memoryLines.join("\n")}`
      : "";

  const systemPrompt = `You are Engram AI — an AI assistant with permanent, decentralized memory powered by the Engram network on Bittensor. Every conversation turn is stored as a vector embedding across a decentralized network of miners, cryptographically proven to exist.

Your personality: thoughtful, direct, and honest. You remember everything the user has ever told you across all sessions.
${memoryContext}

IMPORTANT: The memories above are real excerpts from past conversations with this user. Treat them as factual. If the user asks what you remember about them (their age, what they said, etc.), refer to the memories above and answer accurately. Never claim you don't know something that appears in the memories.`;

  // ── 4. Call xAI Grok with streaming (OpenAI-compatible API) ──────────────────
  const grokRes = await fetch("https://api.x.ai/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${XAI_API_KEY}`,
    },
    body: JSON.stringify({
      model: "grok-3-fast-beta",
      max_tokens: 1024,
      stream: true,
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userMessage },
      ],
    }),
    signal: AbortSignal.timeout(60000),
  });

  if (!grokRes.ok) {
    const errText = await grokRes.text();
    console.error("xAI Grok API error:", errText);
    return NextResponse.json({ error: "AI service error." }, { status: 502 });
  }

  // ── 5. Stream response back to client, collect full text for storage ─────────
  const encoder = new TextEncoder();
  let fullResponse = "";

  const stream = new ReadableStream({
    async start(controller) {
      // Send memory metadata first as a JSON event
      const memMeta = JSON.stringify({
        type: "memory_context",
        memories: memories.map((m) => ({
          cid: m.cid,
          score: m.score,
          role: m.metadata?.role,
          text: m.metadata?.text ?? m.text,
        })),
        userCid,
      });
      controller.enqueue(encoder.encode(`data: ${memMeta}\n\n`));

      const reader = grokRes.body!.getReader();
      const dec = new TextDecoder();

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = dec.decode(value, { stream: true });
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const raw = line.slice(6).trim();
            if (raw === "[DONE]") continue;

            try {
              const parsed = JSON.parse(raw);
              // OpenAI-compatible streaming format
              const delta = parsed.choices?.[0]?.delta?.content;
              if (typeof delta === "string" && delta.length > 0) {
                fullResponse += delta;
                controller.enqueue(
                  encoder.encode(
                    `data: ${JSON.stringify({ type: "token", text: delta })}\n\n`
                  )
                );
              }
            } catch {
              // malformed chunk — skip
            }
          }
        }
      } finally {
        reader.releaseLock();
      }

      // ── 6. Store the AI response in Engram ────────────────────────────────────
      if (fullResponse) {
        const aiCid = await ingestToEngram(fullResponse, {
          role: "assistant",
          session: sessionId,
          text: fullResponse.slice(0, 500),
          ts: String(Date.now()),
        });

        controller.enqueue(
          encoder.encode(
            `data: ${JSON.stringify({ type: "stored", aiCid })}\n\n`
          )
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
