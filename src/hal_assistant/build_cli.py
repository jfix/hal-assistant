from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .atomic_xml import build_xml_batch

app = typer.Typer(no_args_is_help=True, help="Build HAL XML with typology-aware validation.")


@app.command()
def build(
    source: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    domain: Annotated[
        str,
        typer.Option(help="Required HAL scientific-domain code."),
    ],
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", "-o"),
    ] = Path("output/hal-xml"),
    domain_label: Annotated[
        str | None,
        typer.Option(help="Optional human-readable HAL domain label."),
    ] = None,
    idhal: Annotated[
        str | None,
        typer.Option(help="IdHAL attached to the selected author."),
    ] = None,
    idhal_author: Annotated[
        str | None,
        typer.Option(help="Author name that should receive --idhal."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(help="Build only the first N records."),
    ] = None,
) -> None:
    """Build one XML file per publication and block invalid records individually."""
    results = build_xml_batch(
        source,
        output_dir,
        domain=domain,
        domain_label=domain_label,
        idhal=idhal,
        idhal_author=idhal_author,
        limit=limit,
    )
    valid = sum(not item.errors for item in results)
    blocked = len(results) - valid
    typer.echo(f"Generated {valid} XML files; blocked: {blocked}")
    typer.echo(f"Manifest: {output_dir / 'manifest.json'}")
    if blocked:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
