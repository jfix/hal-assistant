from __future__ import annotations

import json
from collections.abc import Callable
from difflib import SequenceMatcher
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .hal import normalize
from .models import Enrichment, Publication, PublicationType

CROSSREF_URL = "https://api.crossref.org/works"
OPENALEX_URL = "https://api.openalex.org/works"
USER_AGENT = "hal-assistant/0.3 (mailto:hal-assistant@example.invalid)"


def _first(value: object) -> str | None:
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value) if value else None


def _score(publication: Publication, title: str | None, year: int | None) -> float:
    title_score = SequenceMatcher(
        None,
        normalize(publication.title),
        normalize(title or ""),
    ).ratio()
    year_score = 1.0 if publication.year and year == publication.year else 0.0
    return round((title_score * 0.85 + year_score * 0.15) * 100, 1)


def _container_title(publication: Publication) -> str | None:
    return publication.book_title or publication.journal_title


def _crossref_year(item: dict[str, object]) -> int | None:
    issued = item.get("issued")
    if not isinstance(issued, dict):
        return None
    date_parts = issued.get("date-parts")
    if not isinstance(date_parts, list) or not date_parts:
        return None
    first_part = date_parts[0]
    if not isinstance(first_part, list) or not first_part:
        return None
    try:
        return int(first_part[0])
    except (TypeError, ValueError):
        return None


def _crossref_score(publication: Publication, item: dict[str, object]) -> float:
    """Score a candidate using the contribution and its host publication.

    Title-only matching is unsafe for humanities contributions with generic
    titles such as ``Introduction`` and ``Préface``. Container, pagination,
    year, and author provide independent corroborating evidence.
    """
    title_score = SequenceMatcher(
        None,
        normalize(publication.title),
        normalize(_first(item.get("title")) or ""),
    ).ratio()

    expected_container = _container_title(publication)
    candidate_container = _first(item.get("container-title"))
    container_score = (
        SequenceMatcher(
            None,
            normalize(expected_container),
            normalize(candidate_container or ""),
        ).ratio()
        if expected_container
        else 0.0
    )
    year_score = 1.0 if publication.year == _crossref_year(item) else 0.0
    pages_score = (
        1.0
        if publication.pages
        and normalize(str(item.get("page") or "")) == normalize(publication.pages)
        else 0.0
    )

    raw_authors = item.get("author")
    authors = raw_authors if isinstance(raw_authors, list) else []
    author_names = " ".join(
        f"{author.get('given', '')} {author.get('family', '')}"
        for author in authors
        if isinstance(author, dict)
    )
    wanted_authors = {normalize(author) for author in publication.authors}
    author_score = (
        1.0
        if wanted_authors
        and any(wanted in normalize(author_names) for wanted in wanted_authors)
        else 0.0
    )

    if expected_container:
        score = (
            title_score * 0.50
            + container_score * 0.25
            + year_score * 0.10
            + pages_score * 0.10
            + author_score * 0.05
        )
    else:
        score = title_score * 0.75 + year_score * 0.15 + author_score * 0.10
    return round(score * 100, 1)


def _suggested_type(item: dict[str, object]) -> PublicationType | None:
    work_type = str(item.get("type") or "")
    if work_type in {"book-chapter", "reference-entry"}:
        return PublicationType.BOOK_CHAPTER
    if work_type == "journal-article":
        return PublicationType.JOURNAL_ARTICLE
    if work_type == "proceedings-article":
        return PublicationType.CONFERENCE_PAPER
    return None


def _get_json(url: str, opener: Callable[..., object], timeout: float) -> dict[str, object]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with opener(request, timeout=timeout) as response:  # type: ignore[attr-defined]
        return json.load(response)


