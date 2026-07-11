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
    hal_match: HALMatch | None = None
    enrichment: Enrichment | None = None
