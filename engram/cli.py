"""
Engram CLI

Usage:
    engram ingest "your text here"
    engram ingest --file ./docs.txt
    engram query "semantic search query"
    engram status
    engram demo
"""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

load_dotenv()

app = typer.Typer(
    name="engram",
    help="Engram — Decentralized Vector Database on Bittensor",
    no_args_is_help=True,
)
console = Console()

os.environ.setdefault("USE_LOCAL_EMBEDDER", "true")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_store_and_embedder():
    from engram.miner.embedder import get_embedder
    from engram.miner.store import FAISSStore
    embedder = get_embedder()
    index_path = os.getenv("FAISS_INDEX_PATH", "./data/engram.index")
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    store = FAISSStore(dim=embedder.dim, index_path=index_path)
    return store, embedder


def _cid_short(cid: str) -> str:
    return cid[:8] + "..." + cid[-6:] if len(cid) > 16 else cid


# ── Commands ──────────────────────────────────────────────────────────────────

@app.command()
def ingest(
    text: str = typer.Argument(None, help="Text to embed and store."),
    file: Path = typer.Option(None, "--file", "-f", help="Path to a .txt or .jsonl file to ingest."),
    dir: Path = typer.Option(None, "--dir", "-d", help="Directory of .txt / .md / .jsonl files to ingest recursively."),
    metadata: str = typer.Option("{}", "--meta", "-m", help='JSON metadata e.g. \'{"source":"arxiv"}\''),
    source: str = typer.Option("cli", "--source", "-s", help="Source label for metadata."),
):
    """Ingest text into the local Engram store."""
    from engram.miner.ingest import IngestHandler
    from engram.protocol import IngestSynapse

    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError:
        console.print("[red]That doesn't look like valid JSON.[/red] Try: --meta '{\"source\": \"my-notes\"}'")
        raise typer.Exit(1)

    meta.setdefault("source", source)
    store, embedder = _get_store_and_embedder()
    handler = IngestHandler(store=store, embedder=embedder)

    texts: list[tuple[str, dict]] = []

    def _load_file(p: Path, base_meta: dict) -> list[tuple[str, dict]]:
        file_meta = {**base_meta, "file": p.name}
        records = []
        if p.suffix == ".jsonl":
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        obj = json.loads(line)
                        records.append((obj["text"], obj.get("metadata", file_meta)))
                    except (json.JSONDecodeError, KeyError):
                        pass
        else:
            content = p.read_text(encoding="utf-8").strip()
            if content:
                records.append((content, file_meta))
        return records

    if dir:
        if not dir.is_dir():
            console.print(f"[red]'{dir}' isn't a directory.[/red]")
            raise typer.Exit(1)
        suffixes = {".txt", ".md", ".jsonl"}
        files = sorted(p for p in dir.rglob("*") if p.suffix in suffixes and p.is_file())
        if not files:
            console.print(f"[yellow]No .txt, .md, or .jsonl files found in '{dir}'. Nothing to ingest.[/yellow]")
            raise typer.Exit(0)
        for p in files:
            texts.extend(_load_file(p, meta))
        console.print(f"[dim]Loaded {len(texts)} records from {len(files)} files in {dir}[/dim]")
    elif file:
        if not file.exists():
            console.print(f"[red]File not found:[/red] {file}")
            raise typer.Exit(1)
        texts = _load_file(file, meta)
        console.print(f"[dim]Loaded {len(texts)} records from {file}[/dim]")
    elif text:
        texts = [(text, meta)]
    else:
        console.print("[red]Nothing to ingest.[/red] Pass some text directly, or use --file to point at a file.")
        raise typer.Exit(1)

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("CID", style="cyan")
    table.add_column("Text", max_width=60)
    table.add_column("ms", justify="right")

    import time
    errors = 0
    for t, m in texts:
        syn = IngestSynapse(text=t, metadata=m)
        t0 = time.perf_counter()
        result = handler.handle(syn)
        elapsed = (time.perf_counter() - t0) * 1000

        if result.cid:
            table.add_row(_cid_short(result.cid), t[:60], f"{elapsed:.0f}")
        else:
            console.print(f"[red]✗ Failed:[/red] {result.error}  [dim]({t[:40]}…)[/dim]")
            errors += 1

    # Save FAISS index after ingest
    if hasattr(store, "save"):
        store.save()

    console.print(table)
    console.print(f"\n[green]✓ {len(texts) - errors} ingested[/green]" +
                  (f"  [red]{errors} failed[/red]" if errors else ""))


