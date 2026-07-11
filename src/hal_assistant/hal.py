from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from difflib import SequenceMatcher
from urllib.parse import urlencode
from urllib.request import urlopen

from .models import HALMatch, HALMatchStatus, Publication

HAL_SEARCH_URL = "https://api.archives-ouvertes.fr/search/hal/"
FIELDS = "halId_s,title_s,producedDateY_i,authFullName_s,docType_s"
SPACE_RE = re.compile(r"\s+")


def normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    cleaned = re.sub(r"[^\w\s]", " ", ascii_text.casefold())
    return SPACE_RE.sub(" ", cleaned).strip()


def solr_phrase(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_search_url(publication: Publication, rows: int = 10) -> str:
    query_parts = [f'title_t:"{solr_phrase(publication.title)}"']
    if publication.year:
        query_parts.append(f"producedDateY_i:{publication.year}")
    params = {"q": " AND ".join(query_parts), "fl": FIELDS, "rows": rows, "wt": "json"}
    return f"{HAL_SEARCH_URL}?{urlencode(params)}"


def build_idhal_url(idhal: str, rows: int = 1000) -> str:
    params = {
        "q": f'authIdHal_s:"{solr_phrase(idhal)}"',
        "fl": FIELDS,
        "rows": rows,
        "wt": "json",
    }
    return f"{HAL_SEARCH_URL}?{urlencode(params)}"


def fetch_idhal_candidates(
    idhal: str,
    opener: Callable[..., object] = urlopen,
    timeout: float = 20.0,
) -> list[dict[str, object]]:
    with opener(build_idhal_url(idhal), timeout=timeout) as response:  # type: ignore[attr-defined]
        payload = json.load(response)
    return list(payload.get("response", {}).get("docs", []))


def score_candidate(publication: Publication, candidate: dict[str, object]) -> float:
    candidate_title = candidate.get("title_s") or ""
    if isinstance(candidate_title, list):
        candidate_title = candidate_title[0] if candidate_title else ""
    title_score = SequenceMatcher(
        None, normalize(publication.title), normalize(str(candidate_title))
    ).ratio()

    year_score = 0.0
    candidate_year = candidate.get("producedDateY_i")
    if publication.year and candidate_year:
        year_score = 1.0 if int(candidate_year) == publication.year else 0.0

    author_score = 0.0
    candidate_authors = candidate.get("authFullName_s") or []
    if isinstance(candidate_authors, str):
        candidate_authors = [candidate_authors]
    if publication.authors and candidate_authors:
        wanted = {normalize(author) for author in publication.authors}
        found = {normalize(str(author)) for author in candidate_authors}
        author_score = 1.0 if wanted & found else 0.0

    return round((title_score * 0.75 + year_score * 0.15 + author_score * 0.10) * 100, 1)


def candidate_to_match(publication: Publication, candidate: dict[str, object]) -> HALMatch:
    score = score_candidate(publication, candidate)
    status = (
        HALMatchStatus.FOUND
        if score >= 90
        else HALMatchStatus.REVIEW
        if score >= 70
        else HALMatchStatus.NOT_FOUND
    )
    title = candidate.get("title_s")
    if isinstance(title, list):
        title = title[0] if title else None
    authors = candidate.get("authFullName_s") or []
    if isinstance(authors, str):
        authors = [authors]
    hal_id = candidate.get("halId_s")
    return HALMatch(
        status=status,
        hal_id=str(hal_id) if hal_id else None,
        title=str(title) if title else None,
        year=int(candidate["producedDateY_i"]) if candidate.get("producedDateY_i") else None,
        authors=[str(author) for author in authors],
        document_type=str(candidate["docType_s"]) if candidate.get("docType_s") else None,
        score=score,
        url=f"https://hal.science/{hal_id}" if hal_id else None,
    )


def best_match(publication: Publication, candidates: list[dict[str, object]]) -> HALMatch:
    if not candidates:
        return HALMatch(status=HALMatchStatus.NOT_FOUND)
    matches = [candidate_to_match(publication, candidate) for candidate in candidates]
    return max(matches, key=lambda match: match.score)


def search_publication(
    publication: Publication,
    opener: Callable[..., object] = urlopen,
    timeout: float = 20.0,
) -> HALMatch:
    try:
        with opener(build_search_url(publication), timeout=timeout) as response:  # type: ignore[attr-defined]
            payload = json.load(response)
        return best_match(publication, payload.get("response", {}).get("docs", []))
    except Exception as exc:
        return HALMatch(status=HALMatchStatus.ERROR, error=str(exc))


def match_publications(
    publications: list[Publication],
    idhal: str | None = None,
    opener: Callable[..., object] = urlopen,
) -> list[Publication]:
    candidates: list[dict[str, object]] | None = None
    if idhal:
        try:
            candidates = fetch_idhal_candidates(idhal, opener=opener)
        except Exception as exc:
            for publication in publications:
                publication.hal_match = HALMatch(status=HALMatchStatus.ERROR, error=str(exc))
            return publications

    for publication in publications:
        publication.hal_match = (
            best_match(publication, candidates)
            if candidates is not None
            else search_publication(publication, opener=opener)
        )
    return publications
