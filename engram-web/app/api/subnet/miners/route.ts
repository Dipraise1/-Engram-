import { NextResponse } from "next/server";

const MINER_URL = process.env.MINER_API_URL || "http://72.62.2.34:8091";

export const revalidate = 0;

async function fetchMinerStats(ip: string, port: number): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`http://${ip}:${port}/stats`, {
      signal: AbortSignal.timeout(3000),
      cache: "no-store",
    });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export async function GET() {
  try {
    const metagraphRes = await fetch(`${MINER_URL}/metagraph`, {
      signal: AbortSignal.timeout(6000),
      cache: "no-store",
    });

    if (!metagraphRes.ok) return NextResponse.json([]);

    const metagraph = await metagraphRes.json();

    const neurons: Array<{
      uid: number;
      hotkey: string | null;
      ip: string | null;
      port: number | null;
      incentive: number;
    }> = metagraph.neurons ?? [];

    // Fan out /stats calls to every neuron that has a routable IP:port (cap 3s each)
    const statsResults = await Promise.all(
      neurons.map((n) =>
        n.ip && n.ip !== "0.0.0.0" && n.port
          ? fetchMinerStats(n.ip, n.port)
          : Promise.resolve(null)
      )
    );

    const miners = neurons.map((n, i) => {
      const live = statsResults[i];
      const isOnline = live !== null && (live as Record<string, unknown>).status === "ok";
      const s = live as Record<string, unknown> | null;

      return {
        uid: n.uid,
        hotkey: n.hotkey,
        vectors: s ? (s.vectors as number ?? 0) : null,
        status: live === null ? (n.ip && n.ip !== "0.0.0.0" ? "offline" : "unknown") : "online",
        peers: s ? (s.peers as number ?? null) : null,
        score:
          n.incentive > 0
            ? n.incentive
            : isOnline
            ? (s!.proof_rate as number ?? null)
            : null,
        latency_ms: s ? (s.p50_latency_ms as number ?? null) : null,
        proof_rate: s ? (s.proof_rate as number ?? null) : null,
        stake: null,
      };
    });

    // Sort: online first, then by score desc, then uid asc
    miners.sort((a, b) => {
      const aOnline = a.status === "online" ? 0 : 1;
      const bOnline = b.status === "online" ? 0 : 1;
      if (aOnline !== bOnline) return aOnline - bOnline;
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