@app.command()
def query(
    text: str = typer.Argument(..., help="Search query text."),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results to return."),
    show_meta: bool = typer.Option(False, "--meta", help="Show metadata in results."),
):
    """Semantic search over the local Engram store."""
    from engram.miner.query import QueryHandler
    from engram.protocol import QuerySynapse

    store, embedder = _get_store_and_embedder()

    if store.count() == 0:
        console.print("[yellow]Nothing stored yet.[/yellow] Run [bold]engram ingest \"some text\"[/bold] first, then come back and search.")
        raise typer.Exit(0)

    handler = QueryHandler(store=store, embedder=embedder)
    syn = QuerySynapse(query_text=text, top_k=top_k)

    import time
    t0 = time.perf_counter()
    result = handler.handle(syn)
    elapsed = (time.perf_counter() - t0) * 1000

    if result.error:
        console.print(f"[red]Search failed:[/red] {result.error}")
        raise typer.Exit(1)

    console.print(f"\n[bold]Query:[/bold] {text}")
    console.print(f"[dim]{len(result.results)} results in {elapsed:.0f}ms[/dim]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Score", justify="right")
    table.add_column("CID", style="cyan")
    if show_meta:
        table.add_column("Metadata")

    for i, r in enumerate(result.results, 1):
        row = [str(i), f"{r['score']:.4f}", _cid_short(r["cid"])]
        if show_meta:
            row.append(json.dumps(r.get("metadata", {})))
        table.add_row(*row)

    console.print(table)


