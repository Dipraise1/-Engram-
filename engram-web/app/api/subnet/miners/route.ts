import { NextResponse } from "next/server";

const MINER_URL = process.env.MINER_API_URL || "http://72.62.2.34:8091";

export const revalidate = 0;

export async function GET() {
  try {
    const statsRes = await fetch(`${MINER_URL}/stats`, {
      signal: AbortSignal.timeout(5000),
    });

    if (!statsRes.ok) return NextResponse.json([]);

    const stats = await statsRes.json();

    const miners = [{
      uid: stats.uid ?? 2,
      hotkey: stats.hotkey ?? null,
      vectors: stats.vectors ?? 0,
      status: stats.status === "ok" ? "online" : "offline",
      peers: stats.peers ?? 0,
      score: stats.avg_score ?? null,
      latency_ms: stats.p50_latency_ms ?? null,
      proof_rate: stats.proof_rate ?? null,
      stake: null,
    }];

    return NextResponse.json(miners);
  } catch {
    return NextResponse.json([]);
  }
}
