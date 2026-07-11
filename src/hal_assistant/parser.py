from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.text.paragraph import Paragraph

from .models import Publication, PublicationType

SECTION_TYPES: dict[str, PublicationType] = {
    "Ouvrages": PublicationType.BOOK,
    (
        "Ouvrages en co-direction (mais HAL ne fait pas la différence avec Ouvrages)"
    ): PublicationType.EDITED_BOOK,
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
URL_ONLY_RE = re.compile(r"^(?:https?://|www\.)\S+\.?$", re.IGNORECASE)


def normalize_text(value: str) -> str:
    return SPACE_RE.sub(" ", value.replace("\u00a0", " ")).strip()


def extract_title(citation: str, formatted_title: str | None = None) -> str:
    citation = citation.strip()
    if citation.startswith(("«", '"')):
        closing = "»" if citation.startswith("«") else '"'
        end = citation.find(closing, 1)
        if end > 1:
            return citation[1:end].strip()
    if formatted_title:
        return normalize_text(formatted_title).strip().rstrip(",.")
    return citation.split(",", 1)[0].strip().rstrip(".")


def leading_italic_title(paragraph: Paragraph) -> str | None:
    """Return a leading contiguous italic span, ignoring initial whitespace."""
    parts: list[str] = []
    started = False
    for run in paragraph.runs:
        text = run.text
        if not text:
            continue
        is_italic = run.italic is True or run.style.font.italic is True
        if not started and not text.strip():
            continue
        if is_italic:
            parts.append(text)
            started = True
        elif started:
            break
        else:
            return None
    title = normalize_text("".join(parts))
    return title or None


def parse_citation(
    citation: str,
    section: str,
    publication_type: PublicationType,
    paragraph_number: int,
    default_author: str | None,
    formatted_title: str | None = None,
) -> Publication:
    years = [int(match.group(1)) for match in YEAR_RE.finditer(citation)]
    page_match = PAGES_RE.search(citation)
    url_match = URL_RE.search(citation)
    return Publication(
        publication_type=publication_type,
        section=section,
        raw_citation=citation,
        title=extract_title(citation, formatted_title=formatted_title),
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
        if URL_ONLY_RE.fullmatch(text) and publications:
            previous = publications[-1]
            previous.raw_citation = f"{previous.raw_citation} {text}"
            previous.url = URL_RE.search(text).group(0).rstrip(".)")
            continue
        publications.append(
            parse_citation(
                text,
                current_section,
                current_type,
                number,
                default_author,
                formatted_title=leading_italic_title(paragraph),
            )
        )

    return publications
