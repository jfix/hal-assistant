from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .review_import import import_review_workbook

app = typer.Typer(no_args_is_help=True, help="Import Florence's validated HAL review workbook.")


@app.command()
def import_review(
    workbook: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o")] = Path(
        "output/review-import"
    ),
) -> None:
    """Validate approved workbook rows and create HAL-ready JSON."""
    try:
        result = import_review_workbook(workbook, output_dir)
    except (OSError, ValueError) as exc:
        typer.echo(f"Import failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(f"Approved: {result.approved_count}")
    typer.echo(f"Already on HAL: {result.already_on_hal_count}")
    typer.echo(f"Blocked: {result.blocked_count}")
    typer.echo(f"Records with warnings: {result.warning_count}")
    typer.echo(f"HAL-ready JSON: {result.approved_path}")
    typer.echo(f"Import report: {result.report_path}")
    if result.blocked_count:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
