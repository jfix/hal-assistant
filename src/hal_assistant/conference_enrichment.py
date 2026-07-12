from __future__ import annotations

import json
import re
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

from .models import (
    EnrichmentConfidence,
    MetadataEvidence,
    Publication,
    PublicationType,
)

REQUIRED_COMM_FIELDS = (
    "conference_title",
    "conference_start_date",
    "conference_city",
    "conference_country",
)
REVIEW_FIELDS = (
    "conference_title",
    "conference_start_date",
    "conference_end_date",
    "conference_city",
    "conference_country",
)
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def _review_rows(workbook_path: str | Path) -> list[dict[str, object]]:
    workbook = load_workbook(workbook_path, data_only=True)
    if "COMM review" not in workbook.sheetnames:
        raise ValueError("Review workbook has no 'COMM review' sheet")
    sheet = workbook["COMM review"]
    headers = [cell.value for cell in sheet[1]]
    required_headers = {
        "publication_id",
        "source_url",
        "source_name",
        "confidence",
        "review_status",
        *REVIEW_FIELDS,
    }
    missing_headers = required_headers.difference(headers)
    if missing_headers:
        raise ValueError(f"Review workbook is missing columns: {sorted(missing_headers)}")
    return [dict(zip(headers, values, strict=True)) for values in sheet.iter_rows(min_row=2, values_only=True)]


def import_conference_reviews(
    publications: list[Publication], workbook_path: str | Path
) -> tuple[list[Publication], list[str]]:
    """Apply accepted sourced reviews by stable publication ID.

    Only accepted rows are applied. Exact dates must use ISO YYYY-MM-DD, and every
    changed field receives a provenance record. Existing non-empty values may only
    be replaced when the accepted workbook row supplies a different sourced value.
    """
    by_id = {item.publication_id: item for item in publications}
    errors: list[str] = []
    seen_ids: set[str] = set()

    for row_number, row in enumerate(_review_rows(workbook_path), start=2):
        status = str(row.get("review_status") or "").strip().casefold()
        if status != "accepted":
            continue
        publication_id = str(row.get("publication_id") or "").strip()
        if not publication_id:
            errors.append(f"row {row_number}: missing publication_id")
            continue
        if publication_id in seen_ids:
            errors.append(f"row {row_number}: duplicate accepted publication_id {publication_id}")
            continue
        seen_ids.add(publication_id)
        publication = by_id.get(publication_id)
        if publication is None:
            errors.append(f"row {row_number}: unknown publication_id {publication_id}")
            continue
        if publication.publication_type is not PublicationType.CONFERENCE_PAPER:
            errors.append(f"row {row_number}: {publication_id} is not a COMM record")
            continue

        source_url = str(row.get("source_url") or "").strip()
        source_name = str(row.get("source_name") or "").strip()
        confidence_raw = str(row.get("confidence") or "").strip().casefold()
        note = str(row.get("review_note") or "").strip() or None
        if not source_url or not source_name:
            errors.append(f"row {row_number}: accepted review requires source_url and source_name")
            continue
        try:
            confidence = EnrichmentConfidence(confidence_raw)
        except ValueError:
            errors.append(f"row {row_number}: confidence must be high, medium, or low")
            continue

        proposed: dict[str, str] = {}
        row_errors: list[str] = []
        for field in REVIEW_FIELDS:
            value = str(row.get(field) or "").strip()
            if not value:
                continue
            if field in {"conference_start_date", "conference_end_date"} and not ISO_DATE_RE.fullmatch(value):
                row_errors.append(f"{field} must use YYYY-MM-DD")
            else:
                proposed[field] = value
        if row_errors:
            errors.append(f"row {row_number}: {'; '.join(row_errors)}")
            continue
        if not proposed:
            errors.append(f"row {row_number}: accepted review contains no conference metadata")
            continue

        for field, value in proposed.items():
            if getattr(publication, field) == value:
                continue
            setattr(publication, field, value)
            publication.metadata_evidence.append(
                MetadataEvidence(
                    field=field,
                    value=value,
                    source_url=source_url,
                    source_name=source_name,
                    confidence=confidence,
                    note=note,
                )
            )

    return publications, errors


def export_imported_publications(publications: list[Publication], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in publications],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return output
