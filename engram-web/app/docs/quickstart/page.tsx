"use client";
import { DocPage, H1, H2, Lead, P, Code, Note, Steps, Ic } from "../ui";

export default function QuickStart() {
  return (
    <DocPage
      prev={{ href: "/docs", label: "Introduction" }}
      next={{ href: "/docs/sdk", label: "Python SDK" }}
      toc={[
        { id: "install", label: "Install" },
        { id: "configure", label: "Configure" },
        { id: "ingest", label: "Ingest text" },
        { id: "query", label: "Query" },
        { id: "cli", label: "Try the CLI" },
      ]}
    >
      <H1>Quick Start</H1>
      <Lead>Get from zero to your first semantic query in under 2 minutes.</Lead>

      <Steps
        steps={[
          {
            title: "Install",
            desc: "Install the engram-subnet package from PyPI.",
            code: `pip install engram-subnet`,
            lang: "bash",
          },
          {
            title: "Configure (optional)",
            desc: "Copy the example env file and edit it. Defaults work out of the box with a local embedder.",
            code: `cp .env.example .env
# USE_LOCAL_EMBEDDER=true  ← no API key needed`,
            lang: "bash",
          },
          {
            title: "Ingest your first text",
            code: `from engram.sdk import EngramClient

client = EngramClient("http://127.0.0.1:8091")
cid = client.ingest("The transformer architecture changed everything.")
print(cid)  # v1::a3f2b1...`,
            lang: "python",
          },
          {
            title: "Run a semantic query",
            code: `results = client.query("how does attention work?", top_k=5)

for r in results:
    print(f"{r['score']:.4f}  {r['cid']}")`,
            lang: "python",
          },
        ]}
      />

      <H2 id="configure">Configuration</H2>
      <P>All config is read from a <Ic>.env</Ic> file in the working directory:</P>
      <Code lang="bash" title=".env">{`# Embedder
USE_LOCAL_EMBEDDER=true       # no API key needed
# OPENAI_API_KEY=sk-...       # set this if USE_LOCAL_EMBEDDER=false

# Network
SUBTENSOR_NETWORK=test        # test | finney | ws://...
NETUID=42

# Wallet (for running a miner/validator)
WALLET_NAME=engram
WALLET_HOTKEY=miner

# Storage
FAISS_INDEX_PATH=./data/engram.index`}</Code>

      <H2 id="ingest">Ingest text</H2>
      <P>The SDK embeds the text, assigns a CID, and stores it on the miner's FAISS index.</P>
      <Code lang="python">{`# Basic ingest
cid = client.ingest("BERT uses bidirectional encoder representations.")

# With metadata
cid = client.ingest(
    "GPT generates text autoregressively.",
    metadata={"source": "arxiv", "year": "2017"}
)

# Batch ingest from JSONL
cids = client.batch_ingest_file("data/corpus.jsonl")`}</Code>

      <Note type="info">
        The CID is deterministically derived from the embedding — the same text always produces the same CID regardless of which miner stores it.
      </Note>

      <H2 id="query">Query</H2>
      <Code lang="python">{`results = client.query("attention mechanisms", top_k=10)
# [
#   {"cid": "v1::a3f2b1...", "score": 0.9821, "metadata": {"source": "arxiv"}},
#   {"cid": "v1::b2e8c1...", "score": 0.8847, "metadata": {}},
#   ...
# ]`}</Code>

      <H2 id="cli">Try the CLI</H2>
      <Code lang="bash">{`# Ingest
engram ingest "Some important knowledge"
engram ingest --file corpus.jsonl

# Query
engram query "what is self-attention?"

# Status
engram status`}</Code>

      <Note type="tip">
        Run <Ic>engram demo</Ic> for a full end-to-end demo — seeds a corpus, ingests it, runs queries, and prints scores.
      </Note>
    </DocPage>
  );
}
