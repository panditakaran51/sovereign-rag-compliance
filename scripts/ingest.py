#!/usr/bin/env python3
"""
Ingest regulation PDFs into Qdrant.

Usage:
    python scripts/ingest.py --corpus docs/regulations/
    python scripts/ingest.py --file docs/regulations/dora.pdf
"""
import argparse
import sys
import time
from pathlib import Path

# Allow imports from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel

from backend.ingestion.loader import load_pdf, load_directory
from backend.ingestion.chunker import chunk_pages
from backend.ingestion.embedder import upsert_chunks

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest regulation documents into Qdrant")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--corpus", type=Path, help="Directory of PDFs to ingest")
    group.add_argument("--file",   type=Path, help="Single PDF to ingest")
    args = parser.parse_args()

    start = time.perf_counter()

    if args.file:
        if not args.file.exists():
            console.print(f"[red]File not found:[/red] {args.file}")
            sys.exit(1)
        console.print(f"[cyan]Loading[/cyan] {args.file.name}...")
        pages = load_pdf(args.file)
    else:
        if not args.corpus.exists():
            console.print(f"[red]Directory not found:[/red] {args.corpus}")
            sys.exit(1)
        console.print(f"[cyan]Loading PDFs from[/cyan] {args.corpus}...")
        pages = load_directory(args.corpus)

    if not pages:
        console.print("[yellow]No text extracted — are the PDFs text-based (not scanned images)?[/yellow]")
        sys.exit(1)

    console.print(f"  Loaded [bold]{len(pages)}[/bold] pages")

    chunks = chunk_pages(pages)
    console.print(f"  Produced [bold]{len(chunks)}[/bold] chunks")

    total = upsert_chunks(chunks)

    elapsed = time.perf_counter() - start
    console.print(Panel(
        f"[green]Done.[/green] Upserted [bold]{total}[/bold] chunks in {elapsed:.1f}s",
        title="Ingestion complete",
    ))


if __name__ == "__main__":
    main()
