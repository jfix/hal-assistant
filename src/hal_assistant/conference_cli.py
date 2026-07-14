from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from .conference_enrichment import (
    export_conference_queue,
    export_imported_publications,
    import_conference_reviews,
)
from .models import Publication

app = typer.Typer(
    no_args_is_help=True,
    help="Prepare and import sourced conference enrichment reviews.",
)


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


@app.command("import")
def import_reviews(
    source: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    workbook: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path(
        "output/conference-enrichment/publications-enriched.json"
    ),
) -> None:
    """Apply accepted workbook rows to publications using stable publication IDs."""
    payload = json.loads(source.read_text(encoding="utf-8"))
    publications = [Publication.model_validate(item) for item in payload]
    publications, errors = import_conference_reviews(publications, workbook)
    if errors:
        for error in errors:
            typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1)
    output_path = export_imported_publications(publications, output)
    typer.echo(f"Enriched publications: {output_path}")


if __name__ == "__main__":
    app()
