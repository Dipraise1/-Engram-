import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Engram — Decentralized Vector Database on Bittensor";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          background: "#080608",
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-start",
          justifyContent: "center",
          padding: "80px 90px",
          fontFamily: "sans-serif",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Background glow */}
        <div
          style={{
            position: "absolute",
            top: "-120px",
            right: "-120px",
            width: "500px",
            height: "500px",
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(160,80,220,0.18) 0%, transparent 70%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: "-80px",
            left: "200px",
            width: "400px",
            height: "400px",
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(100,60,180,0.12) 0%, transparent 70%)",
          }}
        />

        {/* Logo + wordmark */}
        <div style={{ display: "flex", alignItems: "center", gap: "16px", marginBottom: "48px" }}>
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "12px",
              background: "linear-gradient(135deg, #9b59d0 0%, #6b2fa0 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "24px",
              color: "white",
              fontWeight: "bold",
            }}
          >
            E
          </div>
          <span style={{ color: "#ffffff", fontSize: "28px", fontWeight: "600", letterSpacing: "-0.5px" }}>
            Engram
          </span>
          <span
            style={{
              fontSize: "13px",
              color: "#6b5a7e",
              border: "1px solid #1e1525",
              borderRadius: "6px",
              padding: "4px 10px",
              fontFamily: "monospace",
            }}
          >
            subnet 450
          </span>
        </div>

        {/* Headline */}
        <div
          style={{
            fontSize: "58px",
            fontWeight: "800",
            color: "#ffffff",
            lineHeight: 1.1,
            letterSpacing: "-1.5px",
            marginBottom: "24px",
            maxWidth: "860px",
          }}
        >
          Decentralized Vector Database
        </div>

        {/* Sub */}
        <div
          style={{
            fontSize: "22px",
            color: "#8b7a9e",
            maxWidth: "760px",
            lineHeight: 1.5,
            marginBottom: "56px",
          }}
        >
          Store, search, and prove AI embeddings on Bittensor — no central authority, full cryptographic proof.
        </div>

        {/* Pills */}
        <div style={{ display: "flex", gap: "12px" }}>
          {["Bittensor", "AES-256 Encryption", "HNSW Search", "Python SDK"].map((tag) => (
            <div
              key={tag}
              style={{
                background: "#120e18",
                border: "1px solid #2a1f38",
                borderRadius: "100px",
                padding: "8px 18px",
                fontSize: "14px",
                color: "#c4b5d4",
              }}
            >
              {tag}
            </div>
          ))}
        </div>

        {/* URL */}
        <div
          style={{
            position: "absolute",
            bottom: "48px",
            right: "90px",
            fontSize: "16px",
            color: "#3a2845",
            fontFamily: "monospace",
          }}
        >
          theengram.space
        </div>
      </div>
    ),
    { ...size }
  );
}
