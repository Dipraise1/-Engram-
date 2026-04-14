import { NextResponse } from "next/server";

const MINER_URL = process.env.MINER_API_URL || "http://72.62.2.34:8091";

export const revalidate = 0;

export async function GET() {
  try {
    // Fetch metagraph (all registered neurons) and our miner's live stats in parallel
    const [metagraphRes, statsRes] = await Promise.all([
      fetch(`${MINER_URL}/metagraph`, {
        signal: AbortSignal.timeout(6000),
        cache: "no-store",
      }),
      fetch(`${MINER_URL}/stats`, {
        signal: AbortSignal.timeout(5000),
        cache: "no-store",
      }),
    ]);

    if (!metagraphRes.ok) return NextResponse.json([]);

    const metagraph = await metagraphRes.json();
    const stats = statsRes.ok ? await statsRes.json() : null;

    const neurons: Array<{
      uid: number;
      hotkey: string | null;
      ip: string | null;
      port: number | null;
      incentive: number;
    }> = metagraph.neurons ?? [];

    const miners = neurons.map((n) => {
      const isOurs = stats && n.uid === stats.uid;
      return {
        uid: n.uid,
        hotkey: n.hotkey,
        // For our own miner fill in live stats; others get metagraph data only
        vectors: isOurs ? (stats.vectors ?? 0) : null,
        status: isOurs ? (stats.status === "ok" ? "online" : "offline") : "unknown",
        peers: isOurs ? (stats.peers ?? null) : null,
        score:
          n.incentive > 0
            ? n.incentive
            : isOurs
            ? (stats.proof_rate ?? null)
            : null,
        latency_ms: isOurs ? (stats.p50_latency_ms ?? null) : null,
        proof_rate: isOurs ? (stats.proof_rate ?? null) : null,
        stake: null,
      };
    });

    // Sort: online first, then by score descending, then by uid
    miners.sort((a, b) => {
      if (a.status === "online" && b.status !== "online") return -1;
      if (b.status === "online" && a.status !== "online") return 1;
      const sa = a.score ?? -1;
      const sb = b.score ?? -1;
      if (sb !== sa) return sb - sa;
      return a.uid - b.uid;
    });

    return NextResponse.json(miners);
  } catch {
    return NextResponse.json([]);
  }
}
