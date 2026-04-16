import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Memory Search",
  description:
    "Search your stored memories on Engram with natural language. Ask questions across everything you've ingested — text, images, and PDFs — powered by semantic vector search.",
  alternates: { canonical: "https://theengram.space/memory" },
  openGraph: {
    title: "Engram Memory Search — Semantic AI Chat",
    description:
      "Query everything you've stored on Engram using natural language. Semantic search over your decentralized vector database.",
    url: "https://theengram.space/memory",
    images: [{ url: "/og-image.png", width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Engram Memory Search",
    description:
      "Ask questions across everything you've stored on Engram — text, images, PDFs — with semantic vector search.",
    images: ["/og-image.png"],
  },
};

export default function MemoryLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
