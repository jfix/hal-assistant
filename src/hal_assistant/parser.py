from __future__ import annotations

import re
from collections import Counter
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
FRENCH_CONFERENCE_CITIES = {
    "Granada": "Grenade",
    "Santa Maria, Azores": "Santa Maria, Açores",
    "Vienna": "Vienne",
}
FRENCH_COUNTRIES = {"Austria": "Autriche", "Spain": "Espagne"}
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
PUBLISHER_CITY_DEFAULTS = {
    "EUD": "Dijon",
    "L’Harmattan": "Paris",
    "L'Harmattan": "Paris",
}
PUBLISHER_CANONICAL_NAMES = {
    "PUR": "Presses universitaires de Rennes",
    "UAM ediciones": "UAM Ediciones",
    "Frank und Timme": "Frank & Timme",
}
GENERIC_CONTRIBUTION_TITLES = {"avant-propos", "introduction", "préface"}
JOURNAL_ISSUE_RE = re.compile(
    r"^(?P<journal>.+?)\s+(?P<issue>\d+)\s*,\s*"
    r"(?P<theme>.+?)(?:\s+\((?P<part>\d+)\))?\s*,\s*"
    r"(?P<year>(?:19|20)\d{2})\b",
    re.IGNORECASE,
)
PAON_D_HERA_RE = re.compile(r"^Le Paon d[’']Héra$", re.IGNORECASE)


def normalize_text(value: str) -> str:
    return SPACE_RE.sub(" ", value.replace("\u00a0", " ")).strip()


def normalize_centuries(value: str) -> str:
    """Uppercase Roman numerals in explicit French century expressions."""
    normalized = normalize_text(value)
    normalized = normalized.replace("Nineteenh-Century", "Nineteenth-Century")
    return CENTURY_RE.sub(lambda match: f"{match.group(1).upper()}e", normalized)


def _french_quoted_title_end(value: str) -> int | None:
    """Return the closing guillemet paired with a leading opening guillemet."""
    if not value.startswith("«"):
        return None
    depth = 0
    for index, character in enumerate(value):
        if character == "«":
            depth += 1
        elif character == "»":
            depth -= 1
            if depth == 0:
                return index
    return None


def extract_title(citation: str, formatted_title: str | None = None) -> str:
    citation = citation.strip()
    title: str | None = None
    if citation.startswith("«"):
        closing_index = _french_quoted_title_end(citation)
        if closing_index is not None:
            title = citation[1:closing_index].strip()
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
    closing_index = _french_quoted_title_end(citation)
    if closing_index is None:
        return citation
    return citation[closing_index + 1 :].lstrip(" ,")


def _citation_without_urls(citation: str) -> str:
    """Remove URLs before bibliographic year extraction.

    URL path components often contain plausible four-digit years that are not
    publication metadata.
    """
    return URL_RE.sub(" ", citation)


def _container_preposition(container: str) -> tuple[str, str]:
    normalized = normalize_centuries(container).strip(" ,.")
    if re.match(r"^Le\s+", normalized, flags=re.IGNORECASE):
        remainder = re.sub(
            r"^Le\s+", "", normalized, count=1, flags=re.IGNORECASE
        )
        return "au", remainder[:1].upper() + remainder[1:]
    if re.match(r"^Les\s+", normalized, flags=re.IGNORECASE):
        remainder = re.sub(
            r"^Les\s+", "", normalized, count=1, flags=re.IGNORECASE
        )
        return "aux", remainder[:1].upper() + remainder[1:]
    return "à", normalized


def disambiguate_generic_title(title: str, container: str | None) -> str:
    """Qualify generic front-matter titles with their host publication."""
    if title.casefold() not in GENERIC_CONTRIBUTION_TITLES or not container:
        return title
    preposition, qualified_container = _container_preposition(container)
    return f"{title} {preposition} {qualified_container}"


