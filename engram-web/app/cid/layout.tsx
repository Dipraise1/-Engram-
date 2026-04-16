import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "CID Lookup",
  description:
    "Look up any Engram content identifier (CID) — view the stored embedding metadata, Arweave transaction proof, and content hash for any memory on subnet 450.",
  alternates: { canonical: "https://theengram.space/cid" },
  openGraph: {
    title: "Engram CID Lookup — Content-Addressed Memory",
    description:
      "Verify any stored memory on Engram by CID. View metadata, Arweave proof, and cryptographic content hash.",
    url: "https://theengram.space/cid",
    images: [{ url: "/og-image.png", width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Engram CID Lookup",
    description:
      "Verify any stored memory on Engram by CID. Arweave proof, content hash, and metadata.",
    images: ["/og-image.png"],
  },
};

export default function CidLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
