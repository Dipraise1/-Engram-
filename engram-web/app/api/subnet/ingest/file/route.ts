import { NextResponse } from "next/server";
import { uploadToArweave, contentCid } from "@/lib/arweave";

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

  if (!res.ok) throw new Error(`Grok vision error ${res.status}: ${(await res.text()).slice(0, 200)}`);
  return (await res.json()).choices?.[0]?.message?.content ?? "";
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
        return NextResponse.json(
          { error: "PDF appears to be empty or image-only — try the image tab instead." },
          { status: 422 }
        );
      }

      // Upload PDF to Arweave for permanent retrieval
      let arweave_tx_id: string | null = null;
      let arweave_url: string | null = null;
      try {
        const upload = await uploadToArweave(buffer, "application/pdf", {
          "File-Name": name,
          "Content-Source": "engram-playground",
        });
        arweave_tx_id = upload.tx_id;
        arweave_url = upload.url;
      } catch (e) {
        // Arweave upload failure is non-fatal — text still gets stored in Engram
        console.warn("Arweave upload failed for PDF:", e);
      }

      const cid = await ingestText(text, {
        source: name,
        type: "pdf",
        pages: String(parsed.numpages),
        text: text.slice(0, 500),
        ...(arweave_tx_id ? { arweave_tx_id, arweave_url: arweave_url! } : {}),
      });

      return NextResponse.json({
        cid,
        pages: parsed.numpages,
        chars: text.length,
        type: "pdf",
        arweave_tx_id,
        arweave_url,
      });
    }

    // ── Image ─────────────────────────────────────────────────────────────────
    if (mime.startsWith("image/") || /\.(png|jpg|jpeg|gif|webp)$/i.test(name)) {
      const effectiveMime = mime || "image/png";
      const base64 = buffer.toString("base64");

      // Run Grok vision + Arweave upload in parallel
      const [description, arweaveResult] = await Promise.allSettled([
        describeImageWithGrok(base64, effectiveMime),
        uploadToArweave(buffer, effectiveMime, {
          "File-Name": name,
          "Content-Source": "engram-playground",
          "Content-Hash": contentCid(buffer),
        }),
      ]);

      if (description.status === "rejected") {
        throw new Error(description.reason?.message ?? "Image description failed");
      }

      const desc = description.value;
      const upload = arweaveResult.status === "fulfilled" ? arweaveResult.value : null;

      if (arweaveResult.status === "rejected") {
        console.warn("Arweave upload failed:", arweaveResult.reason);
      }

      // Generate thumbnail: store first 2KB of base64 as a data-URL preview
      // (keeps miner metadata lean — ~2KB instead of full image)
      const thumbnail = `data:${effectiveMime};base64,${base64.slice(0, 2048)}`;

      const cid = await ingestText(desc, {
        source: name,
        type: "image",
        text: desc.slice(0, 500),
        content_cid: contentCid(buffer),
        thumbnail,
        ...(upload ? {
          arweave_tx_id: upload.tx_id,
          arweave_url: upload.url,
        } : {}),
      });

      return NextResponse.json({
        cid,
        description: desc.slice(0, 300),
        type: "image",
        content_cid: contentCid(buffer),
        arweave_tx_id: upload?.tx_id ?? null,
        arweave_url: upload?.url ?? null,
        size: buffer.length,
      });
    }

    return NextResponse.json(
      { error: `Unsupported file type: ${mime || name}. Supported: PDF, PNG, JPG, WEBP, GIF.` },
      { status: 415 }
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("connect") || msg.includes("fetch") || msg.includes("timeout") || msg.includes("unreachable")) {
      return NextResponse.json({ error: "Miner unreachable — is it running?" }, { status: 503 });
    }
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
