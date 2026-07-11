from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Annotated

import typer

from .exporters import export_excel, export_json
from .hal import match_publications
from .models import Publication
from .parser import parse_docx

app = typer.Typer(no_args_is_help=True, help="Prepare publication metadata for HAL workflows.")


@app.command()
def parse(
    document: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", "-o"),
    ] = Path("output"),
    author: Annotated[
        str | None,
        typer.Option(help="Default author added to every record."),
    ] = None,
) -> None:
    """Parse a DOCX publication list and export JSON and Excel review files."""
    publications = parse_docx(document, default_author=author)
    json_path = export_json(publications, output_dir / "publications.json")
    excel_path = export_excel(publications, output_dir / "publications.xlsx")

    typer.echo(f"Parsed {len(publications)} publications")
    for publication_type, count in sorted(
        Counter(item.publication_type.value for item in publications).items()
    ):
        typer.echo(f"  {publication_type}: {count}")
    typer.echo(f"JSON:  {json_path}")
    typer.echo(f"Excel: {excel_path}")


@app.command("match-hal")
def match_hal(
    source: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", "-o"),
    ] = Path("output/hal-review"),
) -> None:
    """Search HAL without modifying it and export a match-review report."""
    payload = json.loads(source.read_text(encoding="utf-8"))
    publications = [Publication.model_validate(item) for item in payload]
    match_publications(publications)
    json_path = export_json(publications, output_dir / "publications-with-hal.json")
    excel_path = export_excel(publications, output_dir / "publications-with-hal.xlsx")

    statuses = Counter(
        item.hal_match.status.value
        for item in publications
        if item.hal_match is not None
    )
    typer.echo(f"Checked {len(publications)} publications against HAL")
    for status, count in sorted(statuses.items()):
        typer.echo(f"  {status}: {count}")
    typer.echo(f"JSON:  {json_path}")
    typer.echo(f"Excel: {excel_path}")


@app.command()
def version() -> None:
    """Print the installed HAL Assistant version."""
    from . import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()
