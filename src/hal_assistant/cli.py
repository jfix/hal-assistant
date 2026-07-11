from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Annotated

import typer

from .exporters import export_excel, export_json
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


@app.command()
def version() -> None:
    """Print the installed HAL Assistant version."""
    from . import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()
