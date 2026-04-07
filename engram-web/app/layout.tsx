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
    default: "Engram — Decentralized Vector Database on Bittensor",
    template: "%s | Engram",
  },
  description:
    "The first decentralized, content-addressed vector database built on Bittensor. Store, retrieve, and prove ownership of AI embeddings — no central authority, no AWS, full cryptographic proof.",
  keywords: [
    "vector database",
    "decentralized vector database",
    "bittensor subnet",
    "embeddings storage",
    "semantic search",
    "decentralized AI",
    "RAG",
    "retrieval augmented generation",
    "TAO",
    "blockchain AI",
    "IPFS vector database",
    "content-addressed embeddings",
    "AI memory layer",
    "engram subnet",
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
    icon: [{ url: "/favicon.svg", type: "image/svg+xml" }],
    shortcut: "/favicon.svg",
    apple: "/logo.png",
  },
  openGraph: {
    title: "Engram — Decentralized Vector Database on Bittensor",
    description:
      "The first decentralized, content-addressed vector database built on Bittensor. Store and retrieve AI embeddings with cryptographic proofs — no central authority.",
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
    title: "Engram — Decentralized Vector Database on Bittensor",
    description:
      "The first decentralized vector DB on Bittensor. Store embeddings with cryptographic proofs — no AWS, no central authority.",
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
        "Decentralized, content-addressed vector database built on Bittensor. Store, retrieve, and prove ownership of AI embeddings without a central authority.",
      url: BASE_URL,
      applicationCategory: "DeveloperApplication",
      operatingSystem: "Linux, macOS, Windows",
      offers: {
        "@type": "Offer",
        price: "0",
        priceCurrency: "USD",
      },
      author: {
        "@type": "Organization",
        name: "Engram Contributors",
        url: BASE_URL,
      },
      sameAs: ["https://github.com/Dipraise1/-Engram-"],
    },
    {
      "@type": "WebSite",
      "@id": `${BASE_URL}/#website`,
      url: BASE_URL,
      name: "Engram",
      description: "Decentralized vector database on Bittensor",
      publisher: { "@id": `${BASE_URL}/#software` },
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
