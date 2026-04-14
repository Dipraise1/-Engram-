import { NextResponse } from "next/server";

const MINER_URL = process.env.MINER_API_URL || "http://72.62.2.34:8091";

export async function POST(req: Request) {
  try {
    const body = await req.json();

    const res = await fetch(`${MINER_URL}/QuerySynapse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query_text: body.query_text,
        top_k: body.top_k ?? 5,
      }),
      signal: AbortSignal.timeout(10000),
    });

    if (!res.ok) throw new Error(`miner query failed: ${res.status}`);

    const data = await res.json();
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { error: "Miner unreachable — is it running?", results: [] },
      { status: 503 }
    );
  }
}
