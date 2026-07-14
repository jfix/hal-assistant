from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any


COMMON_REQUIRED_FIELDS = ("title", "authors", "year", "language")

HAL_TYPE_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "ART": COMMON_REQUIRED_FIELDS + ("journal_title",),
    "COUV": COMMON_REQUIRED_FIELDS + ("book_title",),
    "COMM": COMMON_REQUIRED_FIELDS
    + (
        "conference_title",
        "conference_start_date",
        "conference_end_date",
        "conference_city",
        "conference_country",
    ),
    "OUV": COMMON_REQUIRED_FIELDS,
    "DOUV": COMMON_REQUIRED_FIELDS,
}

PUBLICATION_TYPE_TO_HAL = {
    "journal_article": "ART",
    "book_chapter": "COUV",
    "dictionary_entry": "COUV",
    "conference_paper": "COMM",
    "book": "OUV",
    "edited_book": "OUV",
    "journal_issue": "OUV",
}

ALIASES: dict[str, tuple[str, ...]] = {
    "journal_title": (
        "journal_title",
        "journal",
        "container_title",
        "journalOrBookTitle",
    ),
    "book_title": ("book_title", "container_title", "journalOrBookTitle"),
    "conference_title": ("conference_title", "conferenceTitle"),
    "conference_start_date": (
        "conference_start_date",
        "conferenceStartDate",
    ),
    "conference_end_date": (
        "conference_end_date",
        "conferenceEndDate",
    ),
    "conference_city": ("conference_city", "city"),
    "conference_country": ("conference_country", "country"),
    "year": ("year", "producedDateY"),
}


@dataclass(frozen=True)
class ReadinessResult:
    publication_id: str
    document_type: str
    ready: bool
    missing_required_fields: list[str]


def _first(record: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = record.get(name)
        if value not in (None, "", []):
            return value
    return None


def resolve_hal_type(record: dict[str, Any]) -> str:
    explicit = _first(record, "document_type", "docType")
    if explicit:
        return str(explicit)
    publication_type = str(record.get("publication_type") or "")
    return PUBLICATION_TYPE_TO_HAL.get(
        publication_type,
        publication_type.upper() or "UNKNOWN",
    )


def field_value(record: dict[str, Any], field: str) -> Any:
    return _first(record, *ALIASES.get(field, (field,)))


def audit_record(record: dict[str, Any]) -> ReadinessResult:
    document_type = resolve_hal_type(record)
    requirements = HAL_TYPE_REQUIREMENTS.get(document_type, COMMON_REQUIRED_FIELDS)
    missing = [
        field
        for field in requirements
        if field_value(record, field) in (None, "", [])
    ]
    return ReadinessResult(
        publication_id=str(record.get("publication_id") or "unknown"),
        document_type=document_type,
        ready=not missing,
        missing_required_fields=missing,
    )


def audit_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    results = [audit_record(record) for record in records]
    types: dict[str, dict[str, Any]] = {}
    for document_type in sorted({result.document_type for result in results}):
        selected = [
            result for result in results if result.document_type == document_type
        ]
        missing_counts = Counter(
            field for result in selected for field in result.missing_required_fields
        )
        types[document_type] = {
            "total": len(selected),
            "ready": sum(result.ready for result in selected),
            "blocked": sum(not result.ready for result in selected),
            "missing_fields": dict(sorted(missing_counts.items())),
        }

    return {
        "format": "hal-assistant-readiness-audit-v1",
        "total": len(results),
        "ready": sum(result.ready for result in results),
        "blocked": sum(not result.ready for result in results),
        "types": types,
        "records": [
            {
                "publication_id": result.publication_id,
                "document_type": result.document_type,
                "ready": result.ready,
                "missing_required_fields": result.missing_required_fields,
            }
            for result in results
        ],
    }
