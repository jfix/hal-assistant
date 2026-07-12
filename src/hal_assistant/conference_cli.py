from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from .conference_enrichment import export_conference_queue
from .models import Publication

app = typer.Typer(no_args_is_help=True, help="Prepare a sourced conference enrichment review queue.")


@app.command()
def build(
    source: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o")] = Path(
        "output/conference-enrichment"
    ),
) -> None:
    """Create JSON research tasks and an editable review workbook for COMM records."""
    payload = json.loads(source.read_text(encoding="utf-8"))
    publications = [Publication.model_validate(item) for item in payload]
    json_path, workbook_path = export_conference_queue(publications, output_dir)
    typer.echo(f"Queue JSON: {json_path}")
    typer.echo(f"Review workbook: {workbook_path}")


if __name__ == "__main__":
    app()
