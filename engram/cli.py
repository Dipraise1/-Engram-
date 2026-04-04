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
        console.print("[red]Invalid JSON in --meta[/red]")
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
            console.print(f"[red]Not a directory: {dir}[/red]")
            raise typer.Exit(1)
        suffixes = {".txt", ".md", ".jsonl"}
        files = sorted(p for p in dir.rglob("*") if p.suffix in suffixes and p.is_file())
        if not files:
            console.print(f"[yellow]No .txt / .md / .jsonl files found in {dir}[/yellow]")
            raise typer.Exit(0)
        for p in files:
            texts.extend(_load_file(p, meta))
        console.print(f"[dim]Loaded {len(texts)} records from {len(files)} files in {dir}[/dim]")
    elif file:
        if not file.exists():
            console.print(f"[red]File not found: {file}[/red]")
            raise typer.Exit(1)
        texts = _load_file(file, meta)
        console.print(f"[dim]Loaded {len(texts)} records from {file}[/dim]")
    elif text:
        texts = [(text, meta)]
    else:
        console.print("[red]Provide text as argument or --file[/red]")
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
            console.print(f"[red]FAILED:[/red] {result.error} | {t[:40]}")
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
        console.print("[yellow]Store is empty. Run 'engram ingest' first.[/yellow]")
        raise typer.Exit(0)

    handler = QueryHandler(store=store, embedder=embedder)
    syn = QuerySynapse(query_text=text, top_k=top_k)

    import time
    t0 = time.perf_counter()
    result = handler.handle(syn)
    elapsed = (time.perf_counter() - t0) * 1000

    if result.error:
        console.print(f"[red]Query error: {result.error}[/red]")
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
        console.print(f"[red]Failed to connect: {exc}[/red]")
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

        stake = float(meta.S[uid_i]) if hasattr(meta, "S") else 0.0
        trust = float(meta.T[uid_i]) if hasattr(meta, "T") else 0.0
        incentive = float(meta.I[uid_i]) if hasattr(meta, "I") else 0.0

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


@app.command()
def demo():
    """Run the local end-to-end demo."""
    import subprocess
    subprocess.run([sys.executable, "scripts/run_demo.py"])


if __name__ == "__main__":
    app()
