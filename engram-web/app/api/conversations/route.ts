import { NextResponse } from "next/server";

const MINER_URL = process.env.MINER_API_URL || "http://localhost:8091";

// ── GET /api/conversations?uid=X ─────────────────────────────────────────────

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const uid = (searchParams.get("uid") ?? "").trim();

  if (!uid || uid.length > 128) {
    return NextResponse.json({ conversations: [] });
  }

  try {
    const res = await fetch(`${MINER_URL}/conversations/${encodeURIComponent(uid)}`, {
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return NextResponse.json({ conversations: [] });
    const data = await res.json();
    return NextResponse.json({ conversations: data.conversations ?? [] });
  } catch {
    return NextResponse.json({ conversations: [] });
  }
}

// ── POST /api/conversations — create ─────────────────────────────────────────

export async function POST(req: Request) {
  const body = await req.json();
  const uid     = (body.uid ?? "").trim();
  const conv_id = (body.conv_id ?? "").trim();
  const title   = (body.title ?? "New Chat").trim();

  if (!uid || !conv_id || uid.length > 128 || conv_id.length > 128) {
    return NextResponse.json({ error: "Invalid uid or conv_id" }, { status: 400 });
  }

  try {
    const res = await fetch(`${MINER_URL}/conversations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: uid, conv_id, title }),
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) throw new Error("miner error");
    return NextResponse.json({ ok: true });
  } catch {
    return NextResponse.json({ ok: false });
  }
}

// ── PATCH /api/conversations — rename ────────────────────────────────────────

export async function PATCH(req: Request) {
  const body = await req.json();
  const uid     = (body.uid ?? "").trim();
  const conv_id = (body.conv_id ?? "").trim();
  const title   = (body.title ?? "").trim();

  if (!uid || !conv_id || !title) {
    return NextResponse.json({ error: "Invalid params" }, { status: 400 });
  }

  try {
    const res = await fetch(`${MINER_URL}/conversations/${encodeURIComponent(conv_id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: uid, title }),
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) throw new Error("miner error");
    return NextResponse.json({ ok: true });
  } catch {
    return NextResponse.json({ ok: false });
  }
}

// ── DELETE /api/conversations?uid=X&conv_id=Y ────────────────────────────────

export async function DELETE(req: Request) {
  const { searchParams } = new URL(req.url);
  const uid     = (searchParams.get("uid") ?? "").trim();
  const conv_id = (searchParams.get("conv_id") ?? "").trim();

  if (!uid || !conv_id) {
    return NextResponse.json({ error: "Invalid params" }, { status: 400 });
  }

  try {
    const res = await fetch(
      `${MINER_URL}/conversations/${encodeURIComponent(conv_id)}?user_id=${encodeURIComponent(uid)}`,
      { method: "DELETE", signal: AbortSignal.timeout(8000) }
    );
    if (!res.ok) throw new Error("miner error");
    return NextResponse.json({ ok: true });
  } catch {
    return NextResponse.json({ ok: false });
  }
}
