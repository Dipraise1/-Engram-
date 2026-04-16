import type { Metadata } from "next";
import { DocPage, H1, H2, H3, Lead, P, Code, Note, Table, Ic } from "../ui";

export const metadata: Metadata = {
  title: "EngramClient Python SDK",
  description:
    "Complete reference for the EngramClient Python SDK. Ingest text, images, and PDFs, run semantic queries, batch operations, auto-discovery, and private namespace encryption.",
  alternates: { canonical: "https://theengram.space/docs/sdk" },
  openGraph: {
    title: "EngramClient Python SDK — Engram",
    description: "Ingest text, images, and PDFs. Query, batch, and auto-discover vectors with the Engram Python SDK.",
    url: "https://theengram.space/docs/sdk",
  },
};

export default function SDKPage() {
  return (
    <DocPage
      prev={{ href: "/docs/quickstart", label: "Quick Start" }}
      next={{ href: "/docs/namespaces", label: "Private Namespaces" }}
      toc={[
        { id: "install", label: "Install" },
        { id: "client", label: "EngramClient" },
        { id: "autodiscover", label: "from_subnet()" },
        { id: "namespaces", label: "Private namespaces" },
        { id: "ingest", label: "ingest()" },
        { id: "ingest-image", label: "ingest_image()" },
        { id: "ingest-pdf", label: "ingest_pdf()" },
        { id: "query", label: "query()" },
        { id: "batch", label: "batch_ingest_file()" },
        { id: "health", label: "health() / is_online()" },
        { id: "multi-miner", label: "Multi-miner pattern" },
      ]}
    >
      <H1>Python SDK</H1>
      <Lead>
        <Ic>EngramClient</Ic> is a lightweight HTTP client for a single Engram miner. Store text, images, and PDFs — no extra dependencies for text; <Ic>pypdf</Ic> needed for PDFs.
      </Lead>

      <H2 id="install">Install</H2>
      <Code lang="bash">{`pip install engram-subnet

# For PDF support
pip install engram-subnet pypdf`}</Code>

      <H2 id="client">EngramClient</H2>
      <Code lang="python">{`from engram.sdk import EngramClient

client = EngramClient(
    miner_url="http://72.62.2.34:8091",   # or use from_subnet() for auto-discovery
    timeout=30.0,
)`}</Code>

      <Table
        headers={["Parameter", "Type", "Default", "Description"]}
        rows={[
          [<Ic key="mu">miner_url</Ic>, "str", '"http://127.0.0.1:8091"', "Base URL of the miner's HTTP server"],
          [<Ic key="to">timeout</Ic>, "float", "30.0", "Request timeout in seconds"],
          [<Ic key="ns">namespace</Ic>, "str | None", "None", "Private collection name — enables encryption"],
          [<Ic key="nk">namespace_key</Ic>, "str | None", "None", "Secret key for the namespace (min 16 chars)"],
        ]}
      />

      <H2 id="autodiscover">from_subnet()</H2>
      <P>
        Auto-discovers the best available miner from the Bittensor metagraph. Probes the top miners by
        incentive score in parallel and returns a client pointed at the fastest responsive one.
      </P>
      <Code lang="python">{`# One line — no miner URL needed
client = EngramClient.from_subnet(netuid=450)`}</Code>

      <Table
        headers={["Parameter", "Type", "Default", "Description"]}
        rows={[
          [<Ic key="nu">netuid</Ic>, "int", "450", "Subnet UID to query"],
          [<Ic key="nw">network</Ic>, "str", '"finney"', 'Subtensor network — "finney", "test", or ws:// endpoint'],
          [<Ic key="to">timeout</Ic>, "float", "30.0", "Timeout for the returned client"],
          [<Ic key="pt">probe_timeout</Ic>, "float", "3.0", "Timeout for each health probe during discovery"],
          [<Ic key="tn">top_n</Ic>, "int", "5", "Number of top miners to probe (picks by incentive rank)"],
        ]}
      />
      <Note>
        Requires <Ic>bittensor</Ic> to be installed. Raises <Ic>RuntimeError</Ic> if no miners are reachable.
      </Note>

      <H2 id="namespaces">Private namespaces</H2>
      <P>
        Pass <Ic>namespace</Ic> and <Ic>namespace_key</Ic> to store data in an encrypted, private collection.
        Text is encrypted with AES-256-GCM client-side before being sent to any miner.
      </P>
      <Code lang="python">{`private = EngramClient(
    "http://miner:8091",
    namespace="company-docs",
    namespace_key="your-secret-key-min-16-chars",
)

cid = private.ingest("Q4 revenue was $4.2M")  # encrypted before leaving your machine
results = private.query("revenue figures")      # decrypted client-side`}</Code>
      <P>
        See <a href="/docs/namespaces" className="text-[#e040fb] hover:underline">Private Namespaces</a> for
        the full encryption spec and threat model.
      </P>

      <H2 id="ingest">ingest()</H2>
      <Code lang="python">{`cid: str = client.ingest(text: str, metadata: dict = None)`}</Code>
      <P>Embed and store text on the miner. Returns a CID string.</P>
      <Code lang="python">{`cid = client.ingest(
    "BERT uses bidirectional encoder representations.",
    metadata={"source": "arxiv", "year": "2018"}
)
print(cid)  # v1::a3f2b1c4d5e6f7...`}</Code>

      <Table
        headers={["Parameter", "Type", "Description"]}
        rows={[
          [<Ic key="t">text</Ic>, "str", "Text to embed and store (max 8192 chars)"],
          [<Ic key="m">metadata</Ic>, "dict | None", "Optional key-value metadata (max 4 KB JSON)"],
        ]}
      />
      <P>
        <strong className="text-white">Raises:</strong>{" "}
        <Ic>MinerOfflineError</Ic>, <Ic>IngestError</Ic>, <Ic>InvalidCIDError</Ic>
      </P>

      <H2 id="ingest-image">ingest_image()</H2>
      <P>
        Describe an image with Grok Vision (xAI) and store the description as a searchable memory.
        The raw image bytes are <strong className="text-white">never sent to the miner</strong> — only the AI-generated
        description is embedded and stored. A <Ic>content_cid</Ic> (SHA-256 of the image) is stored as metadata
        for integrity verification.
      </P>
      <Code lang="python">{`result = client.ingest_image(
    "photo.jpg",                      # path, or raw bytes
    xai_api_key="xai-...",            # get one at console.x.ai
    metadata={"user_id": "u_123"},    # optional extra metadata
)

print(result["cid"])          # v1::a3f2b1... — use this for search
print(result["description"])  # "A photograph of a whiteboard showing..."
print(result["content_cid"])  # sha256:abc123... — integrity check
print(result["filename"])     # "photo.jpg"

# Search by what's in the image later:
results = client.query("whiteboard diagram with architecture")
`}</Code>

      <Table
        headers={["Parameter", "Type", "Description"]}
        rows={[
          [<Ic key="s">source</Ic>, "str | Path | bytes", "Image file path or raw bytes"],
          [<Ic key="xai">xai_api_key</Ic>, "str", "xAI API key for Grok Vision (required)"],
          [<Ic key="mt">mime_type</Ic>, "str | None", "MIME type e.g. \"image/jpeg\" — auto-detected from extension if omitted"],
          [<Ic key="m">metadata</Ic>, "dict | None", "Optional extra metadata"],
        ]}
      />
      <P>
        <strong className="text-white">Returns:</strong> dict with <Ic>cid</Ic>, <Ic>description</Ic>, <Ic>content_cid</Ic>, <Ic>filename</Ic>
        <br />
        <strong className="text-white">Raises:</strong>{" "}
        <Ic>MinerOfflineError</Ic>, <Ic>IngestError</Ic>, <Ic>RuntimeError</Ic> (Grok API failure)
      </P>
      <Note>
        Get a free xAI API key at <strong>console.x.ai</strong>. Grok Vision supports JPEG, PNG, GIF, and WebP.
      </Note>

      <H2 id="ingest-pdf">ingest_pdf()</H2>
      <P>
        Extract text from a PDF and store it as a searchable memory. Requires <Ic>pypdf</Ic>.
        The full text (up to 8192 chars) is embedded; the SHA-256 of the raw PDF is stored as <Ic>content_cid</Ic>.
      </P>
      <Code lang="bash">{`pip install pypdf`}</Code>
      <Code lang="python">{`result = client.ingest_pdf(
    "research_paper.pdf",             # path, or raw bytes
    metadata={"category": "research"},
)

print(result["cid"])          # v1::...
print(result["pages"])        # 12
print(result["chars"])        # 48293
print(result["content_cid"])  # sha256:...

# Search the PDF content later:
results = client.query("transformer attention mechanism")
`}</Code>

      <Table
        headers={["Parameter", "Type", "Description"]}
        rows={[
          [<Ic key="s">source</Ic>, "str | Path | bytes", "PDF file path or raw bytes"],
          [<Ic key="m">metadata</Ic>, "dict | None", "Optional extra metadata"],
        ]}
      />
      <P>
        <strong className="text-white">Returns:</strong> dict with <Ic>cid</Ic>, <Ic>pages</Ic>, <Ic>chars</Ic>, <Ic>content_cid</Ic>, <Ic>filename</Ic>
        <br />
        <strong className="text-white">Raises:</strong>{" "}
        <Ic>MinerOfflineError</Ic>, <Ic>IngestError</Ic>, <Ic>ImportError</Ic> (pypdf missing), <Ic>ValueError</Ic> (image-only PDF)
      </P>
      <Note>
        Image-only / scanned PDFs have no extractable text. Run OCR first (e.g. <Ic>pytesseract</Ic>) or use <Ic>ingest_image()</Ic> per page.
      </Note>

      <H2 id="query">query()</H2>
      <Code lang="python">{`results: list[dict] = client.query(text: str, top_k: int = 10)`}</Code>
      <P>Semantic search over the miner's stored embeddings — works across text, images, and PDFs.</P>
      <Code lang="python">{`results = client.query("how does self-attention work?", top_k=10)
# [
#   {"cid": "v1::a3f2b1...", "score": 0.9821, "metadata": {"source": "arxiv"}},
#   {"cid": "v1::b2e8c1...", "score": 0.8847, "metadata": {"type": "image"}},
# ]`}</Code>

      <H2 id="batch">batch_ingest_file()</H2>
      <P>Ingest all records from a JSONL file. Each line must be a JSON object with a <Ic>text</Ic> key.</P>
      <Code lang="python">{`# data.jsonl format:
# {"text": "First entry"}
# {"text": "Second entry", "metadata": {"category": "ml"}}

cids = client.batch_ingest_file("data/corpus.jsonl")
print(f"Ingested {len(cids)} records")

# With error tracking
cids, errors = client.batch_ingest_file("corpus.jsonl", return_errors=True)
for err in errors:
    print(f"Skipped: {err}")`}</Code>

      <H2 id="health">health() / is_online()</H2>
      <Code lang="python">{`# Check liveness — raises MinerOfflineError if unreachable
info = client.health()
# {"status": "ok", "vectors": 42156, "uid": 7}

# Safe check — never raises
if client.is_online():
    cid = client.ingest("...")`}</Code>

      <H2 id="multi-miner">Multi-miner pattern</H2>
      <P>For redundancy, ingest to multiple miners. The same text always produces the same CID.</P>
      <Code lang="python">{`from engram.sdk import EngramClient, MinerOfflineError

miners = [
    EngramClient("http://miner1:8091"),
    EngramClient("http://miner2:8091"),
    EngramClient("http://miner3:8091"),
]

cids = []
for miner in miners:
    try:
        cids.append(miner.ingest("Critical knowledge."))
    except MinerOfflineError:
        print(f"Miner offline: {miner.miner_url}")

print(f"Stored on {len(cids)}/3 miners")`}</Code>

      <Note>
        The same text always produces the same CID across every miner — CIDs are content-addressed, not location-addressed.
      </Note>
    </DocPage>
  );
}
