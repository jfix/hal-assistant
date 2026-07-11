from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .production import prepare_production_batch

app = typer.Typer(
    no_args_is_help=True,
    help="Freeze a validated HAL production batch.",
)


@app.command()
def prepare(
    xml_dir: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=False, readable=True),
    ],
    ledger: Annotated[
        Path | None,
        typer.Option(
            help=(
                "Preproduction submission ledger; defaults to "
                "XML_DIR/submission-ledger.json."
            )
        ),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "-o",
            help="New, empty directory for the frozen batch.",
        ),
    ] = Path("output/hal-production"),
) -> None:
    """Copy only preproduction-accepted notices and write a checksum manifest."""
    try:
        batch = prepare_production_batch(
            xml_dir,
            ledger_path=ledger,
            output_dir=output_dir,
        )
    except (OSError, ValueError) as exc:
        typer.echo(f"Production batch refused: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(f"Production-ready XML files: {len(batch.files)}")
    typer.echo(f"Batch directory: {batch.output_dir}")
    typer.echo(f"Manifest: {batch.manifest_path}")
    typer.echo("No production submission was performed.")


if __name__ == "__main__":
    app()
