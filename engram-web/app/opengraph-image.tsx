import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Engram — Decentralized AI Memory Layer on Bittensor";
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
        {/* Background glows */}
        <div
          style={{
            position: "absolute",
            top: "-140px",
            right: "-100px",
            width: "520px",
            height: "520px",
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(160,80,220,0.20) 0%, transparent 70%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: "-100px",
            left: "160px",
            width: "420px",
            height: "420px",
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(100,60,180,0.14) 0%, transparent 70%)",
          }}
        />

        {/* Logo mark + wordmark */}
        <div style={{ display: "flex", alignItems: "center", gap: "16px", marginBottom: "44px" }}>
          <div
            style={{
              width: "52px",
              height: "52px",
              borderRadius: "14px",
              background: "linear-gradient(135deg, #b060e8 0%, #6b2fa0 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "26px",
              color: "white",
              fontWeight: "800",
            }}
          >
            E
          </div>
          <span style={{ color: "#ffffff", fontSize: "30px", fontWeight: "700", letterSpacing: "-0.5px" }}>
            Engram
          </span>
          <span
            style={{
              fontSize: "13px",
              color: "#7a6a8e",
              border: "1px solid #2a1f38",
              borderRadius: "8px",
              padding: "4px 12px",
              fontFamily: "monospace",
              marginLeft: "4px",
            }}
          >
            subnet 450
          </span>
        </div>

        {/* Headline */}
        <div
          style={{
            fontSize: "56px",
            fontWeight: "800",
            color: "#ffffff",
            lineHeight: 1.1,
            letterSpacing: "-1.5px",
            marginBottom: "22px",
            maxWidth: "880px",
          }}
        >
          Decentralized AI{" "}
          <span style={{ color: "#c060f0" }}>Memory Layer</span>
        </div>

        {/* Sub */}
        <div
          style={{
            fontSize: "21px",
            color: "#8b7a9e",
            maxWidth: "780px",
            lineHeight: 1.55,
            marginBottom: "52px",
          }}
        >
          Store text, images, and PDFs on Bittensor miners. Every piece of
          knowledge gets a permanent content-addressed CID — no central authority.
        </div>

        {/* Feature pills */}
        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
          {["Bittensor Subnet 450", "FAISS HNSW Search", "Arweave Storage", "Python SDK"].map((tag) => (
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

        {/* URL watermark */}
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
