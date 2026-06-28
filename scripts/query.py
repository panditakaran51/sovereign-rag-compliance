#!/usr/bin/env python3
"""
Interactive RAG query loop — Phase 2.

Usage:
    python scripts/query.py                        # interactive REPL
    python scripts/query.py "Your question here"   # one-shot
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from backend.rag.pipeline import query

console = Console()

_CONFIDENCE_LABELS = {
    1: ("[bold red]▌ 1/5 — Not supported[/bold red]", "red"),
    2: ("[bold yellow]▌ 2/5 — Weakly supported[/bold yellow]", "yellow"),
    3: ("[bold yellow]▌ 3/5 — Reasonably supported[/bold yellow]", "yellow"),
    4: ("[bold green]▌ 4/5 — Well supported[/bold green]", "green"),
    5: ("[bold green]▌ 5/5 — Fully supported[/bold green]", "green"),
}


def run_query(question: str) -> None:
    t0 = time.perf_counter()
    tokens_collected = []

    def on_rewrite(rewritten: str):
        if rewritten.strip().lower() != question.strip().lower():
            console.print(f"\n[dim]Query expanded →[/dim] [italic]{rewritten}[/italic]")

    console.print("\n[dim]Retrieving relevant passages...[/dim]")

    # Stream tokens into a Live panel so the user sees text appear in real time
    with Live(
        Panel("", title="[bold green]Answer[/bold green]", border_style="green", padding=(1, 2)),
        refresh_per_second=8,
        console=console,
    ) as live:
        def on_token(token: str):
            tokens_collected.append(token)
            current_text = "".join(tokens_collected)
            live.update(Panel(
                Markdown(current_text),
                title="[bold green]Answer[/bold green]",
                border_style="green",
                padding=(1, 2),
            ))

        answer = query(question, on_token=on_token, on_rewrite=on_rewrite)

    # Confidence badge
    label, color = _CONFIDENCE_LABELS.get(answer.confidence, ("▌ ?/5", "white"))
    console.print(f"\n[bold]Confidence:[/bold] {label}", highlight=False)
    if answer.flagged:
        console.print(
            Panel(
                "[yellow]This answer scored below the confidence threshold "
                "and should be reviewed by a human expert before acting on it.[/yellow]",
                border_style="yellow",
            )
        )

    # Source table
    if answer.sources:
        table = Table(title="Sources", box=box.SIMPLE, show_lines=True)
        table.add_column("Rank", style="dim", width=6)
        table.add_column("Document", style="cyan")
        table.add_column("Page", justify="right", width=6)
        table.add_column("Articles", width=12)
        table.add_column("Dense", justify="right", width=7)
        table.add_column("BM25", justify="right", width=7)
        table.add_column("RRF", justify="right", width=8)
        table.add_column("Excerpt", style="dim", max_width=55)

        for i, chunk in enumerate(answer.sources, 1):
            table.add_row(
                str(i),
                chunk.source_file,
                str(chunk.page_number),
                ", ".join(chunk.articles) or "—",
                f"#{chunk.dense_rank + 1}" if chunk.dense_rank >= 0 else "—",
                f"#{chunk.bm25_rank + 1}" if chunk.bm25_rank >= 0 else "—",
                f"{chunk.score:.4f}",
                chunk.text[:100].replace("\n", " ") + "…",
            )
        console.print(table)

    console.print(f"[dim]Total time: {time.perf_counter() - t0:.1f}s[/dim]\n")


def main() -> None:
    if len(sys.argv) > 1:
        run_query(" ".join(sys.argv[1:]))
        return

    console.print(Panel(
        "[bold]Sovereign RAG — EU Compliance Assistant[/bold]\n"
        "Phase 2: Hybrid retrieval · Query rewriting · Confidence scoring\n"
        "Type your question and press Enter. Type [bold]exit[/bold] to quit.",
        border_style="blue",
    ))

    while True:
        try:
            question = console.input("\n[bold blue]Question:[/bold blue] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Bye.[/dim]")
            break

        if not question:
            continue
        if question.lower() in {"exit", "quit", "q"}:
            console.print("[dim]Bye.[/dim]")
            break

        run_query(question)


if __name__ == "__main__":
    main()