@app.command()
def status(
    live: bool = typer.Option(False, "--live", "-l", help="Fetch live metagraph data from the chain."),
    netuid: int = typer.Option(None, "--netuid", help="Subnet UID (overrides NETUID env var)."),
):
    """Show local store status and optionally live neuron info from metagraph."""
    store, embedder = _get_store_and_embedder()

    try:
        import engram_core
        rust = "[green]✓ built[/green]"
    except ImportError:
        rust = "[yellow]not built (run: cd engram-core && maturin develop --release)[/yellow]"

    panel = Panel(
        f"[bold]Vectors stored:[/bold]  {store.count()}\n"
        f"[bold]Embedder:[/bold]        {embedder.backend} ({embedder.dim}d)\n"
        f"[bold]engram-core:[/bold]     {rust}\n"
        f"[bold]Index path:[/bold]      {os.getenv('FAISS_INDEX_PATH', './data/engram.index')}\n"
        f"[bold]Network:[/bold]         {os.getenv('SUBTENSOR_NETWORK', 'not set')}\n"
        f"[bold]Wallet:[/bold]          {os.getenv('WALLET_NAME', 'not set')}",
        title="[bold purple]Engram Status[/bold purple]",
        border_style="purple",
    )
    console.print(panel)

    if not live:
        console.print("[dim]Tip: use --live to fetch metagraph data from the chain[/dim]")
        return

    # ── Live metagraph info ───────────────────────────────────────────────────
    import time
    net = os.getenv("SUBTENSOR_ENDPOINT") or os.getenv("SUBTENSOR_NETWORK", "test")
    uid = netuid if netuid is not None else int(os.getenv("NETUID", "99"))

    console.print(f"\n[bold]Fetching metagraph[/bold] | network=[cyan]{net}[/cyan] | netuid=[cyan]{uid}[/cyan]")

    try:
        import bittensor as bt
        subtensor = bt.Subtensor(network=net)
        meta = subtensor.metagraph(netuid=uid)
    except Exception as exc:
        console.print(f"[red]Couldn't connect to the chain:[/red] {exc}\nCheck that SUBTENSOR_NETWORK or SUBTENSOR_ENDPOINT is set correctly in your .env file.")
        return

    # ── Neuron table ──────────────────────────────────────────────────────────
    table = Table(show_header=True, header_style="bold magenta", title=f"Subnet {uid} Neurons")
    table.add_column("UID", justify="right", style="dim")
    table.add_column("Hotkey", style="cyan")
    table.add_column("IP:Port")
    table.add_column("Stake", justify="right")
    table.add_column("Trust", justify="right")
    table.add_column("Incentive", justify="right")
    table.add_column("Health")

    wallet_name = os.getenv("WALLET_NAME", "default")
    wallet_hotkey = os.getenv("WALLET_HOTKEY", "default")
    try:
        my_hotkey = bt.Wallet(name=wallet_name, hotkey=wallet_hotkey).hotkey.ss58_address
    except Exception:
        my_hotkey = None

    axons = meta.axons
    uids_list = meta.uids.tolist()

    # Health-check each miner via SDK
    from engram.sdk import EngramClient, MinerOfflineError
    fallback_port = int(os.getenv("MINER_PORT", "8091"))
    fallback_ip = os.getenv("MINER_IP", "127.0.0.1")

    for uid_i, axon in zip(uids_list, axons):
        ip = axon.ip if axon.ip not in ("0.0.0.0", "0") else fallback_ip
        port = axon.port or fallback_port
        url = f"http://{ip}:{port}"

        # Quick health probe (short timeout)
        try:
            h = EngramClient(url, timeout=3.0).health()
            health = f"[green]✓ {h.get('vectors', '?')}v[/green]"
        except Exception:
            health = "[red]offline[/red]"

        hotkey_short = axon.hotkey[:12] + "…" if axon.hotkey else "—"
        is_me = "← [bold]you[/bold]" if axon.hotkey == my_hotkey else ""

        stake = float(meta.S[uid_i]) if hasattr(meta, "S") else 0.0  # type: ignore[index]
        trust = float(meta.T[uid_i]) if hasattr(meta, "T") else 0.0  # type: ignore[index]
        incentive = float(meta.I[uid_i]) if hasattr(meta, "I") else 0.0  # type: ignore[index]

        table.add_row(
            str(uid_i),
            f"{hotkey_short} {is_me}",
            f"{ip}:{port}",
            f"{stake:.4f}τ",
            f"{trust:.4f}",
            f"{incentive:.4f}",
            health,
        )

    console.print(table)
    console.print(f"\n[dim]Block: {subtensor.block} | {len(uids_list)} neurons registered[/dim]")


