"use client";
import { DocPage, H1, H2, Lead, Code, Table, Ic } from "../ui";

export default function ErrorsPage() {
  return (
    <DocPage
      prev={{ href: "/docs/sdk-llama", label: "LlamaIndex" }}
      next={{ href: "/docs/cli", label: "CLI Reference" }}
      toc={[
        { id: "hierarchy", label: "Hierarchy" },
        { id: "handling", label: "Error handling" },
      ]}
    >
      <H1>Exceptions</H1>
      <Lead>All SDK exceptions inherit from <Ic>EngramError</Ic> and include a human-readable message explaining what to do.</Lead>

      <H2 id="hierarchy">Exception hierarchy</H2>
      <Code lang="python">{`from engram.sdk import (
    EngramError,        # base class
    MinerOfflineError,  # miner is unreachable
    IngestError,        # miner rejected the ingest
    QueryError,         # query failed on the miner
    InvalidCIDError,    # malformed CID returned
)`}</Code>

      <Table
        headers={["Exception", "When raised", "Common cause"]}
        rows={[
          [<Ic key="1">MinerOfflineError</Ic>, "Connection refused or timeout", "Miner not running — start with python neurons/miner.py"],
          [<Ic key="2">IngestError</Ic>, "Miner rejected the request", "Rate limit, low stake, or text too long"],
          [<Ic key="3">QueryError</Ic>, "Query failed on the miner", "Store empty or miner error"],
          [<Ic key="4">InvalidCIDError</Ic>, "Malformed CID returned", "Miner-side bug — check miner logs"],
        ]}
      />

      <H2 id="handling">Error handling</H2>
      <Code lang="python">{`from engram.sdk import EngramClient, MinerOfflineError, IngestError, QueryError

client = EngramClient("http://127.0.0.1:8091")

# Ingest with handling
try:
    cid = client.ingest("Some important text")
except MinerOfflineError as e:
    print(f"Miner is down: {e}")
    # → Can't reach the miner at http://127.0.0.1:8091
    #   Start it with: python neurons/miner.py
except IngestError as e:
    print(f"Ingest rejected: {e}")
    # → Slow down — you've sent 12 requests in the last 60s.

# Query with handling
try:
    results = client.query("transformers")
except MinerOfflineError:
    results = []  # fallback to cache or empty
except QueryError as e:
    print(f"Query failed: {e}")`}</Code>
    </DocPage>
  );
}
