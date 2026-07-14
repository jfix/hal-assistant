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


def _crossref_score(publication: Publication, item: dict[str, object]) -> float:
    """Score a Crossref candidate using contribution and host metadata.

    A title-only lookup is unsafe for generic humanities contribution titles
    such as ``Introduction`` and ``Avant-propos``.  Host title, pagination,
    year, and author are independent corroborating signals.
    """
    title = _first(item.get("title"))
    issued = item.get("issued", {}).get("date-parts", [[None]])  # type: ignore[union-attr]
    year = issued[0][0] if issued and issued[0] else None
    title_score = SequenceMatcher(
        None, normalize(publication.title), normalize(title or "")
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
    year_score = 1.0 if publication.year and year == publication.year else 0.0
    pages_score = (
        1.0
        if publication.pages
        and normalize(str(item.get("page") or "")) == normalize(publication.pages)
        else 0.0
    )
    author_names = " ".join(
        f"{author.get('given', '')} {author.get('family', '')}"
        for author in item.get("author", [])  # type: ignore[union-attr]
        if isinstance(author, dict)
    )
    author_score = 1.0 if "florence fix" in normalize(author_names) else 0.0

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
    if work_type in {"journal-article", "proceedings-article"}:
        return (
            PublicationType.CONFERENCE_PAPER
            if work_type == "proceedings-article"
            else PublicationType.JOURNAL_ARTICLE
        )
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
    params = {
        "query.bibliographic": bibliographic,
        "query.author": "Florence Fix",
        "rows": 10,
    }
    payload = _get_json(f"{CROSSREF_URL}?{urlencode(params)}", opener, timeout)
    items = payload.get("message", {}).get("items", [])  # type: ignore[union-attr]
    best: Enrichment | None = None
    for item in items:
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
        candidate = Enrichment(
            source="crossref",
            score=score,
            canonical_title=title,
            container_title=_first(item.get("container-title")),
            pages=str(item.get("page")) if item.get("page") else None,
            work_type=str(item.get("type")) if item.get("type") else None,
            suggested_publication_type=suggested_type,
            type_review_reason=type_review_reason,
            doi=item.get("DOI"),
            journal=_first(item.get("container-title")),
            publisher=item.get("publisher"),
            issn=[str(v) for v in item.get("ISSN", [])],
            isbn=[str(v) for v in item.get("ISBN", [])],
            url=item.get("URL"),
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
        candidate = Enrichment(
            source="openalex",
            score=score,
            canonical_title=title,
            doi=ids.get("doi", "").removeprefix("https://doi.org/") or None,
            journal=source.get("display_name"),
            issn=[str(v) for v in source.get("issn", [])],
            url=item.get("id"),
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
