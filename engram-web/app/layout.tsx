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

export const metadata: Metadata = {
  title: "Engram — Decentralized Vector Database",
  description:
    "The first decentralized, content-addressed vector database built on Bittensor. Store, retrieve, and prove ownership of embeddings — without a central authority.",
  keywords: ["vector database", "bittensor", "decentralized", "embeddings", "semantic search", "AI", "TAO"],
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
    ],
    shortcut: "/favicon.svg",
    apple: "/logo.png",
  },
  openGraph: {
    title: "Engram — Decentralized Vector Database",
    description: "The first decentralized, content-addressed vector database built on Bittensor. Store and retrieve embeddings with cryptographic proofs.",
    type: "website",
    url: "https://theengram.space",
    images: [{ url: "https://theengram.space/logo.png", width: 512, height: 512 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Engram — Decentralized Vector Database",
    description: "The first decentralized vector DB on Bittensor. Store embeddings with cryptographic proofs — no AWS, no central authority.",
    images: ["https://theengram.space/logo.png"],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${playfair.variable} ${dmSans.variable} ${jetbrainsMono.variable}`}
    >
      <body className="bg-[#080608] text-slate-200 antialiased">{children}</body>
    </html>
  );
}
