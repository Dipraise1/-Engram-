import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Engram — Decentralized Vector Database",
  description:
    "The first decentralized, content-addressed vector database built on Bittensor. Store, retrieve, and prove ownership of embeddings — without a central authority.",
  keywords: ["vector database", "bittensor", "decentralized", "embeddings", "semantic search", "AI"],
  openGraph: {
    title: "Engram — Decentralized Vector Database",
    description: "Store and retrieve embeddings on Bittensor's decentralized network.",
    type: "website",
    url: "https://engramdb.xyz",
  },
  twitter: {
    card: "summary_large_image",
    title: "Engram — Decentralized Vector Database",
    description: "The first decentralized vector DB on Bittensor.",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400;1,500;1,600&family=DM+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-[#080608] text-slate-200 antialiased">{children}</body>
    </html>
  );
}
