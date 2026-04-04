"""
Phase 6.2 — Generate 1000+ ground truth query/result pairs

Generates a diverse corpus of texts, embeds them, computes top-K matches
via cosine similarity, and writes to data/ground_truth.jsonl.

Run:
  python scripts/generate_ground_truth.py [--count 1000]
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")

CORPUS = [
    # AI / ML
    "Artificial intelligence is transforming every industry",
    "Deep learning models require large amounts of training data",
    "Neural networks can approximate any continuous function",
    "Transformer architecture uses self-attention mechanisms",
    "Gradient descent minimizes the loss function iteratively",
    "Convolutional neural networks excel at image recognition",
    "Recurrent networks process sequential data over time",
    "Reinforcement learning trains agents through reward signals",
    "Transfer learning reuses pretrained model weights",
    "Batch normalization stabilizes training of deep networks",
    "Dropout prevents overfitting by randomly zeroing activations",
    "The attention mechanism allows models to focus on relevant parts",
    "BERT uses bidirectional encoder representations from transformers",
    "GPT generates text by predicting the next token autoregressively",
    "Embeddings map discrete tokens to continuous vector spaces",
    "Semantic similarity is measured by cosine distance between vectors",
    "Vector databases enable approximate nearest neighbor search",
    "FAISS is a library for efficient similarity search",
    "Qdrant is a production vector search engine written in Rust",
    "Pinecone provides managed vector database infrastructure",
    # Bittensor / Web3
    "Bittensor creates a decentralized machine learning network",
    "TAO is the native token of the Bittensor network",
    "Validators score miners and set weights on the blockchain",
    "Miners earn TAO by providing useful machine learning services",
    "Subnet registration requires burning TAO tokens",
    "dTAO routes emissions to subnets based on validator weights",
    "The Opentensor Foundation maintains the Bittensor protocol",
    "Metagraph stores the state of all registered neurons",
    "Hotkeys are used for per-subnet identity and signing",
    "Coldkeys hold the TAO balance and authorize transactions",
    # Storage / Distributed Systems
    "IPFS uses content addressing to identify files by their hash",
    "Distributed hash tables enable peer-to-peer key-value lookup",
    "Kademlia uses XOR distance for routing table organization",
    "Replication factor determines how many nodes store each piece of data",
    "Content identifiers are deterministic hashes of the data",
    "Storage proofs cryptographically verify data possession",
    "HMAC authentication prevents tampering with challenge responses",
    "SHA-256 produces a 256-bit cryptographic hash",
    "Merkle trees enable efficient verification of large datasets",
    "Byzantine fault tolerance handles malicious nodes in consensus",
    # Software Engineering
    "Rust provides memory safety without garbage collection",
    "PyO3 enables writing Python extensions in Rust",
    "Docker containers package applications with their dependencies",
    "Kubernetes orchestrates containerized workloads at scale",
    "CI/CD pipelines automate testing and deployment",
    "GitHub Actions runs workflows on code push events",
    "Pytest is a Python testing framework with powerful fixtures",
    "Type hints improve code readability and catch bugs early",
    "Async/await enables concurrent I/O without blocking threads",
    "aiohttp is an async HTTP client and server for Python",
    # Data Science
    "Cosine similarity measures the angle between two vectors",
    "Euclidean distance measures the straight-line distance between points",
    "Dimensionality reduction projects data to lower dimensions",
    "Principal component analysis finds the axes of maximum variance",
    "t-SNE creates 2D visualizations of high-dimensional data",
    "K-means clustering partitions data into K groups",
    "Random forests combine many decision trees for better accuracy",
    "Gradient boosting builds an ensemble of weak learners",
    "Cross-validation estimates model performance on unseen data",
    "Precision and recall measure classification performance",
    # NLP
    "Tokenization splits text into subword units for model input",
    "Word2Vec learns word embeddings from co-occurrence statistics",
    "Sentence transformers encode entire sentences into fixed vectors",
    "Named entity recognition identifies people, places, and organizations",
    "Sentiment analysis classifies text as positive or negative",
    "Question answering extracts answers from a context passage",
    "Summarization condenses long documents into shorter form",
    "Machine translation converts text between languages",
    "Text classification assigns categories to input documents",
    "Information retrieval finds relevant documents for a query",
    # Crypto / Finance
    "Proof of work requires miners to solve computational puzzles",
    "Proof of stake selects validators proportional to their stake",
    "Smart contracts execute automatically when conditions are met",
    "Decentralized finance removes intermediaries from financial services",
    "Liquidity pools enable automated market making",
    "Yield farming earns rewards by providing liquidity",
    "Non-fungible tokens represent unique digital assets",
    "Layer 2 solutions scale blockchains by processing off-chain",
    "Zero-knowledge proofs verify statements without revealing information",
    "Multisig wallets require multiple signatures to authorize transactions",
    # General Tech
    "APIs enable different software systems to communicate",
    "REST uses HTTP methods to interact with resources",
    "GraphQL allows clients to specify exactly what data they need",
    "WebSockets enable real-time bidirectional communication",
    "Load balancers distribute traffic across multiple servers",
    "Caching stores frequently accessed data in fast memory",
    "Database indexing speeds up query execution",
    "SQL joins combine rows from multiple tables",
    "NoSQL databases sacrifice consistency for scalability",
    "Message queues decouple producers and consumers",
    "Microservices split applications into small independent services",
    "Observability measures system health through logs, metrics, traces",
]


def generate(count: int, output_path: Path, recall_k: int = 10) -> None:
    from engram.miner.embedder import get_embedder

    print(f"Loading embedder…")
    embedder = get_embedder()

    # Build a corpus large enough to cover count entries
    # Repeat and vary the base corpus to reach the target count
    texts = []
    base = CORPUS.copy()
    i = 0
    while len(texts) < count:
        t = base[i % len(base)]
        # Add variation to create distinct entries
        variant = i // len(base)
        if variant > 0:
            t = f"[v{variant}] {t}"
        texts.append(t)
        i += 1

    texts = texts[:count]

    print(f"Embedding {count} texts…")
    t0 = time.perf_counter()
    embeddings = np.array([embedder.embed(t) for t in texts], dtype=np.float32)
    elapsed = time.perf_counter() - t0
    print(f"  Done in {elapsed:.1f}s ({count/elapsed:.0f} texts/sec)")

    # Generate CIDs
    import engram_core
    cids = [engram_core.generate_cid(emb.tolist(), {}, "v1") for emb in embeddings]

    # Compute top-K for each entry via cosine similarity
    print("Computing top-K ground truth…")
    # Normalize for cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normed = embeddings / np.maximum(norms, 1e-8)
    sim_matrix = normed @ normed.T  # (N, N) cosine similarities

    output_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with output_path.open("w") as f:
        for idx in range(count):
            sims = sim_matrix[idx]
            # Top-K by similarity (excluding self at rank 0 — include self as first)
            top_indices = np.argsort(sims)[::-1][:recall_k]
            top_cids = [cids[j] for j in top_indices]

            record = {
                "text": texts[idx],
                "embedding": embeddings[idx].tolist(),
                "cid": cids[idx],
                "top_k_cids": top_cids,
            }
            f.write(json.dumps(record) + "\n")
            written += 1

    print(f"Wrote {written} entries to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--output", type=str, default="data/ground_truth.jsonl")
    parser.add_argument("--recall-k", type=int, default=10)
    args = parser.parse_args()

    generate(
        count=args.count,
        output_path=Path(args.output),
        recall_k=args.recall_k,
    )


if __name__ == "__main__":
    main()
