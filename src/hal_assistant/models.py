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
