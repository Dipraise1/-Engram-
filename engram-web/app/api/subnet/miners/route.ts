import { NextResponse } from "next/server";

const MINER_URL = process.env.MINER_API_URL || "http://98.97.76.65:8091";

export const revalidate = 0;

export async function GET() {
  try {
    const statsRes = await fetch(`${MINER_URL}/stats`, {
      signal: AbortSignal.timeout(5000),
    });

    if (!statsRes.ok) return NextResponse.json([]);

    const stats = await statsRes.json();

    const miners = [{
      uid: stats.uid ?? 1,
      hotkey: null,
      vectors: stats.vectors ?? 0,
      status: stats.status === "ok" ? "online" : "offline",
      peers: stats.peers ?? 0,
      // These come from validator scoring — not available via miner stats alone
      score: null,
      latency_ms: null,
      proof_rate: null,
      stake: null,
    }];

    return NextResponse.json(miners);
  } catch {
    return NextResponse.json([]);
  }
}
