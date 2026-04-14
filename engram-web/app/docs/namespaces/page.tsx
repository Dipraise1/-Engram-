import type { Metadata } from "next";
import { DocPage, H1, H2, H3, Lead, P, Code, Note, Table, Ic } from "../ui";

export const metadata: Metadata = {
  title: "Private Namespaces",
  description:
    "Store and search data that only you can read. Engram private namespaces use client-side AES-256-GCM encryption — miners store ciphertext and never see your original text.",
  alternates: { canonical: "https://theengram.space/docs/namespaces" },
  openGraph: {
    title: "Private Namespaces — Engram",
    description:
      "Client-side AES-256-GCM encryption for your vector data. Miners store ciphertext, you hold the keys.",
    url: "https://theengram.space/docs/namespaces",
  },
};

export default function NamespacesPage() {
  return (
    <DocPage
      prev={{ href: "/docs/sdk", label: "EngramClient" }}
      next={{ href: "/docs/attestation", label: "Namespace Attestation" }}
      toc={[
        { id: "overview", label: "Overview" },
        { id: "how-it-works", label: "How it works" },
        { id: "quickstart", label: "Quick start" },
        { id: "encryption", label: "Encryption details" },
        { id: "key-management", label: "Key management" },
        { id: "admin", label: "Admin API" },
        { id: "threat-model", label: "Threat model" },
      ]}
    >
      <H1>Private Namespaces</H1>
      <Lead>
        Store and search data that only you can read. Namespaces are isolated, access-controlled collections
        with <strong className="text-white">client-side AES-256-GCM encryption</strong> — miners store
        ciphertext and never see your original text.
      </Lead>

      <H2 id="overview">Overview</H2>
      <P>
        By default, all data on Engram is public — any miner can serve it and any client can query it.
        Private namespaces change this for use cases where data confidentiality matters:
      </P>

      <Table
        headers={["", "Public (default)", "Private namespace"]}
        rows={[
          ["Access control", "None", "Key required to read/write"],
          ["Data at rest", "Plaintext on miner", "AES-256-GCM encrypted"],
          ["Semantic search", "✓", "✓ (vectors unencrypted, text encrypted)"],
          ["Miner sees text", "Yes", "No — ciphertext only"],
          ["Miner sees vectors", "Yes", "Yes (needed for search)"],
          ["CID format", "v1::sha256…", "v1::sha256… (same)"],
        ]}
      />

      <H2 id="how-it-works">How it works</H2>
      <P>
        When you create an <Ic>EngramClient</Ic> with a <Ic>namespace</Ic> and <Ic>namespace_key</Ic>,
        the client automatically:
      </P>
      <ol className="list-decimal list-inside space-y-2 text-[#c4b5d4] text-[14px] leading-relaxed mb-6">
        <li>Derives an AES-256 encryption key from your namespace key using PBKDF2-HMAC-SHA256 (100k iterations)</li>
        <li>Computes embeddings <strong className="text-white">locally</strong> before sending anything to the network</li>
        <li>Encrypts your text and metadata with AES-256-GCM and a random 12-byte IV per message</li>
        <li>Sends only the <strong className="text-white">float32 vector</strong> + <strong className="text-white">encrypted blob</strong> to the miner</li>
        <li>On query, sends the query vector (computed locally) and decrypts result metadata client-side</li>
      </ol>
      <Note type="tip">
        Miners can serve semantic search because the embedding vectors are unencrypted.
        Your actual text and metadata are never transmitted or stored in plaintext.
      </Note>

      <H2 id="quickstart">Quick start</H2>
      <Code lang="python">{`from engram.sdk import EngramClient

# Create a private client — all data encrypted to this namespace
client = EngramClient(
    "http://miner:8091",
    namespace="acme-docs",
    namespace_key="your-secret-key-min-16-chars",
)

# Store — text is encrypted before leaving your machine
cid = client.ingest("Q4 revenue was $4.2M, up 18% YoY.")
cid2 = client.ingest("Our new product launches March 15th.")

# Search — query vector sent to miner, results decrypted locally
results = client.query("revenue figures")
for r in results:
    print(r["score"], r["metadata"])   # decrypted metadata here`}</Code>

      <Note>
        The first ingest to a new namespace auto-registers it on the miner with a PBKDF2 hash of
        your key. The key itself is never stored anywhere on the network.
      </Note>

      <H3 id="namespacing-separate-teams">Separate teams, separate keys</H3>
      <Code lang="python">{`# Engineering team
eng_client = EngramClient(miner, namespace="eng", namespace_key=ENG_KEY)
eng_client.ingest("Our CI pipeline config and architecture notes.")

# Sales team — completely isolated, different key
sales_client = EngramClient(miner, namespace="sales", namespace_key=SALES_KEY)
sales_client.ingest("Pipeline deal notes — Q1 close expected.")

# Engineering can't see sales data and vice versa
results = eng_client.query("deal notes")  # returns nothing — scoped to 'eng'`}</Code>

      <H2 id="encryption">Encryption details</H2>
      <Table
        headers={["Property", "Value"]}
        rows={[
          ["Algorithm", "AES-256-GCM (authenticated encryption)"],
          ["Key derivation", "PBKDF2-HMAC-SHA256, 100 000 iterations"],
          ["KDF salt", "Namespace name (UTF-8)"],
          ["IV", "Random 12 bytes per message (os.urandom)"],
          ["Auth tag", "16 bytes — detects tampering"],
          ["Wire format", "base64url( IV[12] ‖ ciphertext ‖ tag[16] )"],
          ["Stored as", 'metadata["_enc"] field on the miner'],
          ["Library", "cryptography >= 42.0 (AESGCM)"],
        ]}
      />

      <P>
        Because GCM is an authenticated mode, any attempt to tamper with stored ciphertext is detected
        on decryption and raises a <Ic>ValueError</Ic> rather than silently returning garbage.
      </P>

      <H2 id="key-management">Key management</H2>
      <P>
        Your namespace key never leaves your machine — only a PBKDF2 hash is stored on the miner
        (used to reject requests with wrong keys at the access-control layer).
      </P>

      <H3 id="rotating-keys">Rotating keys</H3>
      <P>
        To rotate a namespace key, use the admin API on localhost. Note that rotating the
        <em> access control</em> key does not re-encrypt existing data — you must re-ingest
        if you also want to change the encryption key.
      </P>
      <Code lang="bash">{`curl -X POST http://localhost:8091/namespace \\
  -H "Content-Type: application/json" \\
  -d '{
    "action": "rotate",
    "namespace": "acme-docs",
    "key": "old-secret-key",
    "new_key": "new-secret-key-min-16-chars"
  }'`}</Code>

      <H3 id="deleting">Deleting a namespace</H3>
      <Code lang="bash">{`curl -X POST http://localhost:8091/namespace \\
  -H "Content-Type: application/json" \\
  -d '{"action": "delete", "namespace": "acme-docs", "key": "your-secret-key"}'`}</Code>
      <Note>
        Deleting a namespace removes access control but does not wipe the encrypted vectors from the
        miner's store. The data remains as unreadable ciphertext until the miner's collection is pruned.
      </Note>

      <H2 id="admin">Admin API</H2>
      <P>
        The <Ic>/namespace</Ic> endpoint is restricted to <Ic>127.0.0.1</Ic> (localhost only).
        It cannot be called from the public internet.
      </P>
      <Table
        headers={["Action", "Required fields", "Description"]}
        rows={[
          ["create", "namespace, key", "Explicitly pre-create a namespace (optional — auto-created on first ingest)"],
          ["delete", "namespace, key", "Remove namespace registration (data remains encrypted on disk)"],
          ["rotate", "namespace, key, new_key", "Change the access-control key (does not re-encrypt stored data)"],
          ["list", "—", "List all registered namespace names (no keys or hashes returned)"],
        ]}
      />
      <Code lang="bash">{`# List namespaces
curl http://localhost:8091/namespace -d '{"action":"list"}' -H "Content-Type: application/json"
# {"namespaces": ["acme-docs", "eng", "sales"]}`}</Code>

      <H2 id="threat-model">Threat model</H2>
      <Table
        headers={["Threat", "Protected?"]}
        rows={[
          ["Miner reads your stored text", "✓ Yes — ciphertext only on disk"],
          ["Miner reads your query text", "✓ Yes — only float vector sent"],
          ["Network eavesdropper reads data in transit", "Partial — use TLS termination for full protection"],
          ["Attacker guesses your namespace key", "✓ Yes — PBKDF2 with 100k iterations makes brute-force expensive"],
          ["Miner tampers with stored data", "✓ Yes — GCM auth tag detects modification"],
          ["Miner returns results from another namespace", "✓ Yes — server-side namespace filter + client-side decryption"],
          ["Someone with the key reads your data", "No — key holders have full access (by design)"],
          ["Miner infers content from embedding vectors", "Partial — vectors encode semantic meaning; use private miner for full isolation"],
        ]}
      />
      <Note type="tip">
        For maximum privacy, run your own miner on private infrastructure. The namespace system
        protects text content from third-party miners, but embedding vectors inherently encode
        semantic information that a sophisticated attacker could analyze.
      </Note>
    </DocPage>
  );
}
