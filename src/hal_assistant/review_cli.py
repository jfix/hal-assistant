from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from .review_import import import_review_workbook

app = typer.Typer(no_args_is_help=True, help="Import Florence's validated HAL review workbook.")

HAL_DOCUMENT_TYPES = {
    "book": "OUV",
    "edited_book": "DOUV",
    "journal_issue": "DOUV",
    "book_chapter": "COUV",
    "dictionary_entry": "COUV",
    "conference_paper": "COMM",
    "journal_article": "ART",
}


def add_hal_document_types(path: Path) -> list[dict[str, Any]]:
    """Add the HAL typology expected by the AOfr XML builder."""
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("HAL-ready JSON must contain an array of records")

    for record in records:
        publication_type = str(record.get("publication_type") or "")
        document_type = HAL_DOCUMENT_TYPES.get(publication_type)
        if document_type is None:
            raise ValueError(
                f"Unsupported publication type for {record.get('publication_id')}: "
                f"{publication_type or '<blank>'}"
            )
        record["document_type"] = document_type
        if publication_type == "journal_issue":
            record["container_title"] = record.get("journal_title")
        elif document_type == "COUV":
            record["container_title"] = record.get("book_title")
        elif document_type == "ART":
            record["container_title"] = record.get("journal_title")
        elif document_type == "COMM" and record.get("book_title"):
            record["container_title"] = record.get("book_title")

    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return records


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
        if not result.blocked_count:
            add_hal_document_types(result.approved_path)
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
