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
FRENCH_TITLE_END_RE = re.compile(r"»(?=\s*(?:,|$))")
CENTURY_RE = re.compile(
    r"\b([ivxlcdm]+)e(?=(?:\s+siècles?\b|\s*[-–—]\s*[ivxlcdm]+e\s+siècles?\b))",
    re.IGNORECASE,
)
EDITOR_PREFIX_RE = re.compile(
    r"^.*?\((?:éd\.|dir\.)\)\s*,\s*",
    re.IGNORECASE,
)
ARTICLE_PREFIX_RE = re.compile(
    r"^(?:in|dans|revue\s+en\s+ligne)\s+",
    re.IGNORECASE,
)
VOLUME_MARKER_RE = re.compile(
    r",\s*(?=(?:vol\.?\s*\d+|n[°o]\s*\w+|\d+/\d{4}|(?:19|20)\d{2}\b))",
    re.IGNORECASE,
)
CONFERENCE_NOTE_RE = re.compile(r"\[(?P<note>[^\]]+)\]")
CONFERENCE_CITY_RE = re.compile(
    r"(?:Université|université|INHA|séminaire|colloque|journée(?:s)? d[’']études?)"
    r"[^,\]]*,\s*(?P<city>[^,\]]+?)(?:,\s*(?P<country>[^,\]]+))?\s*$",
    re.IGNORECASE,
)
COUNTRY_BY_CITY = {
    "Albolote": "Espagne",
    "Bordeaux": "France",
    "Brest": "France",
    "Dijon": "France",
    "Florence": "Italie",
    "Grenade": "Espagne",
    "Le Havre": "France",
    "Lille": "France",
    "Madrid": "Espagne",
    "Mulhouse": "France",
    "Nancy": "France",
    "Paris": "France",
    "Porto": "Portugal",
    "Rouen": "France",
    "Toulouse": "France",
    "Valence": "Espagne",
    "Vienne": "Autriche",
}
PUBLICATION_CITY_MARKERS = (
    "Paris",
    "Dijon",
    "Reims",
    "Rouen",
    "Rennes",
    "Berlin",
    "Berne",
    "Laval",
    "Pessac",
    "Madrid",
    "Katowice",
    "Cassino",
    "Leyde",
    "Tusson",
    "Amsterdam",
    "Villeneuve-d’Asq",
    "Albolote",
    "Ponta Delgada",
)


def normalize_text(value: str) -> str:
    return SPACE_RE.sub(" ", value.replace("\u00a0", " ")).strip()


def normalize_centuries(value: str) -> str:
    """Uppercase Roman numerals in explicit French century expressions."""
    normalized = normalize_text(value)
    return CENTURY_RE.sub(lambda match: f"{match.group(1).upper()}e", normalized)


def extract_title(citation: str, formatted_title: str | None = None) -> str:
    citation = citation.strip()
    title: str | None = None
    if citation.startswith("«"):
        closing_matches = list(FRENCH_TITLE_END_RE.finditer(citation, 1))
        if closing_matches:
            title = citation[1 : closing_matches[-1].start()].strip()
    elif citation.startswith('"'):
        end = citation.find('"', 1)
        if end > 1:
            title = citation[1:end].strip()
    if title is None and formatted_title:
        title = normalize_text(formatted_title).strip().rstrip(",.")
    if title is None:
        title = citation.split(",", 1)[0].strip().rstrip(".")
    return normalize_centuries(title)


def leading_italic_title(paragraph: Paragraph) -> str | None:
    """Return a leading italic span, allowing formatting-only whitespace runs."""
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
        elif started and not text.strip():
            parts.append(text)
        elif started:
            break
        else:
            return None
    title = normalize_text("".join(parts))
    return title or None


def _after_quoted_title(citation: str) -> str:
    matches = list(FRENCH_TITLE_END_RE.finditer(citation, 1))
    if not matches:
        return citation
    return citation[matches[-1].end() :].lstrip(" ,")


def _strip_editor_prefix(value: str) -> str:
    return EDITOR_PREFIX_RE.sub("", value, count=1).strip()


def _before_publication_city(value: str) -> str:
    candidates: list[tuple[int, str]] = []
    for city in PUBLICATION_CITY_MARKERS:
        marker = f", {city},"
        index = value.find(marker)
        if index >= 0:
            candidates.append((index, city))
    if candidates:
        return value[: min(candidates)[0]].strip(" ,")
    return value.strip(" ,")


def extract_book_title(citation: str) -> str | None:
    tail = _after_quoted_title(citation)
    tail = re.sub(
        r"^(?:in|dans|avant-propos\s+(?:in|à))\s+",
        "",
        tail,
        flags=re.IGNORECASE,
    )
    tail = _strip_editor_prefix(tail)
    tail = CONFERENCE_NOTE_RE.split(tail, maxsplit=1)[0].strip(" ,")
    title = _before_publication_city(tail)
    return normalize_centuries(title) or None


def extract_journal_title(citation: str) -> str | None:
    tail = ARTICLE_PREFIX_RE.sub("", _after_quoted_title(citation), count=1).strip()
    tail = _strip_editor_prefix(tail)
    match = VOLUME_MARKER_RE.search(tail)
    if match:
        tail = tail[: match.start()]
    tail = _before_publication_city(tail)
    return normalize_centuries(tail.strip(" ,")) or None


def extract_conference_metadata(citation: str) -> dict[str, str | None]:
    note_match = CONFERENCE_NOTE_RE.search(citation)
    note = normalize_text(note_match.group("note")) if note_match else None

    tail = _after_quoted_title(citation)
    tail = re.sub(
        r"^(?:in|dans|avant-propos\s+à)\s+",
        "",
        tail,
        flags=re.IGNORECASE,
    )
    tail = _strip_editor_prefix(tail)
    conference_title = tail.split("[", 1)[0].strip(" ,") or None

    city = None
    country = None
    if note:
        city_match = CONFERENCE_CITY_RE.search(note)
        if city_match:
            city = normalize_text(city_match.group("city")).strip(" .")
            country = city_match.group("country")
            if country:
                country = normalize_text(country).strip(" .")
        if city and not country:
            country = COUNTRY_BY_CITY.get(city)

    years = [match.group(1) for match in YEAR_RE.finditer(note or "")]
    return {
        "conference_title": (
            normalize_centuries(conference_title) if conference_title else None
        ),
        "conference_start_date": None,
        "conference_city": city,
        "conference_country": country,
        "conference_year_evidence": years[-1] if years else None,
    }


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
    metadata: dict[str, object] = {}

    chapter_types = {
        PublicationType.BOOK_CHAPTER,
        PublicationType.DICTIONARY_ENTRY,
    }
    if publication_type in chapter_types:
        metadata["book_title"] = extract_book_title(citation)
    elif publication_type is PublicationType.JOURNAL_ARTICLE:
        metadata["journal_title"] = extract_journal_title(citation)
    elif publication_type is PublicationType.CONFERENCE_PAPER:
        conference = extract_conference_metadata(citation)
        metadata.update(
            {
                key: value
                for key, value in conference.items()
                if key != "conference_year_evidence"
            }
        )

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
        **metadata,
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
