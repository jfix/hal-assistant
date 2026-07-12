from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .production import prepare_production_batch

app = typer.Typer(
    no_args_is_help=True,
    help="Freeze a validated HAL production batch into an immutable archive.",
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
                "Preproduction test ledger; defaults to the stage-specific ledger "
                "in XML_DIR, with legacy fallback."
            )
        ),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "-o",
            help="Archive root; a unique timestamp-and-checksum batch is created inside it.",
        ),
    ] = Path("output/hal-archive"),
) -> None:
    """Archive accepted notices, their preproduction ledger, and a checksum manifest."""
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
    typer.echo(f"Immutable batch directory: {batch.output_dir}")
    typer.echo(f"Manifest: {batch.manifest_path}")
    typer.echo(f"Archive index: {batch.output_dir.parent / 'index.json'}")
    typer.echo("No production submission was performed.")


if __name__ == "__main__":
    app()
