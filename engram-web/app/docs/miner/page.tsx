import type { Metadata } from "next";
import { DocPage, H1, H2, Lead, P, Code, Table, Note, Steps, Ic } from "../ui";

export const metadata: Metadata = {
  title: "Run a Miner",
  description:
    "Step-by-step guide to running an Engram miner node on Bittensor subnet 450. Covers wallet setup, registration, configuration, and earning TAO rewards.",
  alternates: { canonical: "https://theengram.space/docs/miner" },
  openGraph: {
    title: "Run an Engram Miner",
    description: "Wallet setup, registration on subnet 450, and start earning TAO as a miner.",
    url: "https://theengram.space/docs/miner",
  },
};

export default function MinerPage() {
  return (
    <DocPage
      prev={{ href: "/docs/cli", label: "CLI Reference" }}
      next={{ href: "/docs/validator", label: "Run a Validator" }}
      toc={[
        { id: "requirements", label: "Requirements" },
        { id: "setup", label: "Setup" },
        { id: "config", label: "Configuration" },
        { id: "start", label: "Start" },
        { id: "monitoring", label: "Monitoring" },
      ]}
    >
      <H1>Run a Miner</H1>
      <Lead>Miners store embedding vectors in a FAISS index and serve them to validators and SDK clients. They earn TAO for provably holding the data.</Lead>

      <H2 id="requirements">Requirements</H2>
      <div className="grid grid-cols-2 gap-3 my-5">
        {[
          ["CPU", "4+ cores"],
          ["RAM", "8 GB minimum"],
          ["Storage", "50 GB SSD"],
          ["Python", "3.10 or higher"],
          ["Network", "Static IP recommended"],
          ["TAO", "0.001 τ minimum stake"],
        ].map(([k, v]) => (
          <div key={k} className="flex justify-between px-4 py-2.5 rounded-lg border border-[#1e1525] bg-[#0e0b12]">
            <span className="text-[12px] text-[#6b5a7e]">{k}</span>
            <span className="text-[12px] font-mono text-white">{v}</span>
          </div>
        ))}
      </div>

      <H2 id="setup">Setup</H2>
      <Steps
        steps={[
          {
            title: "Clone and install",
            code: `git clone https://github.com/Dipraise1/-Engram-.git
cd -Engram-
pip install -e .`,
          },
          {
            title: "Create a wallet",
            code: `btcli wallet new_coldkey --wallet.name engram
btcli wallet new_hotkey --wallet.name engram --wallet.hotkey miner`,
          },
          {
            title: "Get testnet TAO",
            desc: "Request test tokens from the faucet or transfer from an existing wallet.",
            code: `btcli wallet faucet --wallet.name engram --subtensor.network test`,
          },
          {
            title: "Register on the subnet",
            code: `btcli subnet register --netuid 42 --wallet.name engram --wallet.hotkey miner --subtensor.network test`,
          },
          {
            title: "Configure .env",
            code: `cp .env.example .env
# Edit these values:
WALLET_NAME=engram
WALLET_HOTKEY=miner
NETUID=42
SUBTENSOR_NETWORK=test
USE_LOCAL_EMBEDDER=true`,
          },
          {
            title: "Start the miner",
            code: `python neurons/miner.py --wallet.name engram --wallet.hotkey miner --netuid 42`,
          },
        ]}
      />

      <H2 id="config">Configuration</H2>
      <Table
        headers={["Variable", "Default", "Description"]}
        rows={[
          ["NETUID", "42", "Subnet UID"],
          ["SUBTENSOR_NETWORK", "test", "test | finney | ws://..."],
          ["WALLET_NAME", "engram", "Coldkey wallet name"],
          ["WALLET_HOTKEY", "miner", "Hotkey name"],
          ["MINER_PORT", "8091", "HTTP server port"],
          ["MINER_IP", "0.0.0.0", "Bind address"],
          ["USE_LOCAL_EMBEDDER", "true", "true = sentence-transformers, false = OpenAI"],
          ["OPENAI_API_KEY", "—", "Required if USE_LOCAL_EMBEDDER=false"],
          ["FAISS_INDEX_PATH", "./data/engram.index", "Vector index persistence path"],
          ["MAX_TEXT_LENGTH", "8192", "Max chars per ingest request"],
          ["RATE_LIMIT_RPM", "60", "Max requests per minute per hotkey"],
          ["MIN_STAKE_TAO", "0.001", "Min stake to pass the stake check"],
        ]}
      />

      <H2 id="start">Start as a service</H2>
      <P>For production, run the miner as a systemd service so it restarts on failure:</P>
      <Code lang="bash" title="/etc/systemd/system/engram-miner.service">{`[Unit]
Description=Engram Miner
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/-Engram-
Environment=PATH=/home/ubuntu/-Engram-/.venv/bin
ExecStart=python neurons/miner.py --wallet.name engram --wallet.hotkey miner --netuid 42
Restart=on-failure

[Install]
WantedBy=multi-user.target`}</Code>
      <Code lang="bash">{`systemctl daemon-reload
systemctl enable engram-miner
systemctl start engram-miner`}</Code>

      <H2 id="monitoring">Monitoring</H2>
      <Code lang="bash">{`# View logs
journalctl -u engram-miner -f

# Check wallet stats
engram wallet-stats

# Check your miner's score
engram status --live --netuid 42`}</Code>

      <Note type="warn">
        Keep your hotkey registered on-chain and ensure the miner is reachable from the internet. Validators that can't reach your axon will give you a score of 0.
      </Note>
    </DocPage>
  );
}
