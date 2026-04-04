"use client";
import { DocPage, H1, H2, Lead, Code, Table, Note, Ic } from "../ui";

export default function CLIPage() {
  return (
    <DocPage
      prev={{ href: "/docs/sdk-errors", label: "Exceptions" }}
      next={{ href: "/docs/miner", label: "Run a Miner" }}
      toc={[
        { id: "install", label: "Install" },
        { id: "ingest", label: "engram ingest" },
        { id: "query", label: "engram query" },
        { id: "status", label: "engram status" },
        { id: "env", label: "Environment variables" },
      ]}
    >
      <H1>CLI Reference</H1>
      <Lead>The <Ic>engram</Ic> CLI provides a local interface for ingesting text, querying the store, and checking subnet status.</Lead>

      <H2 id="install">Install</H2>
      <Code lang="bash">{`pip install engram-subnet
engram --help`}</Code>

      <Note type="tip">
        The CLI defaults to a local FAISS store and sentence-transformers embedder. No OpenAI key or running miner needed.
      </Note>

      <H2 id="ingest">engram ingest</H2>
      <Code lang="bash">{`# Ingest a string
engram ingest "The transformer architecture changed everything."

# With metadata
engram ingest "BERT uses bidirectional representations." --meta '{"source":"arxiv"}'

# From a JSONL file
engram ingest --file data/corpus.jsonl

# Ingest an entire directory recursively
engram ingest --dir ./docs

# Custom source label
engram ingest "My note" --source personal-notes`}</Code>

      <Table
        headers={["Flag", "Description"]}
        rows={[
          ["TEXT", "Text to embed and store (positional)"],
          ["--file, -f PATH", "Path to a .txt or .jsonl file"],
          ["--dir PATH", "Recursively ingest all .txt files in a directory"],
          ["--meta, -m JSON", "JSON metadata string (default {})"],
          ["--source, -s STR", 'Source label added to metadata (default "cli")'],
        ]}
      />

      <H2 id="query">engram query</H2>
      <Code lang="bash">{`engram query "how does self-attention work?"
engram query "neural network training" --top-k 10
engram query "vector databases" --meta`}</Code>

      <Table
        headers={["Flag", "Description"]}
        rows={[
          ["TEXT", "Search query (required)"],
          ["--top-k, -k INT", "Number of results to return (default 5)"],
          ["--meta", "Show metadata column in results table"],
        ]}
      />

      <H2 id="status">engram status</H2>
      <Code lang="bash">{`# Local store status
engram status

# Live metagraph — connects to chain and probes all miners
engram status --live
engram status --live --netuid 42`}</Code>

      <Table
        headers={["Flag", "Description"]}
        rows={[
          ["--live, -l", "Fetch live data from chain and probe all miners"],
          ["--netuid INT", "Subnet UID (overrides NETUID env var)"],
        ]}
      />

      <H2 id="env">Environment variables</H2>
      <Table
        headers={["Variable", "Default", "Description"]}
        rows={[
          ["FAISS_INDEX_PATH", "./data/engram.index", "Local FAISS index file path"],
          ["USE_LOCAL_EMBEDDER", "true", "Use sentence-transformers (no API key needed)"],
          ["OPENAI_API_KEY", "—", "Required if USE_LOCAL_EMBEDDER=false"],
          ["SUBTENSOR_NETWORK", "—", "Network for --live (test, finney, ws://...)"],
          ["NETUID", "99", "Default subnet UID"],
          ["WALLET_NAME", "default", "Wallet coldkey name"],
          ["WALLET_HOTKEY", "default", "Wallet hotkey name"],
        ]}
      />
    </DocPage>
  );
}
