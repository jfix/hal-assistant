from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .update import update_batch

app = typer.Typer(no_args_is_help=True, help="Safely test or apply exact-version HAL updates.")


@app.command()
def update(
    batch_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    test: Annotated[bool, typer.Option("--test/--no-test")] = True,
    execute: Annotated[bool, typer.Option(help="Required for real production updates.")] = False,
    on_behalf_of: Annotated[str | None, typer.Option(help="HAL On-Behalf-Of value.")] = None,
    limit: Annotated[int | None, typer.Option(help="Consider at most N records.")] = None,
    fail_fast: Annotated[bool, typer.Option("--fail-fast/--continue-on-error")] = False,
    resume: Annotated[bool, typer.Option("--resume/--no-resume")] = False,
) -> None:
    """PUT complete AOfr XML to exact HAL record versions; X-test is the default."""
    try:
        results, ledger = update_batch(
            batch_dir,
            test=test,
            execute=execute,
            on_behalf_of=on_behalf_of,
            limit=limit,
            fail_fast=fail_fast,
            resume=resume,
        )
    except (RuntimeError, ValueError) as exc:
        typer.echo(f"Refused: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    accepted = sum(item.accepted for item in results)
    typer.echo(f"HAL update accepted/test-validated: {accepted}/{len(results)}")
    typer.echo(f"Rejected: {len(results) - accepted}")
    typer.echo(f"Ledger: {ledger}")
    if accepted != len(results):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