def enrich_crossref(
    publication: Publication,
    opener: Callable[..., object] = urlopen,
    timeout: float = 20.0,
) -> Enrichment:
    bibliographic = publication.title
    if container := _container_title(publication):
        bibliographic = f"{bibliographic} {container}"
    query_author = next(
        (author for author in publication.authors if normalize(author) == "florence fix"),
        publication.authors[0] if publication.authors else "Florence Fix",
    )
    params = {
        "query.bibliographic": bibliographic,
        "query.author": query_author,
        "rows": 10,
    }
    payload = _get_json(f"{CROSSREF_URL}?{urlencode(params)}", opener, timeout)
    message = payload.get("message")
    items = message.get("items", []) if isinstance(message, dict) else []
    best: Enrichment | None = None
    for item in items:
        if not isinstance(item, dict):
            continue
        title = _first(item.get("title"))
        score = _crossref_score(publication, item)
        suggested_type = _suggested_type(item)
        type_review_reason = None
        if suggested_type and suggested_type != publication.publication_type:
            type_review_reason = (
                f"Crossref classifies the matched work as {item.get('type')}; "
                f"review {publication.publication_type.value} versus "
                f"{suggested_type.value} against the publisher record."
            )
        source_url = str(item.get("URL")) if item.get("URL") else None
        candidate = Enrichment(
            source="crossref",
            score=score,
            canonical_title=title,
            container_title=_first(item.get("container-title")),
            pages=str(item.get("page")) if item.get("page") else None,
            work_type=str(item.get("type")) if item.get("type") else None,
            suggested_publication_type=suggested_type,
            type_review_reason=type_review_reason,
            doi=str(item.get("DOI")) if item.get("DOI") else None,
            journal=_first(item.get("container-title")),
            volume=str(item.get("volume")) if item.get("volume") else None,
            issue=str(item.get("issue")) if item.get("issue") else None,
            issue_title=_first(item.get("issue-title")),
            publisher=str(item.get("publisher")) if item.get("publisher") else None,
            issn=[str(value) for value in item.get("ISSN", [])],
            isbn=[str(value) for value in item.get("ISBN", [])],
            metadata_sources=[source_url] if source_url else [],
            url=source_url,
        )
        if best is None or candidate.score > best.score:
            best = candidate
    return best or Enrichment(source="crossref")


def enrich_openalex(
    publication: Publication,
    opener: Callable[..., object] = urlopen,
    timeout: float = 20.0,
) -> Enrichment:
    params = {"search": publication.title, "per-page": 5}
    payload = _get_json(f"{OPENALEX_URL}?{urlencode(params)}", opener, timeout)
    best: Enrichment | None = None
    for item in payload.get("results", []):
        title = item.get("title")
        year = item.get("publication_year")
        score = _score(publication, title, int(year) if year else None)
        source = (item.get("primary_location") or {}).get("source") or {}
        ids = item.get("ids") or {}
        source_url = str(item.get("id")) if item.get("id") else None
        candidate = Enrichment(
            source="openalex",
            score=score,
            canonical_title=title,
            doi=ids.get("doi", "").removeprefix("https://doi.org/") or None,
            journal=source.get("display_name"),
            issn=[str(value) for value in (source.get("issn") or [])],
            metadata_sources=[source_url] if source_url else [],
            url=source_url,
        )
        if best is None or candidate.score > best.score:
            best = candidate
    return best or Enrichment(source="openalex")


def enrich_publication(
    publication: Publication,
    opener: Callable[..., object] = urlopen,
) -> Enrichment:
    try:
        crossref = enrich_crossref(publication, opener=opener)
        if crossref.score >= 80:
            return crossref
        openalex = enrich_openalex(publication, opener=opener)
        return openalex if openalex.score > crossref.score else crossref
    except Exception as exc:
        return Enrichment(source="error", error=str(exc))


def enrich_publications(publications: list[Publication]) -> list[Publication]:
    for publication in publications:
        if publication.hal_match is None or publication.hal_match.status.value != "found":
            publication.enrichment = enrich_publication(publication)
    return publications
