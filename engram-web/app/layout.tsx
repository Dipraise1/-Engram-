import type { Metadata } from "next";
import { Playfair_Display, DM_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const playfair = Playfair_Display({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800", "900"],
  style: ["normal", "italic"],
  variable: "--font-display",
  display: "swap",
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

const BASE_URL = "https://theengram.space";

export const metadata: Metadata = {
  metadataBase: new URL(BASE_URL),
  title: {
    default: "Engram — Decentralized AI Memory Layer on Bittensor",
    template: "%s | Engram",
  },
  description:
    "Engram is the decentralized AI memory layer on Bittensor subnet 450. Store text, images, and PDFs as permanent, content-addressed vector embeddings — retrieved by incentivized miners, archived on Arweave. No central authority.",
  keywords: [
    "decentralized vector database",
    "AI memory layer",
    "bittensor subnet 450",
    "embeddings storage",
    "semantic search",
    "decentralized AI",
    "RAG memory",
    "retrieval augmented generation",
    "content-addressed embeddings",
    "AI agent memory",
    "permanent AI memory",
    "vector database bittensor",
    "TAO subnet",
    "blockchain vector database",
    "FAISS HNSW",
    "open source vector database",
    "self-hosted vector database",
    "AI embeddings storage",
    "decentralized RAG",
    "Arweave AI storage",
    "engram subnet",
    "engram bittensor",
  ],
  authors: [{ name: "Engram Contributors", url: BASE_URL }],
  creator: "Engram",
  publisher: "Engram",
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  alternates: {
    canonical: BASE_URL,
  },
  icons: {
    icon: [
      { url: "/logo.png", type: "image/png", sizes: "any" },
    ],
    shortcut: "/logo.png",
    apple: "/logo.png",
  },
  openGraph: {
    title: "Engram — Decentralized AI Memory Layer on Bittensor",
    description:
      "Store text, images, and PDFs as permanent, content-addressed vector embeddings on Bittensor subnet 450. Retrieval, semantic search, and cryptographic storage proofs — no central authority.",
    type: "website",
    url: BASE_URL,
    siteName: "Engram",
    locale: "en_US",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Engram — Decentralized Vector Database on Bittensor",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    site: "@engramsubnet",
    title: "Engram — Decentralized AI Memory Layer on Bittensor",
    description:
      "Permanent, content-addressed AI memory on Bittensor subnet 450. Store text, images, and PDFs with cryptographic proofs — no AWS, no central authority.",
    images: ["/og-image.png"],
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "SoftwareApplication",
      "@id": `${BASE_URL}/#software`,
      name: "Engram",
      description:
        "Decentralized AI memory layer built on Bittensor subnet 450. Store text, images, and PDFs as content-addressed embeddings — retrieved and proved by a network of incentivized miners.",
      url: BASE_URL,
      applicationCategory: "DeveloperApplication",
      applicationSubCategory: "Vector Database",
      operatingSystem: "Linux, macOS, Windows",
      offers: {
        "@type": "Offer",
        price: "0",
        priceCurrency: "USD",
      },
      featureList: [
        "Decentralized vector storage on Bittensor",
        "Content-addressed embeddings (CID)",
        "Permanent blob storage via Arweave",
        "FAISS HNSW semantic search",
        "HMAC storage proof challenges",
        "Python SDK and CLI",
        "LangChain and LlamaIndex integrations",
      ],
      author: {
        "@type": "Organization",
        name: "Engram Contributors",
        url: BASE_URL,
      },
      sameAs: [
        "https://github.com/Dipraise1/-Engram-",
        "https://twitter.com/engramsubnet",
      ],
    },
    {
      "@type": "WebSite",
      "@id": `${BASE_URL}/#website`,
      url: BASE_URL,
      name: "Engram",
      description: "Decentralized AI memory layer on Bittensor",
      publisher: { "@id": `${BASE_URL}/#software` },
      potentialAction: {
        "@type": "SearchAction",
        target: { "@type": "EntryPoint", urlTemplate: `${BASE_URL}/memory?q={search_term_string}` },
        "query-input": "required name=search_term_string",
      },
    },
    {
      "@type": "FAQPage",
      mainEntity: [
        {
          "@type": "Question",
          name: "What is Engram?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "Engram is a decentralized AI memory layer built on Bittensor subnet 450. It lets you store text, images, and PDFs as content-addressed vector embeddings that are replicated across a network of incentivized miners and permanently archived on Arweave.",
          },
        },
        {
          "@type": "Question",
          name: "How does Engram differ from Pinecone or Weaviate?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "Unlike centralised vector databases, Engram has no single point of failure or central authority. Data is stored across multiple miners on the Bittensor blockchain, each of whom must cryptographically prove they hold your data. There is no monthly subscription — miners are paid in TAO tokens by the network.",
          },
        },
        {
          "@type": "Question",
          name: "What is a content-addressed CID?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "A CID (content identifier) is a SHA-256 hash derived from the vector embedding and metadata of your stored content. The same text always produces the same CID, regardless of which miner stores it — making storage verifiable and tamper-proof.",
          },
        },
        {
          "@type": "Question",
          name: "How do I store data on Engram?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "You can use the Python SDK (pip install engram-subnet), the CLI, or the web playground at theengram.space/playground. Each method returns a permanent CID you can use to retrieve the data later.",
          },
        },
        {
          "@type": "Question",
          name: "What is Bittensor subnet 450?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "Subnet 450 is Engram's slot on the Bittensor network. Bittensor is a decentralized machine learning network where miners and validators earn TAO tokens for running useful AI services. Engram's subnet uses those incentives to ensure permanent, verifiable vector storage.",
          },
        },
      ],
    },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${playfair.variable} ${dmSans.variable} ${jetbrainsMono.variable}`}
    >
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className="bg-[#080608] text-slate-200 antialiased">{children}</body>
    </html>
  );
}
