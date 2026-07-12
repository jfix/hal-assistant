from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


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


class Publication(BaseModel):
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

    hal_readiness: HALReadinessStatus = HALReadinessStatus.PARSED
    missing_required_fields: list[str] = Field(default_factory=list)
    hal_match: HALMatch | None = None
    enrichment: Enrichment | None = None
