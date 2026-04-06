import { NextResponse } from "next/server";

const MINER_URL = process.env.MINER_API_URL || "http://98.97.76.65:8091";

export const revalidate = 0;

export async function GET() {
  try {
    const [healthRes, walletRes] = await Promise.allSettled([
      fetch(`${MINER_URL}/health`, { signal: AbortSignal.timeout(5000) }),
      fetch(`${MINER_URL}/wallet-stats`, { signal: AbortSignal.timeout(5000) }),
    ]);

    const health = healthRes.status === "fulfilled" && healthRes.value.ok
      ? await healthRes.value.json()
      : null;

    const wallet = walletRes.status === "fulfilled" && walletRes.value.ok
      ? await walletRes.value.json()
      : null;

    if (!health) return NextResponse.json([]);

    // Build miner entry from real health data
    const miners = [{
      uid: health.uid ?? 1,
      hotkey: wallet?.hotkey ?? null,
      vectors: health.vectors ?? 0,
      status: health.status === "ok" ? "online" : "offline",
      peers: health.peers ?? 0,
      // These come from validator scoring — not available via miner health alone
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
