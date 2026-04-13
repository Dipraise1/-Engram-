"""Generate Engram miner/validator setup guide PDF."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# ── Palette ───────────────────────────────────────────────────────────────────
PURPLE      = colors.HexColor("#7c3aed")
PURPLE_DARK = colors.HexColor("#4c1d95")
PURPLE_BG   = colors.HexColor("#1e1b2e")
CODE_BG     = colors.HexColor("#0f0d1a")
CODE_TEXT   = colors.HexColor("#c4b5fd")
MUTED       = colors.HexColor("#a78bfa")
WHITE       = colors.HexColor("#f5f3ff")
LIGHT_GRAY  = colors.HexColor("#e5e7eb")
STEP_BG     = colors.HexColor("#2d1b69")

W, H = A4

def build_styles():
    base = getSampleStyleSheet()
    s = {}

    s["title"] = ParagraphStyle("title",
        fontSize=28, fontName="Helvetica-Bold",
        textColor=WHITE, alignment=TA_CENTER,
        spaceAfter=4)

    s["subtitle"] = ParagraphStyle("subtitle",
        fontSize=12, fontName="Helvetica",
        textColor=MUTED, alignment=TA_CENTER,
        spaceAfter=2)

    s["section"] = ParagraphStyle("section",
        fontSize=16, fontName="Helvetica-Bold",
        textColor=WHITE, spaceBefore=14, spaceAfter=6,
        leftIndent=0)

    s["step_label"] = ParagraphStyle("step_label",
        fontSize=11, fontName="Helvetica-Bold",
        textColor=WHITE, spaceBefore=8, spaceAfter=3)

    s["os_label"] = ParagraphStyle("os_label",
        fontSize=10, fontName="Helvetica-Bold",
        textColor=MUTED, spaceBefore=6, spaceAfter=2)

    s["body"] = ParagraphStyle("body",
        fontSize=9.5, fontName="Helvetica",
        textColor=LIGHT_GRAY, spaceAfter=4, leading=14)

    s["note"] = ParagraphStyle("note",
        fontSize=9, fontName="Helvetica-Oblique",
        textColor=MUTED, spaceAfter=4, leading=13,
        leftIndent=8)

    s["code"] = ParagraphStyle("code",
        fontSize=8.5, fontName="Courier",
        textColor=CODE_TEXT, spaceAfter=2, leading=13,
        leftIndent=6)

    return s


def code_block(lines, s):
    """Render a list of command strings as a styled code block."""
    content = []
    for line in lines:
        if line == "":
            content.append(Spacer(1, 3))
        else:
            content.append(Paragraph(line, s["code"]))
    table = Table(
        [[content]],
        colWidths=[W - 40*mm],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("ROUNDEDCORNERS", [6]),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("BOX", (0, 0), (-1, -1), 0.5, PURPLE),
    ]))
    return table


def step_header(num, title, s):
    return Paragraph(f"<b>Step {num} — {title}</b>", s["step_label"])


def os_block(label, lines, s):
    items = [Paragraph(label, s["os_label"])]
    items.append(code_block(lines, s))
    return items


def divider():
    return HRFlowable(width="100%", thickness=0.4, color=PURPLE, spaceAfter=8, spaceBefore=4)


def section_header(title, s):
    return [
        Spacer(1, 6),
        Paragraph(title, s["section"]),
        HRFlowable(width="100%", thickness=1, color=PURPLE, spaceAfter=6),
    ]


def build_pdf(path):
    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=18*mm, bottomMargin=18*mm,
        title="Engram — Miner & Validator Setup Guide",
        author="Engram",
    )

    s = build_styles()
    story = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    story += [
        Spacer(1, 18),
        Paragraph("ENGRAM", s["title"]),
        Paragraph("Miner &amp; Validator Setup Guide", s["subtitle"]),
        Paragraph("theengram.space · testnet · netuid 450", s["subtitle"]),
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=1.5, color=PURPLE, spaceAfter=10),
        Spacer(1, 4),
    ]

    # ═══════════════════════════════════════════════════════════════════════════
    # MINER
    # ═══════════════════════════════════════════════════════════════════════════
    story += section_header("Running a Miner", s)

    # Step 1 — Prerequisites
    story.append(KeepTogether([
        step_header(1, "Install Prerequisites", s),
        *os_block("Linux (Ubuntu 22.04+)", [
            "sudo apt update &amp;&amp; sudo apt install -y \\",
            "  python3.11 python3.11-venv git docker.io",
            "sudo systemctl start docker",
        ], s),
        *os_block("macOS", [
            "brew install python@3.11 git",
            "# Install Docker Desktop → docker.com/products/docker-desktop",
        ], s),
        *os_block("Windows", [
            "# Open PowerShell as Administrator:",
            "wsl --install -d Ubuntu",
            "# Restart, then follow the Linux steps inside WSL",
        ], s),
    ]))

    # Step 2 — Clone & Install
    story.append(KeepTogether([
        step_header(2, "Clone &amp; Install", s),
        code_block([
            "git clone https://github.com/Dipraise1/-Engram-.git",
            "cd -Engram-",
            "python3.11 -m venv .venv",
            "source .venv/bin/activate   # Windows: .venv\\Scripts\\activate",
            "pip install -e \".[node,qdrant]\"",
        ], s),
    ]))

    # Step 3 — Start Qdrant
    story.append(KeepTogether([
        step_header(3, "Start Qdrant (vector store)", s),
        code_block([
            "docker run -d --name qdrant -p 6333:6333 \\",
            "  -v $(pwd)/data/qdrant:/qdrant/storage qdrant/qdrant",
        ], s),
    ]))

    # Step 4 — Configure
    story.append(KeepTogether([
        step_header(4, "Configure", s),
        code_block([
            "cp .env.example .env",
            "# Then edit .env with the values below:",
        ], s),
        code_block([
            "WALLET_NAME=default",
            "WALLET_HOTKEY=default",
            "SUBTENSOR_NETWORK=test",
            "NETUID=450",
            "MINER_PORT=8091",
            "EXTERNAL_IP=&lt;your-public-ip&gt;",
            "VECTOR_STORE_BACKEND=qdrant",
            "USE_LOCAL_EMBEDDER=true",
        ], s),
    ]))

    # Step 5 — Create Wallet
    story.append(KeepTogether([
        step_header(5, "Create Bittensor Wallet", s),
        code_block([
            "pip install bittensor",
            "",
            "# Coldkey — save the mnemonic somewhere safe, it cannot be recovered",
            "btcli wallet new_coldkey --wallet.name default",
            "",
            "# Hotkey — used by the miner process",
            "btcli wallet new_hotkey --wallet.name default --wallet.hotkey default",
            "",
            "# Get your coldkey address",
            "btcli wallet overview --wallet.name default",
        ], s),
    ]))

    # Step 6 — Get TAO
    story.append(KeepTogether([
        step_header(6, "Get Testnet TAO", s),
        Paragraph(
            "Go to <b>https://taoswap.org/testnet-faucet</b>, paste your coldkey address "
            "and receive test TAO (~1 min).",
            s["body"]
        ),
        code_block([
            "# Confirm balance arrived",
            "btcli wallet balance --wallet.name default --subtensor.network test",
        ], s),
    ]))

    # Step 7 — Register
    story.append(KeepTogether([
        step_header(7, "Register on Subnet", s),
        code_block([
            "btcli subnet register --netuid 450 \\",
            "  --wallet.name default \\",
            "  --wallet.hotkey default \\",
            "  --subtensor.network test",
        ], s),
    ]))

    # Step 8 — Run
    story.append(KeepTogether([
        step_header(8, "Run the Miner", s),
        code_block([
            "python neurons/miner.py",
        ], s),
        Paragraph("Verify it's running:", s["body"]),
        code_block([
            'curl http://localhost:8091/stats',
            '# {"status":"ok","vectors":0,"peers":5,"uid":4}',
        ], s),
    ]))

    # Step 9 — Keep Alive
    story.append(KeepTogether([
        step_header(9, "Keep Alive (auto-restart)", s),
        *os_block("Linux — systemd (recommended)", [
            "sudo cp scripts/engram-miner.service /etc/systemd/system/",
            "sudo systemctl enable --now engram-miner",
            "journalctl -u engram-miner -f   # view live logs",
        ], s),
        *os_block("macOS / Windows (WSL)", [
            "pip install pm2",
            "pm2 start \"python neurons/miner.py\" --name engram-miner --cwd $(pwd)",
            "pm2 save &amp;&amp; pm2 startup",
        ], s),
    ]))

    # ═══════════════════════════════════════════════════════════════════════════
    # VALIDATOR
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story += section_header("Running a Validator", s)

    # Step 1 — Clone & Install
    story.append(KeepTogether([
        step_header(1, "Clone &amp; Install", s),
        Paragraph("Skip if you already ran the miner setup on this machine.", s["note"]),
        *os_block("Linux (Ubuntu 22.04+)", [
            "sudo apt update &amp;&amp; sudo apt install -y python3.11 python3.11-venv git",
        ], s),
        *os_block("macOS", [
            "brew install python@3.11 git",
        ], s),
        *os_block("Windows", [
            "wsl --install -d Ubuntu   # in PowerShell as Admin, then use WSL",
        ], s),
        code_block([
            "git clone https://github.com/Dipraise1/-Engram-.git",
            "cd -Engram-",
            "python3.11 -m venv .venv",
            "source .venv/bin/activate   # Windows: .venv\\Scripts\\activate",
            "pip install -e \".[node]\"",
        ], s),
    ]))

    # Step 2 — Ground Truth
    story.append(KeepTogether([
        step_header(2, "Generate Ground Truth Dataset", s),
        code_block([
            "USE_LOCAL_EMBEDDER=true python scripts/generate_ground_truth.py --count 1000",
        ], s),
        Paragraph("Creates <b>data/ground_truth.jsonl</b> — 1000 embedded text entries used to score miners.", s["note"]),
    ]))

    # Step 3 — Configure
    story.append(KeepTogether([
        step_header(3, "Configure", s),
        code_block([
            "cp .env.example .env",
        ], s),
        code_block([
            "WALLET_NAME=default",
            "WALLET_HOTKEY=validator",
            "SUBTENSOR_NETWORK=test",
            "NETUID=450",
            "GROUND_TRUTH_PATH=./data/ground_truth.jsonl",
        ], s),
    ]))

    # Step 4 — Create Wallet
    story.append(KeepTogether([
        step_header(4, "Create Bittensor Wallet", s),
        Paragraph("Skip if already created during miner setup.", s["note"]),
        code_block([
            "pip install bittensor",
            "",
            "btcli wallet new_coldkey --wallet.name default",
            "btcli wallet new_hotkey --wallet.name default --wallet.hotkey validator",
            "btcli wallet overview --wallet.name default",
        ], s),
    ]))

    # Step 5 — Get TAO
    story.append(KeepTogether([
        step_header(5, "Get Testnet TAO", s),
        Paragraph(
            "Go to <b>https://taoswap.org/testnet-faucet</b>, paste your coldkey address.",
            s["body"]
        ),
        code_block([
            "btcli wallet balance --wallet.name default --subtensor.network test",
        ], s),
    ]))

    # Step 6 — Register
    story.append(KeepTogether([
        step_header(6, "Register on Subnet", s),
        code_block([
            "btcli subnet register --netuid 450 \\",
            "  --wallet.name default \\",
            "  --wallet.hotkey validator \\",
            "  --subtensor.network test",
        ], s),
    ]))

    # Step 7 — Run
    story.append(KeepTogether([
        step_header(7, "Run the Validator", s),
        code_block([
            "python neurons/validator.py",
        ], s),
    ]))

    # Step 8 — Keep Alive
    story.append(KeepTogether([
        step_header(8, "Keep Alive (auto-restart)", s),
        *os_block("Linux — systemd (recommended)", [
            "sudo cp scripts/engram-validator.service /etc/systemd/system/",
            "sudo systemctl enable --now engram-validator",
            "journalctl -u engram-validator -f",
        ], s),
        *os_block("macOS / Windows (WSL)", [
            "pm2 start \"python neurons/validator.py\" --name engram-validator --cwd $(pwd)",
            "pm2 save",
        ], s),
    ]))

    # ── Scoring reference ─────────────────────────────────────────────────────
    story += [
        Spacer(1, 8),
        divider(),
        Paragraph("<b>Scoring</b> — validators score miners every 120s.", s["body"]),
    ]

    score_data = [
        ["Component", "Weight", "Description"],
        ["recall@10",    "50%", "Did the miner return the expected CIDs?"],
        ["Latency",      "30%", "100ms = 1.0 · 500ms = 0.0 · linear"],
        ["Proof rate",   "20%", "HMAC challenge-response success rate"],
    ]
    score_table = Table(score_data, colWidths=[40*mm, 22*mm, W - 40*mm - 22*mm - 40*mm])
    score_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  PURPLE_DARK),
        ("BACKGROUND",   (0, 1), (-1, -1), CODE_BG),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  WHITE),
        ("TEXTCOLOR",    (0, 1), (-1, -1), LIGHT_GRAY),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CODE_BG, PURPLE_BG]),
        ("GRID",         (0, 0), (-1, -1), 0.3, PURPLE),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Miners below 50% proof success rate score 0 regardless of recall or latency.",
        s["note"]
    ))

    # ── Footer note ────────────────────────────────────────────────────────────
    story += [
        Spacer(1, 10),
        HRFlowable(width="100%", thickness=0.4, color=PURPLE, spaceAfter=6),
        Paragraph("theengram.space · github.com/Dipraise1/-Engram- · Discord: discord.gg/engram", s["subtitle"]),
    ]

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(PURPLE_BG)
        canvas.rect(0, 0, W, H, fill=1, stroke=0)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(W / 2, 10*mm, f"Engram Setup Guide  ·  Page {doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"PDF written → {path}")


if __name__ == "__main__":
    build_pdf("/Users/divine/Documents/engram/engram-miner-validator-guide.pdf")
