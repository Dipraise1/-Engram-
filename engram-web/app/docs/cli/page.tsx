"use client";
import { DocPage, H1, H2, Lead, Code, Table, Note, Ic } from "../ui";

export default function CLIPage() {
  return (
    <DocPage
      prev={{ href: "/docs/sdk-errors", label: "Exceptions" }}
      next={{ href: "/docs/miner", label: "Run a Miner" }}
      toc={[
        { id: "install", label: "Install" },
        { id: "init", label: "engram init" },
        { id: "ingest", label: "engram ingest" },
        { id: "query", label: "engram query" },
        { id: "status", label: "engram status" },
        { id: "wallet-stats", label: "engram wallet-stats" },
        { id: "env", label: "Environment variables" },
      ]}
    >
      <H1>CLI Reference</H1>
      <Lead>The <Ic>engram</Ic> CLI provides a local interface for setup, ingesting text, querying the store, and checking subnet status.</Lead>

      <H2 id="install">Install</H2>
      <Code lang="bash">{`pip install engram-subnet
engram --help`}</Code>

      <Note type="tip">
        The CLI defaults to a local FAISS store and sentence-transformers embedder. No OpenAI key or running miner needed for basic use.
      </Note>

      <H2 id="init">engram init</H2>
      <p className="text-[#c4b5d4] text-[14px] leading-relaxed mb-4">
        Interactive setup wizard — creates a <Ic>.env</Ic> file and verifies your installation.
        The fastest way to get started.
      </p>
      <Code lang="bash">{`engram init`}</Code>
      <p className="text-[#c4b5d4] text-[14px] leading-relaxed mb-4">
        The wizard asks about your role and writes the right config:
      </p>
      <Code lang="bash">{`$ engram init

╭──────────────────────────────────────────╮
│  Welcome to Engram                        │
│  This wizard will help you set up your   │
│  environment.                             │
╰──────────────────────────────────────────╯

What are you setting up?
  [miner]     Run a miner node and earn TAO
  [validator] Run a validator and set weights
  [dev]       Use the SDK locally
> miner

Subtensor network [finney/test/ws://...]: test
Subnet UID: 450
Wallet name: default
Hotkey name: miner
Your public IP address: 1.2.3.4
...
✓ Written: /your/project/.env

Checking your installation...
  ✓  engram package          installed
  ✓  engram-core (Rust)      built
  ✓  openai                  installed
  ✓  bittensor               installed

Next steps:
  btcli subnet register --netuid 450 ...
  python neurons/miner.py`}</Code>

      <Table
        headers={["Flag", "Description"]}
        rows={[
          ["--role miner|validator|dev", "Skip the role prompt"],
          ["--out PATH", "Output path for .env file (default .env)"],
          ["--force", "Overwrite existing .env without prompting"],
        ]}
      />

      <H2 id="ingest">engram ingest</H2>
      <Code lang="bash">{`# Ingest a string
engram ingest "The transformer architecture changed everything."

# With metadata
engram ingest "BERT uses bidirectional representations." --meta '{"source":"arxiv"}'

# From a JSONL file
engram ingest --file data/corpus.jsonl

# Ingest an entire directory recursively (.txt, .md, .jsonl)
engram ingest --dir ./docs

# Custom source label
engram ingest "My note" --source personal-notes`}</Code>

      <Table
        headers={["Flag", "Description"]}
        rows={[
          ["TEXT", "Text to embed and store (positional)"],
          ["--file, -f PATH", "Path to a .txt or .jsonl file"],
          ["--dir PATH", "Recursively ingest all .txt / .md / .jsonl files"],
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
engram status --live --netuid 450`}</Code>

      <Table
        headers={["Flag", "Description"]}
        rows={[
          ["--live, -l", "Fetch live data from chain and health-check all miners"],
          ["--netuid INT", "Subnet UID (overrides NETUID env var)"],
        ]}
      />

      <H2 id="wallet-stats">engram wallet-stats</H2>
      <Code lang="bash">{`# All wallet activity on this miner
engram wallet-stats

# Single wallet detail
engram wallet-stats 5FHGPfixdXLs...

# With live TAO stake
engram wallet-stats --live --netuid 450`}</Code>

      <H2 id="env">Environment variables</H2>
      <Table
        headers={["Variable", "Default", "Description"]}
        rows={[
          ["FAISS_INDEX_PATH", "./data/engram.index", "Local FAISS index file path"],
          ["USE_LOCAL_EMBEDDER", "true", "Use sentence-transformers (no API key needed)"],
          ["OPENAI_API_KEY", "—", "Required if USE_LOCAL_EMBEDDER=false"],
          ["SUBTENSOR_NETWORK", "—", "Network for --live (test, finney, ws://...)"],
          ["NETUID", "450", "Default subnet UID"],
          ["WALLET_NAME", "default", "Wallet coldkey name"],
          ["WALLET_HOTKEY", "default", "Wallet hotkey name"],
          ["MINER_URL", "http://127.0.0.1:8091", "Miner URL for wallet-stats command"],
        ]}
      />
    </DocPage>
  );
}
