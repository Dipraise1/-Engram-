import type { Metadata } from "next";
import { DocPage, H1, H2, H3, Lead, Ic as Code, CodeBlock, Note, Step, Steps } from "../ui";

export const metadata: Metadata = {
  title: "Memory AI — Engram AI that never forgets",
  description:
    "How Engram's AI chat works: permanent per-user memory stored as vector embeddings on Bittensor, recalled by semantic similarity across all sessions.",
  alternates: { canonical: "https://theengram.space/docs/memory-ai" },
  openGraph: {
    title: "Memory AI | Engram Docs",
    description: "Build AI that permanently remembers users — powered by Engram on Bittensor.",
    url: "https://theengram.space/docs/memory-ai",
  },
};

export default function MemoryAIPage() {
  return (
    <DocPage
      prev={{ href: "/docs/namespaces", label: "Private Namespaces" }}
      next={{ href: "/docs/sdk", label: "Python SDK" }}
    >
      <H1>Memory AI</H1>
      <Lead>
        Engram&apos;s <strong>/memory</strong> page is a live demo of an AI that never forgets.
        Every message you send is permanently stored as a vector embedding on the Engram
        decentralized network, recalled by semantic similarity across all your future sessions.
      </Lead>

      <Note>
        Try it now at{" "}
        <a href="/memory" className="text-[#e040fb] hover:underline">
          theengram.space/memory
        </a>{" "}
        — no account required.
      </Note>

      {/* ── How it works ─────────────────────────────────────────────────────── */}
      <H2>How it works</H2>
      <p className="text-[#a89ab8] leading-relaxed mb-4">
        Every conversation turn goes through four steps before the AI replies:
      </p>

      <Steps>
        <Step n={1} title="Your message is embedded">
          The text is converted into a 384-dimensional vector using{" "}
          <Code>all-MiniLM-L6-v2</Code> running on the Engram miner. This turns meaning
          into math that can be compared to other memories.
        </Step>
        <Step n={2} title="Similar past memories are recalled">
          The embedding is used to search the Engram network for the most semantically
          similar things you&apos;ve said or the AI has replied — across all your previous
          sessions. Only your own memories are returned (session-isolated).
        </Step>
        <Step n={3} title="Memories are injected into context">
          Up to 12 recalled memories are included in the AI&apos;s system prompt as
          factual past conversation excerpts. The AI is instructed to treat them as real
          and answer accordingly.
        </Step>
        <Step n={4} title="Both turns are permanently stored">
          Your message and the AI&apos;s response are both stored on Engram with a{" "}
          <Code>v1::...</Code> content-addressed CID. They live on the decentralized
          network indefinitely — not in a database you own.
        </Step>
      </Steps>

      {/* ── Session identity ─────────────────────────────────────────────────── */}
      <H2>Your identity — no login required</H2>
      <p className="text-[#a89ab8] leading-relaxed mb-4">
        Engram uses a stable anonymous UUID stored in your browser&apos;s{" "}
        <Code>localStorage</Code> as your identity. No account, no email, no wallet needed.
      </p>

      <CodeBlock lang="js" code={`// Your ID lives here — never leaves your browser
localStorage.getItem("engram_session")
// → "s_m3x7k2_abc9f1..."`} />

      <p className="text-[#a89ab8] leading-relaxed mt-4 mb-4">
        This ID is used to:
      </p>
      <ul className="list-disc list-inside space-y-1.5 text-[#a89ab8] text-sm mb-6 ml-2">
        <li>Tag every message stored on Engram with your session</li>
        <li>Filter recalled memories so you never see another user&apos;s data</li>
        <li>Load your full chat history from the server on any new visit</li>
        <li>Generate shareable read-only links to your conversations</li>
      </ul>

      <Note type="warn">
        Your chats are tied to this UUID. If you clear <Code>localStorage</Code> or switch
        browsers without copying your ID, you start fresh. See{" "}
        <strong>Cross-device sync</strong> below.
      </Note>

      {/* ── Chat history persistence ──────────────────────────────────────────── */}
      <H2>Chat history persistence</H2>
      <p className="text-[#a89ab8] leading-relaxed mb-4">
        Messages are saved in two places simultaneously so your history is never lost:
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        <div className="bg-[#0e0b12] border border-[#1e1525] rounded-xl p-4">
          <div className="text-[#e040fb] font-semibold text-sm mb-1">localStorage (instant)</div>
          <p className="text-[#6b5a7e] text-xs leading-relaxed">
            Every message is written to your browser cache immediately. This is what you
            see when you open the page — no loading delay.
          </p>
        </div>
        <div className="bg-[#0e0b12] border border-[#1e1525] rounded-xl p-4">
          <div className="text-[#e040fb] font-semibold text-sm mb-1">VPS SQLite (durable)</div>
          <p className="text-[#6b5a7e] text-xs leading-relaxed">
            Messages are synced to a SQLite database on the Engram server. This survives
            browser cache clears, private mode, and device switches.
          </p>
        </div>
      </div>

      <p className="text-[#a89ab8] leading-relaxed mb-4">
        When you load the page, the server copy wins if it has more messages than your
        local cache — for example after visiting from a different device.
      </p>

      {/* ── Cross-device sync ──────────────────────────────────────────────────── */}
      <H2>Cross-device sync</H2>
      <p className="text-[#a89ab8] leading-relaxed mb-4">
        To continue your conversation on a different device or browser, copy your session ID
        from the original browser and paste it into the new one:
      </p>

      <CodeBlock lang="js" code={`// On your original browser — open DevTools console:
localStorage.getItem("engram_session")
// Copy the result, e.g. "s_m3x7k2_abc9f1..."

// On your new browser — paste it:
localStorage.setItem("engram_session", "s_m3x7k2_abc9f1...")
// Reload the page — your history loads from the server.`} />

      {/* ── Sharing chats ─────────────────────────────────────────────────────── */}
      <H2>Sharing a conversation</H2>
      <p className="text-[#a89ab8] leading-relaxed mb-4">
        Click the <strong>Share</strong> button in the top-right of the chat to copy a
        read-only link. The full conversation is base64-encoded into the URL — no server
        needed, works anywhere.
      </p>

      <CodeBlock lang="bash" code={`# Share URL format
https://theengram.space/memory?view=eyJyIjoie...

# Anyone who opens this sees a read-only replay of the chat
# with a "Start your own" button to begin their own session`} />

      {/* ── Chat folders ─────────────────────────────────────────────────────── */}
      <H2>Chat history folders</H2>
      <p className="text-[#a89ab8] leading-relaxed mb-4">
        The chat interface groups your messages into date sections — <strong>Today</strong>,{" "}
        <strong>Yesterday</strong>, and then by calendar date for older conversations.
        Each section is collapsible. This makes it easy to find a specific conversation
        without scrolling through everything.
      </p>

      {/* ── Building with it ──────────────────────────────────────────────────── */}
      <H2>Build your own memory-powered AI</H2>
      <p className="text-[#a89ab8] leading-relaxed mb-4">
        The full stack is open source. The key pieces are:
      </p>

      <H3>1. Store a message on Engram</H3>
      <CodeBlock lang="python" code={`from engram.sdk import EngramClient

client = EngramClient("http://your-miner:8091")

# Store a user message with session metadata
cid = client.ingest(
    "I'm 22 years old and I built Engram",
    metadata={
        "role": "user",
        "session": "s_m3x7k2_abc9f1",
        "text": "I'm 22 years old and I built Engram",
    }
)
print(cid)  # v1::a3f9...`} />

      <H3>2. Recall memories before generating a reply</H3>
      <CodeBlock lang="python" code={`# Query for semantically related past messages
results = client.query("how old are you", top_k=30)

# Filter to this user's session only
session_memories = [
    r for r in results
    if r["metadata"].get("session") == "s_m3x7k2_abc9f1"
    and r["metadata"].get("text")
][:12]

# Build context
memory_lines = [
    f"[{r['metadata']['role'].title()}]: {r['metadata']['text']}"
    for r in session_memories
]
context = "\\n".join(memory_lines)`} />

      <H3>3. Inject into your LLM call</H3>
      <CodeBlock lang="python" code={`import anthropic  # or openai, xai, etc.

client_ai = anthropic.Anthropic()

system = f"""You are a memory-powered AI assistant.
You have access to the user's past conversation history:

{context}

Treat these as real facts. Never deny knowing something that appears above."""

response = client_ai.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    system=system,
    messages=[{"role": "user", "content": user_message}]
)`} />

      <H3>4. Store the AI response too</H3>
      <CodeBlock lang="python" code={`reply_text = response.content[0].text

# Store so it can be recalled in future turns
cid = client.ingest(
    reply_text,
    metadata={
        "role": "assistant",
        "session": "s_m3x7k2_abc9f1",
        "text": reply_text[:500],
    }
)`} />

      {/* ── Privacy ───────────────────────────────────────────────────────────── */}
      <H2>Privacy & data ownership</H2>
      <ul className="list-disc list-inside space-y-2 text-[#a89ab8] text-sm mb-6 ml-2">
        <li>
          <strong className="text-white">Session isolation:</strong> Engram returns up to 40
          candidate memories per query but only those matching your session ID reach the AI.
          Other users&apos; memories are discarded server-side before context injection.
        </li>
        <li>
          <strong className="text-white">Decentralized storage:</strong> Messages are stored
          as vector embeddings across Bittensor miners — not in a central database controlled
          by Engram or any single entity.
        </li>
        <li>
          <strong className="text-white">No PII required:</strong> Your identity is an
          anonymous UUID. No email, name, or wallet address is ever requested or stored.
        </li>
        <li>
          <strong className="text-white">Sensitive data:</strong> For production use cases
          involving sensitive information, use{" "}
          <a href="/docs/namespaces" className="text-[#e040fb] hover:underline">
            Private Namespaces
          </a>{" "}
          which encrypt your data with a PBKDF2-derived key before storing on miners.
        </li>
      </ul>

      <Note>
        The memory AI demo at <Code>/memory</Code> is built entirely with open-source
        components. View the full source in the{" "}
        <a
          href="https://github.com/Dipraise1/-Engram-"
          className="text-[#e040fb] hover:underline"
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub repo
        </a>{" "}
        under <Code>engram-web/app/memory/</Code> and{" "}
        <Code>engram-web/app/api/chat/</Code>.
      </Note>
    </DocPage>
  );
}
