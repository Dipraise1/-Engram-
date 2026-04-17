import { NextResponse } from "next/server";

const MINER_URL = process.env.MINER_API_URL || "http://72.62.2.34:8091";
const MAX_CHARS = 8192;

export const runtime = "nodejs";

/** Strip HTML tags and collapse whitespace into plain text. */
function extractText(html: string): { text: string; title: string } {
  // Extract <title>
  const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  const title = titleMatch ? titleMatch[1].replace(/\s+/g, " ").trim() : "";

  // Remove script, style, nav, footer, header blocks entirely
  let cleaned = html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<nav[\s\S]*?<\/nav>/gi, " ")
    .replace(/<footer[\s\S]*?<\/footer>/gi, " ")
    .replace(/<header[\s\S]*?<\/header>/gi, " ");

  // Strip remaining tags, decode common entities
  const text = cleaned
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&nbsp;/g, " ")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, " ")
    .trim();

  return { text, title };
}

export async function POST(req: Request) {
  let body: { url?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Expected JSON body with url field" }, { status: 400 });
  }

  const url = body.url?.trim();
  if (!url) {
    return NextResponse.json({ error: "url is required" }, { status: 400 });
  }

  // Basic URL validation — only http/https
  let parsed: URL;
  try {
    parsed = new URL(url);
    if (!["http:", "https:"].includes(parsed.protocol)) {
      throw new Error("Only http and https URLs are supported");
    }
  } catch (e) {
    return NextResponse.json({ error: `Invalid URL: ${(e as Error).message}` }, { status: 400 });
  }

  // Block private/loopback addresses to prevent SSRF
  const hostname = parsed.hostname.toLowerCase();
  const ssrfPatterns = [
    /^localhost$/,
    /^127\./,
    /^10\./,
    /^192\.168\./,
    /^172\.(1[6-9]|2\d|3[01])\./,
    /^::1$/,
    /^0\.0\.0\.0$/,
    /^169\.254\./,         // link-local
    /^fc00:/,              // IPv6 ULA
  ];
  if (ssrfPatterns.some((p) => p.test(hostname))) {
    return NextResponse.json({ error: "Private/internal URLs are not allowed" }, { status: 400 });
  }

  // Fetch the URL server-side (no CORS issues)
  let rawText: string;
  let contentType: string;
  let finalUrl = url;
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": "EngramBot/1.0 (semantic-memory-indexer)" },
      redirect: "follow",
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) {
      return NextResponse.json(
        { error: `URL returned HTTP ${res.status}` },
        { status: 422 }
      );
    }
    contentType = res.headers.get("content-type") ?? "";
    finalUrl = res.url ?? url;

    if (contentType.includes("application/pdf")) {
      return NextResponse.json(
        { error: "URL points to a PDF — use the PDF tab instead." },
        { status: 415 }
      );
    }
    if (contentType.startsWith("image/")) {
      return NextResponse.json(
        { error: "URL points to an image — use the Image tab instead." },
        { status: 415 }
      );
    }

    rawText = await res.text();
  } catch (e) {
    const msg = (e as Error).message ?? String(e);
    return NextResponse.json(
      { error: `Could not fetch URL: ${msg}` },
      { status: 502 }
    );
  }

  // Extract readable text
  const { text, title } = contentType.includes("text/html")
    ? extractText(rawText)
    : { text: rawText.replace(/\s+/g, " ").trim(), title: finalUrl };

  if (!text || text.length < 20) {
    return NextResponse.json(
      { error: "No readable text found at this URL." },
      { status: 422 }
    );
  }

  // Store in Engram miner
  try {
    const res = await fetch(`${MINER_URL}/IngestSynapse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: text.slice(0, MAX_CHARS),
        metadata: {
          source: finalUrl,
          type: "url",
          title: title.slice(0, 256),
          text: text.slice(0, 500),
        },
      }),
      signal: AbortSignal.timeout(30000),
    });

    const data = await res.json();
    if (data.error) throw new Error(data.error);

    return NextResponse.json({
      cid: data.cid,
      url: finalUrl,
      title,
      chars: text.length,
      type: "url",
    });
  } catch (e) {
    const msg = (e as Error).message ?? String(e);
    if (msg.includes("connect") || msg.includes("fetch") || msg.includes("timeout")) {
      return NextResponse.json({ error: "Miner unreachable — is it running?" }, { status: 503 });
    }
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
