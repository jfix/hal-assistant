from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from .models import Publication, PublicationType

REQUIRED_COMM_FIELDS = (
    "conference_title",
    "conference_start_date",
    "conference_city",
    "conference_country",
)


def conference_enrichment_queue(
    publications: list[Publication],
) -> list[dict[str, object]]:
    """Build a deterministic research queue without fabricating missing dates."""
    queue: list[dict[str, object]] = []
    for item in publications:
        if item.publication_type is not PublicationType.CONFERENCE_PAPER:
            continue
        missing = [field for field in REQUIRED_COMM_FIELDS if not getattr(item, field)]
        if not missing:
            continue
        year_hint = item.year
        queries = [
            f'"{item.title}" colloque programme',
            f'"{item.title}" {year_hint or ""} Fabula'.strip(),
            f'"{item.conference_title or item.title}" programme PDF',
        ]
        queue.append(
            {
                "publication_id": item.publication_id,
                "title": item.title,
                "publication_year": item.year,
                "conference_title": item.conference_title,
                "conference_start_date": item.conference_start_date,
                "conference_end_date": item.conference_end_date,
                "conference_city": item.conference_city,
                "conference_country": item.conference_country,
                "missing_fields": missing,
                "preferred_sources": [
                    "Fabula.org",
                    "official university programme",
                    "official conference PDF",
                ],
                "search_queries": queries,
                "raw_citation": item.raw_citation,
            }
        )
    return queue


def export_conference_queue(
    publications: list[Publication], output_dir: str | Path
) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    queue = conference_enrichment_queue(publications)

    json_path = output / "conference-enrichment-queue.json"
    json_path.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "COMM review"
    headers = [
        "publication_id",
        "title",
        "publication_year",
        "conference_title",
        "conference_start_date",
        "conference_end_date",
        "conference_city",
        "conference_country",
        "missing_fields",
        "source_url",
        "source_name",
        "confidence",
        "review_status",
        "review_note",
        "raw_citation",
    ]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:O{max(1, len(queue) + 1)}"

    for record in queue:
        sheet.append(
            [
                record["publication_id"],
                record["title"],
                record["publication_year"],
                record["conference_title"],
                record["conference_start_date"],
                record["conference_end_date"],
                record["conference_city"],
                record["conference_country"],
                "; ".join(record["missing_fields"]),
                None,
                None,
                None,
                "pending",
                None,
                record["raw_citation"],
            ]
        )

    widths = {
        "A": 24,
        "B": 58,
        "C": 16,
        "D": 58,
        "E": 22,
        "F": 22,
        "G": 24,
        "H": 22,
        "I": 38,
        "J": 55,
        "K": 30,
        "L": 14,
        "M": 16,
        "N": 55,
        "O": 100,
    }
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width

    instructions = workbook.create_sheet("Instructions")
    instructions.append(["Rule", "Description"])
    instructions.append(
        ["Dates", "Use exact source dates only; never convert a bare year to 1 January."]
    )
    instructions.append(
        ["Sources", "Prefer Fabula.org, then official programmes and conference PDFs."]
    )
    instructions.append(
        ["Confidence", "Use high, medium, or low and explain ambiguity in review_note."]
    )
    instructions.append(
        ["Decision", "Set review_status to accepted, rejected, or needs_review."]
    )
    for cell in instructions[1]:
        cell.font = Font(bold=True)
    instructions.column_dimensions["A"].width = 20
    instructions.column_dimensions["B"].width = 100

    workbook_path = output / "conference-enrichment-review.xlsx"
    workbook.save(workbook_path)
    return json_path, workbook_path
