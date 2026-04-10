import { NextResponse } from "next/server";

const MINER_URL = process.env.MINER_API_URL || "http://98.97.76.65:8091";
const NETUID = process.env.NETUID || "450";

export const revalidate = 0;

export async function GET() {
  try {
    const res = await fetch(`${MINER_URL}/stats`, {
      next: { revalidate: 0 },
      signal: AbortSignal.timeout(5000),
    });

    if (!res.ok) throw new Error(`stats check failed: ${res.status}`);

    const stats = await res.json();

    return NextResponse.json({
      netuid: parseInt(NETUID),
      vectors: stats.vectors ?? 0,
      miners: stats.peers ?? 0,
      validators: 1,
      block: null,
      avg_score: null,
      queries_today: null,
      uptime_pct: null,
      status: stats.status ?? "unknown",
    });
  } catch {
    return NextResponse.json({
      netuid: parseInt(NETUID),
      vectors: null,
      miners: null,
      validators: null,
      block: null,
      avg_score: null,
      queries_today: null,
      uptime_pct: null,
      status: "unreachable",
    }, { status: 200 }); // 200 so dashboard renders the empty state
  }
}
