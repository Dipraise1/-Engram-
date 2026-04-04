"use client";
import { DocPage, H1, H2, Lead, Code, Note, Ic } from "../_components";

export default function LlamaIndexPage() {
  return (
    <DocPage
      prev={{ href: "/docs/sdk-langchain", label: "LangChain" }}
      next={{ href: "/docs/sdk-errors", label: "Exceptions" }}
      toc={[
        { id: "install", label: "Install" },
        { id: "basic", label: "Basic usage" },
        { id: "query", label: "Query engine" },
      ]}
    >
      <H1>LlamaIndex Integration</H1>
      <Lead>
        <Ic>EngramVectorStore</Ic> from <Ic>engram.sdk.llama_index</Ic> implements <Ic>BasePydanticVectorStore</Ic>.
      </Lead>

      <H2 id="install">Install</H2>
      <Code lang="bash">{`pip install llama-index-core engram-subnet`}</Code>

      <H2 id="basic">Basic usage</H2>
      <Code lang="python">{`from llama_index.core import VectorStoreIndex, Document
from llama_index.core.storage.storage_context import StorageContext
from engram.sdk.llama_index import EngramVectorStore

store = EngramVectorStore(miner_url="http://127.0.0.1:8091")
storage_context = StorageContext.from_defaults(vector_store=store)

documents = [
    Document(text="Bittensor is a decentralised ML network."),
    Document(text="TAO tokens reward miners and validators."),
    Document(text="Engram stores embeddings on Bittensor."),
]

index = VectorStoreIndex.from_documents(
    documents,
    storage_context=storage_context,
)`}</Code>

      <H2 id="query">Query engine</H2>
      <Code lang="python">{`query_engine = index.as_query_engine()

response = query_engine.query("How does Bittensor distribute rewards?")
print(response)

# Retrieve without generating
retriever = index.as_retriever(similarity_top_k=5)
nodes = retriever.retrieve("TAO tokenomics")`}</Code>

      <Note>
        The <Ic>delete()</Ic> method is a no-op in Engram — vectors are content-addressed and immutable once stored.
      </Note>
    </DocPage>
  );
}
