from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from .hal_requirements import audit_records

app = typer.Typer(
    add_completion=False,
    help="Audit normalized publications against HAL requirements.",
)


@app.command()
def main(
    source: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Optional JSON audit output path."),
    ] = None,
    show_records: Annotated[
        bool,
        typer.Option(
            "--show-records",
            help="Print blocked publication IDs and missing fields.",
        ),
    ] = False,
) -> None:
    """Report which publications are HAL-ready before XML generation."""
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise typer.BadParameter("Source must be a JSON array")

    audit = audit_records(payload)
    typer.echo(
        f"HAL readiness: {audit['ready']}/{audit['total']} ready; "
        f"blocked: {audit['blocked']}"
    )
    for document_type, summary in audit["types"].items():
        typer.echo(
            f"  {document_type}: {summary['ready']}/{summary['total']} ready; "
            f"blocked: {summary['blocked']}"
        )
        for field, count in summary["missing_fields"].items():
            typer.echo(f"    missing {field}: {count}")

    if show_records:
        for record in audit["records"]:
            if record["ready"]:
                continue
            fields = ", ".join(record["missing_required_fields"])
            typer.echo(
                f"  {record['publication_id']} "
                f"[{record['document_type']}]: {fields}"
            )

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(audit, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        typer.echo(f"Audit: {output}")

    if audit["blocked"]:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
