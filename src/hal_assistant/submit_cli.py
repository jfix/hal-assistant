from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .sword import submit_batch

app = typer.Typer(
    no_args_is_help=True,
    help="Validate or submit HAL notices independently with safe resume support.",
)


@app.command()
def submit(
    xml_dir: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=False, readable=True),
    ],
    environment: Annotated[
        str,
        typer.Option(help="HAL endpoint: preprod or production."),
    ] = "preprod",
    test: Annotated[
        bool,
        typer.Option("--test/--no-test", help="Send X-test: 1; enabled by default."),
    ] = True,
    execute: Annotated[
        bool,
        typer.Option(help="Required for non-test production writes."),
    ] = False,
    on_behalf_of: Annotated[
        str | None,
        typer.Option(help="HAL On-Behalf-Of value."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(help="Consider at most N XML notices."),
    ] = None,
    fail_fast: Annotated[
        bool,
        typer.Option(
            "--fail-fast/--continue-on-error",
            help="Stop on the first rejected notice; disabled by default.",
        ),
    ] = False,
    resume: Annotated[
        bool,
        typer.Option(
            "--resume/--no-resume",
            help="Reuse the stage ledger and skip notices already accepted.",
        ),
    ] = False,
    force_title_duplicate: Annotated[
        str | None,
        typer.Option(
            "--force-title-duplicate",
            help=(
                "Retry exactly one verified HAL title-only false positive by XML basename. "
                "Production writes require a matching forced production X-test checksum."
            ),
        ),
    ] = None,
) -> None:
    """Process each XML notice independently and write a cumulative ledger."""
    try:
        results, ledger = submit_batch(
            xml_dir,
            environment=environment,
            test=test,
            execute=execute,
            on_behalf_of=on_behalf_of,
            limit=limit,
            fail_fast=fail_fast,
            resume=resume,
            force_title_duplicate=force_title_duplicate,
        )
    except (RuntimeError, ValueError) as exc:
        typer.echo(f"Refused: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    accepted = sum(item.accepted for item in results)
    rejected = sum(not item.accepted for item in results)
    typer.echo(f"HAL accepted/test-validated: {accepted}/{len(results)}")
    typer.echo(f"Rejected: {rejected}")
    typer.echo(f"Ledger: {ledger}")
    if rejected:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
