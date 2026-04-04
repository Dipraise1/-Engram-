"use client";
import { DocPage, H1, H2, H3, Lead, P, Code, Note, Table, Ic } from "../_components";

export default function SDKPage() {
  return (
    <DocPage
      prev={{ href: "/docs/quickstart", label: "Quick Start" }}
      next={{ href: "/docs/sdk-langchain", label: "LangChain" }}
      toc={[
        { id: "install", label: "Install" },
        { id: "client", label: "EngramClient" },
        { id: "ingest", label: "ingest()" },
        { id: "query", label: "query()" },
        { id: "batch", label: "batch_ingest_file()" },
        { id: "health", label: "health() / is_online()" },
        { id: "multi-miner", label: "Multi-miner pattern" },
      ]}
    >
      <H1>Python SDK</H1>
      <Lead>
        <Ic>EngramClient</Ic> is a lightweight HTTP client for a single Engram miner. No extra dependencies — uses only stdlib <Ic>urllib</Ic>.
      </Lead>

      <H2 id="install">Install</H2>
      <Code lang="bash">{`pip install engram-subnet`}</Code>

      <H2 id="client">EngramClient</H2>
      <Code lang="python">{`from engram.sdk import EngramClient

client = EngramClient(
    miner_url="http://127.0.0.1:8091",
    timeout=30.0,
)`}</Code>

      <Table
        headers={["Parameter", "Type", "Default", "Description"]}
        rows={[
          [<Ic key="mu">miner_url</Ic>, "str", '"http://127.0.0.1:8091"', "Base URL of the miner's HTTP server"],
          [<Ic key="to">timeout</Ic>, "float", "30.0", "Request timeout in seconds"],
        ]}
      />

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

      <H2 id="query">query()</H2>
      <Code lang="python">{`results: list[dict] = client.query(text: str, top_k: int = 10)`}</Code>
      <P>Semantic search over the miner's stored embeddings.</P>
      <Code lang="python">{`results = client.query("how does self-attention work?", top_k=10)
# [
#   {"cid": "v1::a3f2b1...", "score": 0.9821, "metadata": {"source": "arxiv"}},
#   {"cid": "v1::b2e8c1...", "score": 0.8847, "metadata": {}},
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
