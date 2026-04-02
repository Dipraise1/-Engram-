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
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

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

    if file:
        if not file.exists():
            console.print(f"[red]File not found: {file}[/red]")
            raise typer.Exit(1)
        if file.suffix == ".jsonl":
            for line in file.read_text().splitlines():
                if line.strip():
                    obj = json.loads(line)
                    texts.append((obj["text"], obj.get("metadata", meta)))
        else:
            for line in file.read_text().splitlines():
                if line.strip():
                    texts.append((line.strip(), meta))
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
def status():
    """Show local store status."""
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


@app.command()
def demo():
    """Run the local end-to-end demo."""
    import subprocess
    subprocess.run([sys.executable, "scripts/run_demo.py"])


if __name__ == "__main__":
    app()
