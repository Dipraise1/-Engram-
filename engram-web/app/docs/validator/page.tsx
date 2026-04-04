"use client";
import { DocPage, H1, H2, Lead, Code, Table, Note, Steps, Ic } from "../_components";

export default function ValidatorPage() {
  return (
    <DocPage
      prev={{ href: "/docs/miner", label: "Run a Miner" }}
      next={{ href: "/docs/protocol", label: "Protocol Reference" }}
      toc={[
        { id: "setup", label: "Setup" },
        { id: "scoring", label: "Scoring" },
        { id: "config", label: "Configuration" },
      ]}
    >
      <H1>Run a Validator</H1>
      <Lead>Validators score miners by issuing storage-proof challenges and measuring recall accuracy, latency, and proof success rate.</Lead>

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
            title: "Create wallet",
            code: `btcli wallet new_coldkey --wallet.name engram
btcli wallet new_hotkey --wallet.name engram --wallet.hotkey validator`,
          },
          {
            title: "Register on subnet",
            code: `btcli subnet register --netuid 42 --wallet.name engram --wallet.hotkey validator --subtensor.network test`,
          },
          {
            title: "Generate ground truth corpus",
            desc: "The validator needs a local corpus to issue recall challenges.",
            code: `USE_LOCAL_EMBEDDER=true python scripts/generate_ground_truth.py --count 1000`,
          },
          {
            title: "Start validator",
            code: `python neurons/validator.py --wallet.name engram --wallet.hotkey validator --netuid 42`,
          },
        ]}
      />

      <H2 id="scoring">Scoring loop</H2>
      <P>The validator runs a loop every 120 seconds:</P>
      <div className="space-y-2 my-5">
        {[
          ["Sync metagraph", "Fetch current neuron list and axon IPs from the chain."],
          ["Issue challenges", "Send random CIDs from the ground truth corpus to each miner and verify the returned vectors match."],
          ["Measure latency", "Record round-trip time for each challenge response."],
          ["Compute scores", "Composite score = 0.50 × recall@10 + 0.30 × latency_score + 0.20 × proof_success_rate."],
          ["Set weights", "Commit normalized scores to the chain via substrate extrinsic every 600 seconds."],
        ].map(([step, desc], i) => (
          <div key={step} className="flex gap-4 px-4 py-3 rounded-xl border border-[#1e1525] bg-[#0a0810]">
            <span className="text-[11px] font-mono text-[#e040fb] w-4 flex-shrink-0 mt-0.5">{String(i + 1).padStart(2, "0")}</span>
            <div>
              <span className="text-[14px] font-semibold text-white">{step} — </span>
              <span className="text-[13px] text-[#6b5a7e]">{desc}</span>
            </div>
          </div>
        ))}
      </div>

      <Code lang="bash" title="Scoring formula">{`composite_score = (
    0.50 * recall_at_10
  + 0.30 * latency_score   # 1.0 at ≤100ms, 0.0 at ≥500ms
  + 0.20 * proof_success_rate
)

# Miners below 50% proof success rate receive weight 0`}</Code>

      <H2 id="config">Configuration</H2>
      <Table
        headers={["Variable", "Default", "Description"]}
        rows={[
          ["NETUID", "42", "Subnet UID"],
          ["SUBTENSOR_NETWORK", "test", "Network to connect to"],
          ["WALLET_NAME", "engram", "Validator coldkey"],
          ["WALLET_HOTKEY", "validator", "Validator hotkey"],
          ["SCORING_INTERVAL", "120", "Seconds between scoring rounds"],
          ["WEIGHT_INTERVAL", "600", "Seconds between weight-setting on chain"],
          ["CHALLENGE_SAMPLE_SIZE", "10", "CIDs per miner per round"],
          ["MIN_PROOF_RATE", "0.50", "Proof success rate below which weight = 0"],
        ]}
      />

      <Note type="warn">
        Validators require a minimum stake to set weights on chain. Check the current minimum with <Ic>btcli subnet show --netuid 42</Ic>.
      </Note>
    </DocPage>
  );
}
