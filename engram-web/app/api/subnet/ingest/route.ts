import { NextResponse } from "next/server";

const MINER_URL = process.env.MINER_API_URL || "http://98.97.76.65:8091";
const MAX_TEXT_CHARS = 8192;

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const text: string = body.text ?? "";
    const metadata: Record<string, string> = body.metadata ?? {};

    if (!text || typeof text !== "string") {
      return NextResponse.json(
        { error: "Missing or invalid 'text' field." },
        { status: 400 }
      );
    }

    if (text.length > MAX_TEXT_CHARS) {
      return NextResponse.json(
        { error: `Text is too long (${text.length} chars). Max is ${MAX_TEXT_CHARS}.` },
        { status: 400 }
      );
    }

    const res = await fetch(`${MINER_URL}/IngestSynapse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, metadata }),
      signal: AbortSignal.timeout(30000),
    });

    if (!res.ok) {
      throw new Error(`Miner responded with status ${res.status}`);
    }

    const data = await res.json();

    if (data.error) {
      return NextResponse.json({ error: data.error }, { status: 422 });
    }

    return NextResponse.json({ cid: data.cid });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    if (message.includes("fetch") || message.includes("connect") || message.includes("timeout")) {
      return NextResponse.json(
        { error: "Miner unreachable — is it running?" },
        { status: 503 }
      );
    }
    return NextResponse.json({ error: "Internal error." }, { status: 500 });
  }
}