@app.command(name="wallet-stats")
def wallet_stats(
    hotkey: str = typer.Argument(None, help="Hotkey SS58 address to inspect (omit for all wallets)."),
    miner: str = typer.Option(None, "--miner", "-m", help="Miner URL (default: MINER_URL env or http://127.0.0.1:8091)."),
    live: bool = typer.Option(False, "--live", "-l", help="Also fetch current TAO stake from the chain."),
    netuid: int = typer.Option(None, "--netuid", help="Subnet UID for stake lookup (overrides NETUID env)."),
):
    """Show per-wallet ingest/query activity tracked by the miner."""
    from engram.miner.wallet_tracker import WalletTracker

    miner_url = miner or os.getenv("MINER_URL", "http://127.0.0.1:8091")

    # Try to fetch live stats from the running miner first
    import urllib.request as _urllib
    import urllib.error as _urlerr

    def _fetch(url: str):
        try:
            with _urllib.urlopen(url, timeout=5) as r:
                import json as _json
                return _json.loads(r.read())
        except Exception:
            return None

    if hotkey:
        data = _fetch(f"{miner_url}/wallet-stats/{hotkey}")
    else:
        data = _fetch(f"{miner_url}/wallet-stats")

    # Fall back to reading the local file if the miner isn't running
    if data is None:
        tracker = WalletTracker()
        if hotkey:
            entry = tracker.get_stats(hotkey)
            data = {**entry, "hotkey": hotkey}
        else:
            data = tracker.summary()

    # ── Stake lookup ──────────────────────────────────────────────────────────
    stakes: dict[str, float] = {}
    if live:
        try:
            import bittensor as bt
            net = os.getenv("SUBTENSOR_ENDPOINT") or os.getenv("SUBTENSOR_NETWORK", "test")
            uid = netuid if netuid is not None else int(os.getenv("NETUID", "99"))
            subtensor = bt.Subtensor(network=net)
            meta = subtensor.metagraph(netuid=uid)
            hotkeys_to_check = [hotkey] if hotkey else [r["hotkey"] for r in (data if isinstance(data, list) else [])]
            for hk in hotkeys_to_check:
                try:
                    idx = [a.hotkey for a in meta.axons].index(hk)
                    stakes[hk] = float(meta.S[idx])
                except (ValueError, IndexError):
                    stakes[hk] = 0.0
        except Exception as exc:
            console.print(f"[yellow]Could not fetch stake: {exc}[/yellow]")

    # ── Display ───────────────────────────────────────────────────────────────
    import time as _time

    if hotkey:
        # Single wallet detail view
        entry = data if isinstance(data, dict) else {}
        last = entry.get("last_seen", 0)
        last_str = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(last)) if last else "never"
        stake_str = f"  τ{stakes.get(hotkey, 0):.4f}" if live else ""

        panel_body = (
            f"[bold]Hotkey:[/bold]        {hotkey}\n"
            f"[bold]Ingest count:[/bold]  {entry.get('ingest_count', 0)}\n"
            f"[bold]Query count:[/bold]   {entry.get('query_count', 0)}\n"
            f"[bold]CIDs tracked:[/bold]  {len(entry.get('cids', []))}\n"
            f"[bold]Last seen:[/bold]     {last_str}"
            + (f"\n[bold]Stake:[/bold]         {stake_str}" if live else "")
        )
        console.print(Panel(panel_body, title=f"[bold purple]Wallet Stats — {hotkey[:16]}…[/bold purple]", border_style="purple"))

        cids = entry.get("cids", [])
        if cids:
            console.print(f"\n[bold]Recent CIDs ({min(len(cids), 20)} of {len(cids)}):[/bold]")
            for c in cids[-20:]:
                console.print(f"  [cyan]{c}[/cyan]")
    else:
        # Summary table
        rows = data if isinstance(data, list) else []
        if not rows:
            console.print("[yellow]No wallet activity recorded yet.[/yellow]")
            return

        table = Table(show_header=True, header_style="bold magenta", title="Wallet Activity")
        table.add_column("Hotkey", style="cyan")
        table.add_column("Ingests", justify="right")
        table.add_column("Queries", justify="right")
        table.add_column("CIDs", justify="right")
        if live:
            table.add_column("Stake τ", justify="right")
        table.add_column("Last seen")

        for row in rows:
            hk = row["hotkey"]
            last = row.get("last_seen", 0)
            last_str = _time.strftime("%m-%d %H:%M", _time.localtime(last)) if last else "—"
            cells = [
                hk[:20] + "…" if len(hk) > 22 else hk,
                str(row.get("ingest_count", 0)),
                str(row.get("query_count", 0)),
                str(row.get("cid_count", 0)),
            ]
            if live:
                cells.append(f"{stakes.get(hk, 0):.4f}")
            cells.append(last_str)
            table.add_row(*cells)

        console.print(table)


@app.command()
def demo():
    """Run the local end-to-end demo."""
    import subprocess
    subprocess.run([sys.executable, "scripts/run_demo.py"])


