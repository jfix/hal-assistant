from __future__ import annotations

import json
from collections.abc import Callable
from difflib import SequenceMatcher
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .hal import normalize
from .models import Enrichment, Publication

CROSSREF_URL = "https://api.crossref.org/works"
OPENALEX_URL = "https://api.openalex.org/works"
USER_AGENT = "hal-assistant/0.3 (mailto:hal-assistant@example.invalid)"


def _first(value: object) -> str | None:
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value) if value else None


def _score(publication: Publication, title: str | None, year: int | None) -> float:
    title_score = SequenceMatcher(None, normalize(publication.title), normalize(title or "")).ratio()
    year_score = 1.0 if publication.year and year == publication.year else 0.0
    return round((title_score * 0.85 + year_score * 0.15) * 100, 1)


def _get_json(url: str, opener: Callable[..., object], timeout: float) -> dict[str, object]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with opener(request, timeout=timeout) as response:  # type: ignore[attr-defined]
        return json.load(response)


def enrich_crossref(
    publication: Publication,
    opener: Callable[..., object] = urlopen,
    timeout: float = 20.0,
) -> Enrichment:
    params = {"query.bibliographic": publication.title, "rows": 5}
    payload = _get_json(f"{CROSSREF_URL}?{urlencode(params)}", opener, timeout)
    items = payload.get("message", {}).get("items", [])  # type: ignore[union-attr]
    best: Enrichment | None = None
    for item in items:
        title = _first(item.get("title"))
        issued = item.get("issued", {}).get("date-parts", [[None]])
        year = issued[0][0] if issued and issued[0] else None
        score = _score(publication, title, int(year) if year else None)
        candidate = Enrichment(
            source="crossref",
            score=score,
            canonical_title=title,
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
