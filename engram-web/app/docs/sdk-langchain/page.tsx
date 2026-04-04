"use client";
import { DocPage, H1, H2, Lead, P, Code, Note, Ic } from "../ui";

export default function LangChainPage() {
  return (
    <DocPage
      prev={{ href: "/docs/sdk", label: "EngramClient" }}
      next={{ href: "/docs/sdk-llama", label: "LlamaIndex" }}
      toc={[
        { id: "install", label: "Install" },
        { id: "basic", label: "Basic usage" },
        { id: "retriever", label: "As a retriever" },
        { id: "qa", label: "RetrievalQA chain" },
      ]}
    >
      <H1>LangChain Integration</H1>
      <Lead>
        <Ic>EngramVectorStore</Ic> implements the LangChain <Ic>VectorStore</Ic> interface — drop Engram into any LangChain pipeline.
      </Lead>

      <H2 id="install">Install</H2>
      <Code lang="bash">{`pip install langchain-core langchain-openai engram-subnet`}</Code>

      <H2 id="basic">Basic usage</H2>
      <Code lang="python">{`from langchain_openai import OpenAIEmbeddings
from engram.sdk.langchain import EngramVectorStore

embeddings = OpenAIEmbeddings()
store = EngramVectorStore(
    miner_url="http://127.0.0.1:8091",
    embeddings=embeddings,   # omit to use miner's built-in embedder
)

# Store documents
store.add_texts(
    ["BERT uses bidirectional transformers.", "GPT generates text autoregressively."],
    metadatas=[{"source": "paper"}, {"source": "paper"}],
)

# Similarity search
docs = store.similarity_search("how does attention work?", k=5)
for doc in docs:
    print(doc.page_content, doc.metadata)

# With scores
docs_and_scores = store.similarity_search_with_score("transformers", k=3)
for doc, score in docs_and_scores:
    print(f"{score:.4f} — {doc.page_content[:60]}")`}</Code>

      <Note type="tip">
        If <Ic>embeddings</Ic> is omitted, the miner's built-in sentence-transformers model is used. Pass an embeddings object to use OpenAI, Cohere, HuggingFace, etc.
      </Note>

      <H2 id="retriever">As a retriever</H2>
      <Code lang="python">{`retriever = store.as_retriever(search_kwargs={"k": 5})

# Use in any chain
docs = retriever.invoke("what is Bittensor?")`}</Code>

      <H2 id="qa">RetrievalQA chain</H2>
      <Code lang="python">{`from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini")
retriever = store.as_retriever(search_kwargs={"k": 5})

chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=retriever,
)

answer = chain.run("How does Bittensor distribute rewards?")
print(answer)`}</Code>
    </DocPage>
  );
}
