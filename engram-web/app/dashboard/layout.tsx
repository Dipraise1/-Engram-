import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Live Dashboard",
  description:
    "Real-time stats for Engram subnet 450 on Bittensor: active miners, stored vectors, average recall score, proof rate, and current block height.",
  alternates: { canonical: "https://theengram.space/dashboard" },
  openGraph: {
    title: "Engram Live Dashboard — Subnet 450 Stats",
    description:
      "Monitor active miners, vector count, scoring, and proof rate on Engram — the decentralized vector database on Bittensor.",
    url: "https://theengram.space/dashboard",
    images: [{ url: "/og-image.png", width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Engram Live Dashboard — Subnet 450",
    description:
      "Real-time miner stats, vector counts, and recall scores for Engram on Bittensor.",
    images: ["/og-image.png"],
  },
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