def _clean_container_title(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.split(
        r",\s*(?:ouvrage collectif|actes des?\b|numéro de\b|revue\b)",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return normalize_centuries(cleaned.strip(" ,.")) or None


def extract_generic_container(
    citation: str,
    publication_type: PublicationType,
    fallback: str | None,
) -> str | None:
    """Extract a concise host title for otherwise generic contributions."""
    tail = _after_quoted_title(citation)
    tail = re.sub(
        r"^(?:avec|en collaboration avec)\s+[^,]+,\s*",
        "",
        tail,
        count=1,
        flags=re.IGNORECASE,
    )
    tail = ARTICLE_PREFIX_RE.sub("", tail, count=1).strip()
    tail = _strip_editor_prefix(tail)

    if publication_type is PublicationType.JOURNAL_ARTICLE:
        numbered_issue = re.split(
            r",\s*numéro de\b", tail, maxsplit=1, flags=re.IGNORECASE
        )[0].strip()
        if numbered_issue != tail:
            return normalize_centuries(numbered_issue)
        issue_match = re.search(
            r"(?:,\s*|\s+)n[°o]\s*\d+\s*,?\s*", tail, re.IGNORECASE
        )
        if issue_match:
            dossier = tail[issue_match.end() :].split(",", 1)[0].strip()
            if dossier and not re.fullmatch(
                r"(?:(?:19|20)\d{2}(?:/\d+)?|p\.?\s*\d+(?:-\d+)?)",
                dossier,
                flags=re.IGNORECASE,
            ):
                return normalize_centuries(dossier)
        return _clean_container_title(tail) or _clean_container_title(fallback)

    cleaned_fallback = _before_publication_city(fallback) if fallback else None
    return _clean_container_title(cleaned_fallback) or _clean_container_title(
        _before_publication_city(CONFERENCE_NOTE_RE.split(tail, maxsplit=1)[0])
    )


def extract_publisher_metadata(citation: str) -> tuple[str | None, str | None]:
    """Extract a publication city and publisher from `..., City, Publisher, ...`."""
    without_notes = CONFERENCE_NOTE_RE.sub("", citation)
    later_version = re.search(
        r"Publication\s+sous\s+le\s+titre\s+(?P<citation>.+)$",
        without_notes,
        re.IGNORECASE,
    )
    if later_version:
        without_notes = later_version.group("citation")

    # A single contribution can cite a jointly published volume. Preserve both
    # publisher/place pairs instead of silently dropping the second one.
    if re.search(r"Ponta Delgada\s*,\s*Letras Levadas", without_notes, re.I) and re.search(
        r"Fresno\s*,\s*Bruma Publications", without_notes, re.I
    ):
        return (
            "Letras Levadas Edições; Bruma Publications",
            "Ponta Delgada; Fresno",
        )

    albolote = re.search(
        r",\s*Albolote\s*\(Granada\)\s*,\s*(?P<publisher>[^,\[]+)",
        without_notes,
        re.IGNORECASE,
    )
    if albolote:
        return albolote.group("publisher").strip(), "Albolote (Granada)"

    candidates: list[tuple[int, str, str]] = []
    for city in PUBLICATION_CITY_MARKERS:
        match = re.search(
            rf",\s*{re.escape(city)}\s*,\s*(?P<publisher>[^,\[]+)",
            without_notes,
            flags=re.IGNORECASE,
        )
        if match:
            candidates.append((match.start(), city, match.group("publisher").strip()))
    if not candidates:
        for publisher, city in PUBLISHER_CITY_DEFAULTS.items():
            if re.search(rf"\b{re.escape(publisher)}\b", without_notes, re.I):
                return publisher.replace("'", "’"), city
        if "Presses universitaires de Rouen et du Havre" in without_notes:
            return "Presses universitaires de Rouen et du Havre", None
        return None, None
    _, city, publisher = min(candidates)
    if publisher.casefold().startswith("temps"):
        return None, "Villeneuve-d’Ascq" if city == "Villeneuve-d’Asq" else city
    publisher = PUBLISHER_CANONICAL_NAMES.get(publisher, publisher)
    return publisher or None, city


def _strip_editor_prefix(value: str) -> str:
    return EDITOR_PREFIX_RE.sub("", value, count=1).strip()


def extract_editors(citation: str) -> list[str]:
    """Extract explicitly labelled volume editors without guessing roles."""
    tail = _after_quoted_title(citation)
    match = re.search(
        r"\b(?:in|dans)\s+(?P<names>[^()]+?)\s*\((?:éd\.|dir\.)\)\s*,",
        tail,
        re.IGNORECASE,
    )
    if not match:
        match = re.match(
            r"(?:avant-propos\s+à\s+)?(?P<names>[^()]+?)\s*"
            r"\((?:éd\.|dir\.)\)\s*,",
            tail,
            re.IGNORECASE,
        )
    if not match:
        return []
    names = re.sub(r"^(?:in|dans)\s+", "", match.group("names"), flags=re.I)
    return [
        re.sub(
            r"Natalia Arregui Barragá$",
            "Natalia Arregui Barragán",
            normalize_text(name),
        )
        for name in re.split(r"\s*(?:,|\bet\b)\s*", names)
        if normalize_text(name)
    ]


def _before_publication_city(value: str) -> str:
    candidates: list[tuple[int, str]] = []
    for city in PUBLICATION_CITY_MARKERS:
        marker = f", {city},"
        index = value.find(marker)
        if index >= 0:
            candidates.append((index, city))
    if candidates:
        return value[: min(candidates)[0]].strip(" ,")
    paris_turin = re.search(r",\s*Paris\s+et\s+Turin\s*,", value, re.I)
    if paris_turin:
        return value[: paris_turin.start()].strip(" ,")
    albolote = re.search(r",\s*Albolote\s*\(Granada\)\s*,", value, re.I)
    if albolote:
        return value[: albolote.start()].strip(" ,")
    return value.strip(" ,")


def extract_book_title(citation: str) -> str | None:
    tail = _after_quoted_title(citation)
    later_version = re.search(
        r"Publication\s+sous\s+le\s+titre\s+(?P<title>.+)$", tail, re.I
    )
    if later_version:
        return normalize_centuries(
            _before_publication_city(later_version.group("title"))
        ) or None
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
            city = FRENCH_CONFERENCE_CITIES.get(city, city)
            country = city_match.group("country")
            if country:
                country = normalize_text(country).strip(" .")
                country = FRENCH_COUNTRIES.get(country, country)
                if YEAR_RE.fullmatch(country):
                    country = None
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
    years = [
        int(match.group(1))
        for match in YEAR_RE.finditer(_citation_without_urls(citation))
    ]
    page_matches = list(PAGES_RE.finditer(citation))
    page_match = page_matches[-1] if page_matches else None
    url_match = URL_RE.search(citation)
    metadata: dict[str, object] = {}

    chapter_types = {
        PublicationType.BOOK_CHAPTER,
        PublicationType.DICTIONARY_ENTRY,
    }
    if publication_type in chapter_types:
        metadata["book_title"] = extract_book_title(citation)
        if default_author and isinstance(metadata["book_title"], str):
            metadata["book_title"] = re.sub(
                rf"^{re.escape(default_author)}\s*,\s*",
                "",
                metadata["book_title"],
                count=1,
                flags=re.IGNORECASE,
            )
        if isinstance(metadata["book_title"], str):
            metadata["book_title"] = _clean_container_title(metadata["book_title"])
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
        book_title = _clean_container_title(extract_book_title(citation))
        metadata["book_title"] = book_title
        if book_title:
            metadata["conference_title"] = book_title

    editors = extract_editors(citation)
    if editors:
        metadata["editors"] = editors

    publisher, publisher_city = extract_publisher_metadata(citation)
    if publisher:
        metadata["publisher"] = publisher
    if publisher_city:
        metadata["publisher_city"] = publisher_city

    title = extract_title(citation, formatted_title=formatted_title)
    container: str | None = None
    if publication_type in chapter_types:
        container = metadata.get("book_title")
    elif publication_type is PublicationType.JOURNAL_ARTICLE:
        container = metadata.get("journal_title")
    elif publication_type is PublicationType.CONFERENCE_PAPER:
        conference_container = metadata.get("conference_title")
        if isinstance(conference_container, str):
            container = conference_container
    if title.casefold() in GENERIC_CONTRIBUTION_TITLES:
        container = extract_generic_container(
            citation,
            publication_type,
            container if isinstance(container, str) else None,
        )
        title = disambiguate_generic_title(title, container)

    return Publication(
        publication_type=publication_type,
        section=section,
        raw_citation=citation,
        title=title,
        year=years[-1] if years else None,
        pages=(next(group for group in page_match.groups() if group).replace(" ", ""))
        if page_match
        else None,
        url=url_match.group(0).rstrip(".)") if url_match else None,
        authors=[default_author] if default_author else [],
        source_paragraph=paragraph_number,
        **metadata,
    )


def normalize_journal_issue_titles(publications: list[Publication]) -> None:
    """Build issue titles and keep part numbers only for repeated themes."""
    parsed: list[tuple[Publication, re.Match[str]]] = []
    for publication in publications:
        if publication.publication_type is not PublicationType.JOURNAL_ISSUE:
            continue
        match = JOURNAL_ISSUE_RE.match(publication.raw_citation)
        if match:
            parsed.append((publication, match))

    theme_counts = Counter(
        normalize_text(match.group("theme")).casefold() for _, match in parsed
    )
    for publication, match in parsed:
        journal = normalize_text(match.group("journal"))
        issue = match.group("issue")
        theme = normalize_text(match.group("theme"))
        part = match.group("part")
        repeated = theme_counts[theme.casefold()] > 1
        suffix = f" ({part})" if part and repeated else ""
        publication.title = f"{journal} {issue}, {theme}{suffix}"
        publication.issue = issue
        if PAON_D_HERA_RE.fullmatch(journal):
            if int(issue) <= 10:
                publication.publisher = "Éditions du Murmure"
                publication.publisher_city = "Neuilly-lès-Dijon"
            else:
                publication.publisher = "Presses universitaires de Franche-Comté"
                publication.publisher_city = "Besançon"


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

    normalize_journal_issue_titles(publications)
    return publications
