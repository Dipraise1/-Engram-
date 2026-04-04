import type { Metadata } from "next";
import { Cormorant_Garamond, DM_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
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

export const metadata: Metadata = {
  title: "Engram — Decentralized Vector Database",
  description:
    "The first decentralized, content-addressed vector database built on Bittensor. Store, retrieve, and prove ownership of embeddings — without a central authority.",
  keywords: ["vector database", "bittensor", "decentralized", "embeddings", "semantic search", "AI"],
  openGraph: {
    title: "Engram — Decentralized Vector Database",
    description: "Store and retrieve embeddings on Bittensor's decentralized network.",
    type: "website",
    url: "https://theengram.space",
  },
  twitter: {
    card: "summary_large_image",
    title: "Engram — Decentralized Vector Database",
    description: "The first decentralized vector DB on Bittensor.",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${cormorant.variable} ${dmSans.variable} ${jetbrainsMono.variable}`}
    >
      <body className="bg-[#080608] text-slate-200 antialiased">{children}</body>
    </html>
  );
}
