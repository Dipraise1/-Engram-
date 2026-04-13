import { NextResponse } from "next/server";

const MINER_URL = process.env.MINER_API_URL || "http://98.97.76.65:8091";

// ── GET /api/history?uid=<userId> ─────────────────────────────────────────────

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const uid = (searchParams.get("uid") ?? "").trim();

  if (!uid || uid.length > 128) {
    return NextResponse.json({ messages: [] });
  }

  try {
    const res = await fetch(`${MINER_URL}/chat-history/${encodeURIComponent(uid)}`, {
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return NextResponse.json({ messages: [] });
    const data = await res.json();
    return NextResponse.json({ messages: data.messages ?? [] });
  } catch {
    // Miner unreachable — return empty, client falls back to localStorage
    return NextResponse.json({ messages: [] });
  }
}

// ── POST /api/history ─────────────────────────────────────────────────────────

export async function POST(req: Request) {
  const body = await req.json();
  const uid      = (body.uid ?? "").trim();
  const messages = body.messages ?? [];

  if (!uid || uid.length > 128) {
    return NextResponse.json({ error: "Invalid uid" }, { status: 400 });
  }

  try {
    const res = await fetch(`${MINER_URL}/chat-history`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: uid, messages }),
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) throw new Error("miner error");
    return NextResponse.json({ ok: true });
  } catch {
    // Miner unreachable — silently fail, client keeps localStorage copy
    return NextResponse.json({ ok: false });
  }
}
