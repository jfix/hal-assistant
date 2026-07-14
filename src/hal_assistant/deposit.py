from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from pydantic import BaseModel, Field

from .models import HALMatchStatus, Publication, PublicationType


class DepositStatus(StrEnum):
    READY = "ready"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"
    SKIPPED_EXISTING = "skipped_existing"


class DepositPlan(BaseModel):
    index: int
    status: DepositStatus
    title: str
    document_type: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


HAL_DOCUMENT_TYPES = {
    PublicationType.BOOK: "OUV",
    PublicationType.EDITED_BOOK: "OUV",
    PublicationType.JOURNAL_ISSUE: "OUV",
    PublicationType.BOOK_CHAPTER: "COUV",
    PublicationType.DICTIONARY_ENTRY: "COUV",
    PublicationType.CONFERENCE_PAPER: "COMM",
    PublicationType.JOURNAL_ARTICLE: "ART",
}


def _canonical_title(publication: Publication) -> str:
    enrichment = publication.enrichment
    if enrichment and enrichment.score >= 80 and enrichment.canonical_title:
        return enrichment.canonical_title
    return publication.title


def _identifier(publication: Publication, name: str) -> object | None:
    enrichment = publication.enrichment
    return getattr(enrichment, name, None) if enrichment else None


def build_deposit_plan(publication: Publication, index: int) -> DepositPlan:
    existing = publication.hal_match
    if existing and existing.status is HALMatchStatus.FOUND:
        return DepositPlan(
            index=index,
            status=DepositStatus.SKIPPED_EXISTING,
            title=publication.title,
            document_type=existing.document_type,
            warnings=[f"Already present in HAL as {existing.hal_id}"],
        )

    document_type = HAL_DOCUMENT_TYPES.get(publication.publication_type)
    errors: list[str] = []
    warnings: list[str] = []
    if not document_type:
        errors.append("Unsupported or unknown publication type")
    if not publication.title.strip():
        errors.append("Missing title")
    if not publication.year:
        errors.append("Missing publication year")
    if not publication.authors:
        errors.append("Missing author")

    enrichment = publication.enrichment
    if enrichment is None:
        warnings.append("No external metadata enrichment available")
    elif enrichment.score < 80:
        warnings.append(f"Low-confidence enrichment score: {enrichment.score}")
    if (
        publication.publication_type is PublicationType.JOURNAL_ARTICLE
        and enrichment
        and enrichment.validation_notes
        and enrichment.journal_status != "VALID"
    ):
        warnings.extend(enrichment.validation_notes)

    payload: dict[str, object] = {
        "title": _canonical_title(publication),
        "docType": document_type,
        "producedDateY": publication.year,
        "language": publication.language,
        "authors": publication.authors,
        "pages": publication.pages,
        "doi": _identifier(publication, "doi"),
        "journal": _identifier(publication, "journal"),
        "journalId": _identifier(publication, "journal_id"),
        "journalStatus": _identifier(publication, "journal_status"),
        "volume": _identifier(publication, "volume") or publication.volume,
        "issue": _identifier(publication, "issue") or publication.issue,
        "issueTitle": _identifier(publication, "issue_title"),
        "publisher": _identifier(publication, "publisher"),
        "issn": _identifier(publication, "issn") or publication.issn,
        "eissn": _identifier(publication, "eissn") or [],
        "isbn": _identifier(publication, "isbn") or [],
        "sourceUrl": publication.url,
        "rawCitation": publication.raw_citation,
    }
    payload = {
        key: value
        for key, value in payload.items()
        if value not in (None, "", [])
    }

    if errors:
        status = DepositStatus.BLOCKED
    elif warnings:
        status = DepositStatus.NEEDS_REVIEW
    else:
        status = DepositStatus.READY
    return DepositPlan(
        index=index,
        status=status,
        title=publication.title,
        document_type=document_type,
        payload=payload,
        warnings=warnings,
        errors=errors,
    )


def build_deposit_plans(publications: list[Publication]) -> list[DepositPlan]:
    return [
        build_deposit_plan(publication, index)
        for index, publication in enumerate(publications, 1)
    ]


def export_deposit_plans(
    plans: list[DepositPlan],
    output_dir: str | Path,
) -> tuple[Path, Path]:
    output = Path(output_dir)
    packages = output / "packages"
    packages.mkdir(parents=True, exist_ok=True)

    json_path = output / "deposit-plan.json"
    json_path.write_text(
        json.dumps(
            [plan.model_dump(mode="json") for plan in plans],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    for plan in plans:
        if plan.status not in {DepositStatus.READY, DepositStatus.NEEDS_REVIEW}:
            continue
        package_path = packages / f"{plan.index:03d}.json"
        package_path.write_text(
            json.dumps(plan.payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Deposit plan"
    sheet.append(
        [
            "index",
            "status",
            "title",
            "HAL document type",
            "warnings",
            "errors",
            "payload",
        ]
    )
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.freeze_panes = "A2"
    for plan in plans:
        sheet.append(
            [
                plan.index,
                plan.status.value,
                plan.title,
                plan.document_type,
                "; ".join(plan.warnings),
                "; ".join(plan.errors),
                json.dumps(plan.payload, ensure_ascii=False),
            ]
        )
    sheet.auto_filter.ref = f"A1:G{max(1, len(plans) + 1)}"
    for column, width in {
        "A": 10,
        "B": 20,
        "C": 60,
        "D": 20,
        "E": 60,
        "F": 60,
        "G": 100,
    }.items():
        sheet.column_dimensions[column].width = width
    excel_path = output / "deposit-plan.xlsx"
    workbook.save(excel_path)
    return json_path, excel_path
