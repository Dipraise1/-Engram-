import { NextResponse } from "next/server";
// eslint-disable-next-line @typescript-eslint/no-require-imports
const pdfParse = require("pdf-parse") as (buf: Buffer) => Promise<{ text: string; numpages: number }>;

const MINER_URL = process.env.MINER_API_URL || "http://72.62.2.34:8091";
const XAI_API_KEY = process.env.XAI_API_KEY || "";
const MAX_TEXT_CHARS = 8192;

export const runtime = "nodejs";

async function describeImageWithGrok(base64: string, mimeType: string): Promise<string> {
  if (!XAI_API_KEY) throw new Error("XAI_API_KEY not configured");

  const res = await fetch("https://api.x.ai/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${XAI_API_KEY}`,
    },
    body: JSON.stringify({
      model: "grok-2-vision-latest",
      max_tokens: 1024,
      messages: [
        {
          role: "user",
          content: [
            {
              type: "image_url",
              image_url: { url: `data:${mimeType};base64,${base64}`, detail: "high" },
            },
            {
              type: "text",
              text: "Describe this image in detail. Extract any visible text verbatim. Include layout, content, and context. Be thorough — this description will be stored as a searchable memory.",
            },
          ],
        },
      ],
    }),
    signal: AbortSignal.timeout(30000),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Grok vision error ${res.status}: ${err.slice(0, 200)}`);
  }

  const data = await res.json();
  return data.choices?.[0]?.message?.content ?? "";
}

async function ingestText(text: string, metadata: Record<string, string>): Promise<string> {
  const res = await fetch(`${MINER_URL}/IngestSynapse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: text.slice(0, MAX_TEXT_CHARS), metadata }),
    signal: AbortSignal.timeout(30000),
  });
  if (!res.ok) throw new Error(`Miner responded ${res.status}`);
  const data = await res.json();
  if (data.error) throw new Error(data.error);
  return data.cid;
}

export async function POST(req: Request) {
  let formData: FormData;
  try {
    formData = await req.formData();
  } catch {
    return NextResponse.json({ error: "Expected multipart/form-data" }, { status: 400 });
  }

  const file = formData.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "No file uploaded" }, { status: 400 });
  }

  const name = file.name;
  const mime = file.type;
  const bytes = await file.arrayBuffer();
  const buffer = Buffer.from(bytes);

  try {
    // ── PDF ───────────────────────────────────────────────────────────────────
    if (mime === "application/pdf" || name.endsWith(".pdf")) {
      const parsed = await pdfParse(buffer);
      const text = parsed.text.replace(/\s+/g, " ").trim();

      if (!text) {
        return NextResponse.json({ error: "PDF appears to be empty or image-only — try the image tab instead." }, { status: 422 });
      }

      const pages = parsed.numpages;
      // Chunk large PDFs: ingest first 8192 chars (one chunk for now)
      const cid = await ingestText(text, {
        source: name,
        type: "pdf",
        pages: String(pages),
        text: text.slice(0, 500),
      });

      return NextResponse.json({ cid, pages, chars: text.length, type: "pdf" });
    }

    // ── Image ─────────────────────────────────────────────────────────────────
    if (mime.startsWith("image/") || /\.(png|jpg|jpeg|gif|webp)$/i.test(name)) {
      const base64 = buffer.toString("base64");
      const effectiveMime = mime || "image/png";

      const description = await describeImageWithGrok(base64, effectiveMime);

      if (!description) {
        return NextResponse.json({ error: "Image description came back empty." }, { status: 422 });
      }

      const cid = await ingestText(description, {
        source: name,
        type: "image",
        text: description.slice(0, 500),
      });

      return NextResponse.json({ cid, description: description.slice(0, 300), type: "image" });
    }

    return NextResponse.json(
      { error: `Unsupported file type: ${mime || name}. Supported: PDF, PNG, JPG, WEBP, GIF.` },
      { status: 415 }
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("connect") || msg.includes("fetch") || msg.includes("timeout")) {
      return NextResponse.json({ error: "Miner unreachable — is it running?" }, { status: 503 });
    }
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
