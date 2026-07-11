from __future__ import annotations

import re
from pathlib import Path

from docx import Document

from .models import Publication, PublicationType

SECTION_TYPES: dict[str, PublicationType] = {
    "Ouvrages": PublicationType.BOOK,
    "Ouvrages en co-direction (mais HAL ne fait pas la différence avec Ouvrages)": PublicationType.EDITED_BOOK,
    "N°spécial de revue": PublicationType.JOURNAL_ISSUE,
    "Chapitre d’ouvrage": PublicationType.BOOK_CHAPTER,
    "Notice d’encyclopédie ou de dictionnaire": PublicationType.DICTIONARY_ENTRY,
    "Communication dans un congrès": PublicationType.CONFERENCE_PAPER,
    "Article dans revue": PublicationType.JOURNAL_ARTICLE,
}

YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
PAGES_RE = re.compile(
    r"(?:\bp\.?\s*(\d+(?:\s*[-–—]\s*\d+)?)\b|\b(\d+)\s*p\.)",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://[^\s,;]+|www\.[^\s,;]+", re.IGNORECASE)
SPACE_RE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    return SPACE_RE.sub(" ", value.replace("\u00a0", " ")).strip()


def extract_title(citation: str) -> str:
    citation = citation.strip()
    if citation.startswith(("«", '"')):
        closing = "»" if citation.startswith("«") else '"'
        end = citation.find(closing, 1)
        if end > 1:
            return citation[1:end].strip()
    return citation.split(",", 1)[0].strip().rstrip(".")


def parse_citation(
    citation: str,
    section: str,
    publication_type: PublicationType,
    paragraph_number: int,
    default_author: str | None,
) -> Publication:
    years = [int(match.group(1)) for match in YEAR_RE.finditer(citation)]
    page_match = PAGES_RE.search(citation)
    url_match = URL_RE.search(citation)
    return Publication(
        publication_type=publication_type,
        section=section,
        raw_citation=citation,
        title=extract_title(citation),
        year=years[-1] if years else None,
        pages=(next(group for group in page_match.groups() if group).replace(" ", ""))
        if page_match
        else None,
        url=url_match.group(0).rstrip(".)") if url_match else None,
        authors=[default_author] if default_author else [],
        source_paragraph=paragraph_number,
    )


def parse_docx(path: str | Path, default_author: str | None = None) -> list[Publication]:
    document = Document(str(path))
    current_section = "Unclassified"
    current_type = PublicationType.UNKNOWN
    publications: list[Publication] = []

    for number, paragraph in enumerate(document.paragraphs, start=1):
        text = normalize_text(paragraph.text)
        if not text:
            continue
        if text in SECTION_TYPES:
            current_section = text
            current_type = SECTION_TYPES[text]
            continue
        publications.append(
            parse_citation(text, current_section, current_type, number, default_author)
        )

    return publications
