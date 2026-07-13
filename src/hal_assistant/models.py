from __future__ import annotations

import hashlib
import re
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class PublicationType(StrEnum):
    BOOK = "book"
    EDITED_BOOK = "edited_book"
    JOURNAL_ISSUE = "journal_issue"
    BOOK_CHAPTER = "book_chapter"
    DICTIONARY_ENTRY = "dictionary_entry"
    CONFERENCE_PAPER = "conference_paper"
    JOURNAL_ARTICLE = "journal_article"
    UNKNOWN = "unknown"


class HALMatchStatus(StrEnum):
    FOUND = "found"
    REVIEW = "review"
    NOT_FOUND = "not_found"
    ERROR = "error"


class HALReadinessStatus(StrEnum):
    PARSED = "parsed"
    NEEDS_ENRICHMENT = "needs_enrichment"
    NEEDS_REVIEW = "needs_review"
    HAL_READY = "hal_ready"
    PREPROD_VALIDATED = "preprod_validated"
    PRODUCTION_SUBMITTED = "production_submitted"


class EnrichmentConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MetadataEvidence(BaseModel):
    field: str
    value: str
    source_url: str
    source_name: str
    confidence: EnrichmentConfidence
    note: str | None = None


class HALMatch(BaseModel):
    status: HALMatchStatus
    hal_id: str | None = None
    title: str | None = None
    year: int | None = None
    authors: list[str] = Field(default_factory=list)
    document_type: str | None = None
    score: float = 0.0
    url: str | None = None
    error: str | None = None


class Enrichment(BaseModel):
    source: str
    score: float = 0.0
    canonical_title: str | None = None
    doi: str | None = None
    journal: str | None = None
    publisher: str | None = None
    issn: list[str] = Field(default_factory=list)
    isbn: list[str] = Field(default_factory=list)
    url: str | None = None
    error: str | None = None


def stable_publication_id(
    publication_type: PublicationType,
    title: str,
    raw_citation: str,
) -> str:
    """Return a reproducible identifier independent of paragraph order and output paths."""
    normalized = "|".join(
        (
            publication_type.value,
            re.sub(r"\s+", " ", title).strip().casefold(),
            re.sub(r"\s+", " ", raw_citation).strip().casefold(),
        )
    )
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"pub-{digest}"


class Publication(BaseModel):
    publication_id: str | None = None
    publication_type: PublicationType
    section: str
    raw_citation: str
    title: str
    year: int | None = None
    pages: str | None = None
    url: str | None = None
    authors: list[str] = Field(default_factory=list)
    language: str = "fr"
    source_paragraph: int

    # Explicit semantic container metadata. New extraction code should populate
    # these fields instead of overloading a generic container_title value.
    journal_title: str | None = None
    book_title: str | None = None
    publisher: str | None = None
    publisher_city: str | None = None
    editors: list[str] = Field(default_factory=list)
    volume: str | None = None
    issue: str | None = None
    doi: str | None = None
    isbn: list[str] = Field(default_factory=list)
    issn: list[str] = Field(default_factory=list)

    conference_title: str | None = None
    conference_start_date: str | None = None
    conference_end_date: str | None = None
    conference_city: str | None = None
    conference_country: str | None = None
    conference_country_code: str | None = None
    metadata_evidence: list[MetadataEvidence] = Field(default_factory=list)

    hal_readiness: HALReadinessStatus = HALReadinessStatus.PARSED
    missing_required_fields: list[str] = Field(default_factory=list)
    hal_match: HALMatch | None = None
    enrichment: Enrichment | None = None

    @model_validator(mode="after")
    def ensure_publication_id(self) -> Publication:
        if not self.publication_id:
            self.publication_id = stable_publication_id(
                self.publication_type,
                self.title,
                self.raw_citation,
            )
        return self
