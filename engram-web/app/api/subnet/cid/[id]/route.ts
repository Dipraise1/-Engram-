import { NextResponse } from "next/server";

const MINER_URL = process.env.MINER_API_URL || "http://localhost:8091";

export async function GET(
  _req: Request,
  { params }: { params: { id: string } }
) {
  const cid = params.id?.trim();
  if (!cid) {
    return NextResponse.json({ error: "missing cid" }, { status: 400 });
  }

  try {
    const res = await fetch(`${MINER_URL}/retrieve/${encodeURIComponent(cid)}`, {
      signal: AbortSignal.timeout(8000),
    });

    if (res.status === 404) {
      return NextResponse.json({ error: "CID not found on this miner." }, { status: 404 });
    }
    if (!res.ok) {
      throw new Error(`miner error ${res.status}`);
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("not found")) {
      return NextResponse.json({ error: "CID not found on this miner." }, { status: 404 });
    }
    return NextResponse.json({ error: "Miner unreachable." }, { status: 503 });
  }
}