@app.command(name="init")
def init(
    role: str = typer.Option(None, "--role", "-r", help="'miner', 'validator', or 'dev'"),
    env_file: Path = typer.Option(Path(".env"), "--out", "-o", help="Path to write the .env file."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing .env without prompting."),
):
    """
    Interactive setup wizard — creates a .env file and verifies your installation.

    Guides you through wallet, network, and embedding configuration.
    Safe to re-run: it will prompt before overwriting an existing .env.
    """
    console.print(Panel(
        "[bold purple]Welcome to Engram[/bold purple]\n\n"
        "This wizard will help you set up your environment.\n"
        "It creates a [bold].env[/bold] file with your configuration.\n\n"
        "[dim]Press Ctrl+C at any time to cancel.[/dim]",
        border_style="purple",
    ))

    # ── Guard: existing .env ──────────────────────────────────────────────────
    if env_file.exists() and not force:
        overwrite = typer.confirm(f"\n'{env_file}' already exists. Overwrite it?", default=False)
        if not overwrite:
            console.print("[yellow]Skipped.[/yellow] Run with --force to overwrite without prompting.")
            raise typer.Exit(0)

    # ── Role ──────────────────────────────────────────────────────────────────
    if role is None:
        role = typer.prompt(
            "\nWhat are you setting up?",
            default="dev",
            prompt_suffix="\n  [miner] Run a miner node and earn TAO\n  [validator] Run a validator and set weights\n  [dev] Use the SDK locally (no Bittensor needed)\n> ",
        ).strip().lower()

    if role not in ("miner", "validator", "dev"):
        console.print(f"[red]Unknown role '{role}'.[/red] Choose miner, validator, or dev.")
        raise typer.Exit(1)

    config: dict[str, str] = {}

    # ── Network ───────────────────────────────────────────────────────────────
    if role in ("miner", "validator"):
        console.print("\n[bold]Network[/bold]")
        network = typer.prompt(
            "Subtensor network",
            default="test",
            prompt_suffix="\n  [finney] Mainnet  [test] Testnet  [ws://...] Custom endpoint\n> ",
        ).strip()
        config["SUBTENSOR_NETWORK"] = network

        netuid = typer.prompt("Subnet UID", default="450").strip()
        config["NETUID"] = netuid

    # ── Wallet ────────────────────────────────────────────────────────────────
    if role in ("miner", "validator"):
        console.print("\n[bold]Bittensor Wallet[/bold]")
        wallet_name = typer.prompt("Wallet name", default="default").strip()
        wallet_hotkey = typer.prompt(
            "Hotkey name",
            default="miner" if role == "miner" else "validator",
        ).strip()
        config["WALLET_NAME"] = wallet_name
        config["WALLET_HOTKEY"] = wallet_hotkey

    # ── Miner-specific ────────────────────────────────────────────────────────
    if role == "miner":
        console.print("\n[bold]Miner Settings[/bold]")
        external_ip = typer.prompt("Your public IP address (must be reachable by validators)", default="").strip()
        if external_ip:
            config["EXTERNAL_IP"] = external_ip
        config["MINER_PORT"] = typer.prompt("Miner port", default="8091").strip()

        use_qdrant = typer.confirm("Use Qdrant vector store? (recommended for production; FAISS is fine for testing)", default=False)
        config["VECTOR_STORE_BACKEND"] = "qdrant" if use_qdrant else "faiss"
        if use_qdrant:
            config["QDRANT_HOST"] = typer.prompt("Qdrant host", default="localhost").strip()
            config["QDRANT_PORT"] = typer.prompt("Qdrant port", default="6333").strip()

    # ── Embedder ──────────────────────────────────────────────────────────────
    console.print("\n[bold]Embedding Model[/bold]")
    use_local = typer.confirm(
        "Use local embedder? (no OpenAI key needed, lower quality)",
        default=(role == "dev"),
    )
    config["USE_LOCAL_EMBEDDER"] = "true" if use_local else "false"

    if not use_local:
        openai_key = typer.prompt("OpenAI API key", default="", hide_input=True).strip()
        if openai_key:
            config["OPENAI_API_KEY"] = openai_key
        else:
            console.print("[yellow]No key entered — add OPENAI_API_KEY to your .env manually.[/yellow]")

    # ── Write .env ────────────────────────────────────────────────────────────
    lines = [
        "# Engram configuration — generated by `engram init`",
        f"# Role: {role}",
        "",
    ]
    for key, value in config.items():
        lines.append(f"{key}={value}")

    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    console.print(f"\n[green]✓ Written:[/green] {env_file.resolve()}")

    # ── Verify installation ───────────────────────────────────────────────────
    console.print("\n[bold]Checking your installation…[/bold]")

    checks = []

    # Python package
    try:
        import engram  # noqa: F401
        checks.append(("[green]✓[/green]", "engram package", "installed"))
    except ImportError:
        checks.append(("[red]✗[/red]", "engram package", "not found — run: pip install -e ."))

    # Rust core
    try:
        import engram_core  # noqa: F401
        checks.append(("[green]✓[/green]", "engram-core (Rust)", "built"))
    except ImportError:
        checks.append(("[yellow]~[/yellow]", "engram-core (Rust)", "not built (optional, improves performance)"))

    # Embedder
    if not use_local:
        try:
            from openai import OpenAI  # noqa: F401
            checks.append(("[green]✓[/green]", "openai", "installed"))
        except ImportError:
            checks.append(("[red]✗[/red]", "openai", "not installed — run: pip install openai"))
    else:
        try:
            from sentence_transformers import SentenceTransformer  # noqa: F401
            checks.append(("[green]✓[/green]", "sentence-transformers", "installed"))
        except ImportError:
            checks.append(("[red]✗[/red]", "sentence-transformers", "not installed — run: pip install sentence-transformers"))

    # Bittensor (only needed for miner/validator)
    if role in ("miner", "validator"):
        try:
            import bittensor  # noqa: F401
            checks.append(("[green]✓[/green]", "bittensor", "installed"))
        except ImportError:
            checks.append(("[red]✗[/red]", "bittensor", "not installed — run: pip install bittensor"))

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(justify="center", width=3)
    table.add_column(style="bold")
    table.add_column(style="dim")
    for status, name, note in checks:
        table.add_row(status, name, note)
    console.print(table)

    # ── Next steps ────────────────────────────────────────────────────────────
    console.print()
    if role == "miner":
        console.print(Panel(
            "[bold]Next steps:[/bold]\n\n"
            "1. Register your hotkey:\n"
            f"   [cyan]btcli subnet register --netuid {config.get('NETUID', '450')} "
            f"--wallet.name {config.get('WALLET_NAME', 'default')} "
            f"--wallet.hotkey {config.get('WALLET_HOTKEY', 'miner')}[/cyan]\n\n"
            "2. Start your miner:\n"
            "   [cyan]python neurons/miner.py[/cyan]\n\n"
            "3. Check it's live:\n"
            f"   [cyan]curl http://localhost:{config.get('MINER_PORT', '8091')}/health[/cyan]",
            title="[bold purple]You're almost ready![/bold purple]",
            border_style="purple",
        ))
    elif role == "validator":
        console.print(Panel(
            "[bold]Next steps:[/bold]\n\n"
            "1. Register your hotkey:\n"
            f"   [cyan]btcli subnet register --netuid {config.get('NETUID', '450')} "
            f"--wallet.name {config.get('WALLET_NAME', 'default')} "
            f"--wallet.hotkey {config.get('WALLET_HOTKEY', 'validator')}[/cyan]\n\n"
            "2. Start your validator:\n"
            "   [cyan]python neurons/validator.py[/cyan]",
            title="[bold purple]You're almost ready![/bold purple]",
            border_style="purple",
        ))
    else:
        console.print(Panel(
            "[bold]Try it out:[/bold]\n\n"
            "  [cyan]engram ingest \"The transformer architecture changed everything.\"[/cyan]\n"
            "  [cyan]engram query \"how does attention work?\"[/cyan]\n\n"
            "Or use the SDK:\n"
            "  [cyan]from engram.sdk import EngramClient[/cyan]\n"
            "  [cyan]client = EngramClient(\"http://127.0.0.1:8091\")[/cyan]\n"
            "  [cyan]cid = client.ingest(\"Hello, Engram!\")[/cyan]",
            title="[bold purple]Setup complete![/bold purple]",
            border_style="purple",
        ))


if __name__ == "__main__":
    app()
