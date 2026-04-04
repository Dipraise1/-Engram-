"""
Phase 8.3 — AI Agent Memory Demo

Shows how to use Engram as persistent memory for AI agents via:
  1. LangChain VectorStore adapter
  2. LlamaIndex VectorStore adapter
  3. Raw EngramClient as a manual memory layer

Prerequisites:
  pip install langchain-core langchain-openai llama-index-core
  python neurons/miner.py &   # miner must be running

Run:
  python scripts/demo_agent_memory.py
"""

import os
import sys
sys.path.insert(0, ".")

MINER_URL = os.getenv("MINER_URL", "http://127.0.0.1:8091")

# ── 1. Raw SDK — manual agent memory ─────────────────────────────────────────

def demo_raw_memory():
    print("\n── Raw SDK memory ────────────────────────────────────────────")
    from engram.sdk import EngramClient

    client = EngramClient(MINER_URL)

    if not client.is_online():
        print(f"  Miner offline at {MINER_URL} — skipping")
        return

    # Agent stores facts it learns
    cid1 = client.ingest("The user prefers concise responses.",    metadata={"type": "preference"})
    cid2 = client.ingest("The user is building a Bittensor subnet.", metadata={"type": "context"})
    cid3 = client.ingest("TAO is the native token of Bittensor.",   metadata={"type": "fact"})
    print(f"  Stored 3 memories:")
    print(f"    {cid1[:30]}…")
    print(f"    {cid2[:30]}…")
    print(f"    {cid3[:30]}…")

    # Agent retrieves relevant context before answering
    results = client.query("what is the user building?", top_k=3)
    print(f"\n  Query: 'what is the user building?'")
    for r in results:
        print(f"    score={r['score']:.4f}  meta={r['metadata']}")

    print("  ✓ Raw SDK demo complete")


# ── 2. LangChain adapter ──────────────────────────────────────────────────────

def demo_langchain():
    print("\n── LangChain VectorStore ─────────────────────────────────────")
    try:
        from langchain_core.documents import Document
    except ImportError:
        print("  langchain-core not installed — skipping (pip install langchain-core)")
        return

    from engram.sdk.langchain import EngramVectorStore

    store = EngramVectorStore(miner_url=MINER_URL)

    if not store.health():
        print(f"  Miner offline at {MINER_URL} — skipping")
        return

    # Store agent observations as LangChain Documents
    docs = [
        Document(page_content="Transformers use self-attention to process sequences.",
                 metadata={"source": "lecture", "topic": "ml"}),
        Document(page_content="BERT is pretrained on masked language modeling.",
                 metadata={"source": "paper", "topic": "nlp"}),
        Document(page_content="GPT generates text autoregressively left-to-right.",
                 metadata={"source": "paper", "topic": "nlp"}),
        Document(page_content="Vector databases store embeddings for fast similarity search.",
                 metadata={"source": "blog", "topic": "infrastructure"}),
    ]

    cids = store.add_documents(docs)
    print(f"  Stored {len(cids)} documents: {[c[:20] + '…' for c in cids]}")

    # Retrieve relevant context
    results = store.similarity_search_with_score("how does BERT work?", k=3)
    print(f"\n  Query: 'how does BERT work?'")
    for doc, score in results:
        print(f"    score={score:.4f}  [{doc.metadata.get('topic')}] {doc.page_content[:60]}")

    print("  ✓ LangChain adapter demo complete")


# ── 3. LlamaIndex adapter ─────────────────────────────────────────────────────

def demo_llama_index():
    print("\n── LlamaIndex VectorStore ────────────────────────────────────")
    try:
        from llama_index.core.schema import TextNode
        from llama_index.core.vector_stores.types import VectorStoreQuery
    except ImportError:
        print("  llama-index-core not installed — skipping (pip install llama-index-core)")
        return

    from engram.sdk.llama_index import EngramVectorStore

    store = EngramVectorStore(miner_url=MINER_URL)

    if not store.health():
        print(f"  Miner offline at {MINER_URL} — skipping")
        return

    # Store nodes
    nodes = [
        TextNode(text="Bittensor is a decentralised ML network.",
                 metadata={"source": "whitepaper"}),
        TextNode(text="TAO tokens are distributed to miners and validators.",
                 metadata={"source": "whitepaper"}),
        TextNode(text="Subnets specialise in different ML tasks.",
                 metadata={"source": "docs"}),
    ]

    cids = store.add(nodes)
    print(f"  Stored {len(cids)} nodes")

    # Query
    query = VectorStoreQuery(query_str="how does Bittensor distribute rewards?", similarity_top_k=3)
    result = store.query(query)
    print(f"\n  Query: 'how does Bittensor distribute rewards?'")
    for node, score in zip(result.nodes, result.similarities):
        print(f"    score={score:.4f}  {node.node.get_content()[:60]}")

    print("  ✓ LlamaIndex adapter demo complete")


# ── 4. RetrievalQA agent pattern (LangChain) ──────────────────────────────────

def demo_retrieval_qa():
    print("\n── LangChain RetrievalQA agent pattern ───────────────────────")
    try:
        from langchain_core.documents import Document
        from langchain_core.prompts import PromptTemplate
    except ImportError:
        print("  langchain-core not installed — skipping")
        return

    from engram.sdk.langchain import EngramVectorStore

    store = EngramVectorStore(miner_url=MINER_URL)
    if not store.health():
        print(f"  Miner offline — skipping")
        return

    retriever = store.as_retriever(search_kwargs={"k": 3})
    print(f"  Retriever created: {retriever}")
    print("  → Pass this retriever to any LangChain chain:")
    print("      from langchain.chains import RetrievalQA")
    print("      chain = RetrievalQA.from_chain_type(llm=your_llm, retriever=retriever)")
    print("      answer = chain.run('What is Bittensor?')")
    print("  ✓ Retriever pattern demo complete")


if __name__ == "__main__":
    print(f"Engram AI Agent Memory Demo")
    print(f"Miner: {MINER_URL}")

    demo_raw_memory()
    demo_langchain()
    demo_llama_index()
    demo_retrieval_qa()

    print("\n✓ All demos complete.")
