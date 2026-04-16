import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Playground",
  description:
    "Try Engram live — store text, images, and PDFs on a decentralized Bittensor subnet. Every upload gets a permanent content-addressed CID backed by Arweave.",
  alternates: { canonical: "https://theengram.space/playground" },
  openGraph: {
    title: "Engram Playground — Store AI Memories Live",
    description:
      "Upload text, images, or PDFs. Get back a permanent CID stored on Bittensor miners and pinned to Arweave. No wallet needed.",
    url: "https://theengram.space/playground",
    images: [{ url: "/og-image.png", width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Engram Playground — Store AI Memories Live",
    description:
      "Upload text, images, or PDFs. Get a permanent content-addressed CID on Bittensor subnet 450.",
    images: ["/og-image.png"],
  },
};

export default function PlaygroundLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
