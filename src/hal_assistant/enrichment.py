from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable
from difflib import SequenceMatcher
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .hal import normalize
from .models import Enrichment, Publication, PublicationType

CROSSREF_URL = "https://api.crossref.org/works"
OPENALEX_URL = "https://api.openalex.org/works"
HAL_JOURNAL_REF_URL = "https://api.archives-ouvertes.fr/ref/journal/"
HAL_SEARCH_URL = "https://api.archives-ouvertes.fr/search/"
USER_AGENT = "hal-assistant/0.3 (mailto:hal-assistant@example.invalid)"


def _first(value: object) -> str | None:
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value) if value else None


def _values(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)] if value else []


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
            volume=str(item.get("volume")) if item.get("volume") else None,
            issue=str(item.get("issue")) if item.get("issue") else None,
            issue_title=_first(item.get("issue-title")),
            publisher=item.get("publisher"),
            issn=[str(v) for v in item.get("ISSN", [])],
            isbn=[str(v) for v in item.get("ISBN", [])],
            url=item.get("URL"),
            metadata_sources=[str(item.get("URL"))] if item.get("URL") else [],
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
            issn=[str(v) for v in (source.get("issn") or [])],
            url=item.get("id"),
            metadata_sources=[str(item.get("id"))] if item.get("id") else [],
        )
        if best is None or candidate.score > best.score:
            best = candidate
    return best or Enrichment(source="openalex")


def _journal_authority_score(
    publication: Publication,
    enrichment: Enrichment,
    candidate: dict[str, object],
) -> tuple[float, bool]:
    expected_titles = [publication.journal_title] if publication.journal_title else []
    if enrichment.score >= 80 and enrichment.journal:
        expected_titles.append(enrichment.journal)
    candidate_title = _first(candidate.get("title_s")) or ""
    title_score = max(
        (
            SequenceMatcher(None, normalize(value), normalize(candidate_title)).ratio()
            for value in expected_titles
        ),
        default=0.0,
    )
    expected_issn = (
        {
            normalize(value)
            for value in [*enrichment.issn, *enrichment.eissn]
            if value
        }
        if enrichment.score >= 80
        else set()
    )
    candidate_issn = {
        normalize(value)
        for value in [
            *_values(candidate.get("issn_s")),
            *_values(candidate.get("eissn_s")),
        ]
        if value
    }
    identifier_match = bool(expected_issn & candidate_issn)
    score = title_score * 100
    if expected_issn:
        score = title_score * 30 + (70 if identifier_match else 0)
    return round(score, 1), identifier_match


def _journal_authority_candidates(
    publication: Publication,
    enrichment: Enrichment,
    opener: Callable[..., object],
    timeout: float,
) -> tuple[list[dict[str, object]], str]:
    identifiers = (
        list(dict.fromkeys([*enrichment.issn, *enrichment.eissn]))
        if enrichment.score >= 80
        else []
    )
    if identifiers:
        clauses = [f'(issn_s:"{value}" OR eissn_s:"{value}")' for value in identifiers]
        query = " OR ".join(clauses)
    else:
        title = (
            enrichment.journal
            if enrichment.score >= 80 and enrichment.journal
            else publication.journal_title or ""
        )
        query = f'title_t:"{title.replace(chr(34), chr(92) + chr(34))}"'
    params = {
        "q": query,
        "fl": "docid,title_s,issn_s,eissn_s,publisher_s,valid_s",
        "rows": 50,
        "wt": "json",
    }
    url = f"{HAL_JOURNAL_REF_URL}?{urlencode(params)}"
    payload = _get_json(url, opener, timeout)
    response = payload.get("response") or {}
    return list(response.get("docs") or []), url  # type: ignore[union-attr]


def _same_journal_evidence(
    publication: Publication,
    enrichment: Enrichment,
    opener: Callable[..., object],
    timeout: float,
) -> tuple[str | None, str | None, list[str], str]:
    params = {
        "q": f"journalId_i:{enrichment.journal_id}",
        "fl": "halId_s,volume_s,issue_s,label_xml",
        "rows": 30,
        "sort": "producedDate_tdate desc",
        "wt": "json",
    }
    url = f"{HAL_SEARCH_URL}?{urlencode(params)}"
    payload = _get_json(url, opener, timeout)
    docs = (payload.get("response") or {}).get("docs") or []  # type: ignore[union-attr]
    candidate_number = publication.issue or enrichment.issue or enrichment.volume
    issue_count = sum(bool(_values(item.get("issue_s"))) for item in docs)
    volume_count = sum(bool(_values(item.get("volume_s"))) for item in docs)
    issue = enrichment.issue
    volume = enrichment.volume
    if candidate_number and issue_count > volume_count:
        issue, volume = candidate_number, None
    elif candidate_number and volume_count > issue_count:
        volume, issue = candidate_number, None

    themes: list[str] = []
    evidence_ids: list[str] = []
    for item in docs:
        values = [*_values(item.get("issue_s")), *_values(item.get("volume_s"))]
        if candidate_number and candidate_number not in values:
            continue
        label_xml = str(item.get("label_xml") or "")
        match = re.search(r'<biblScope unit="serie">([^<]+)</biblScope>', label_xml)
        if match:
            themes.append(match.group(1))
        if item.get("halId_s"):
            evidence_ids.append(str(item["halId_s"]))
    issue_title = Counter(themes).most_common(1)[0][0] if themes else None
    return volume, issue, evidence_ids[:10], issue_title or enrichment.issue_title


def validate_journal_authority(
    publication: Publication,
    enrichment: Enrichment,
    opener: Callable[..., object] = urlopen,
    timeout: float = 20.0,
) -> Enrichment:
    """Resolve a journal article against VALID HAL journal authorities.

    The authority is accepted only when a strong title/ISSN match is unique.
    Same-journal HAL records are then used as evidence for issue-versus-volume
    conventions and issue themes. Ambiguity is retained as a review note.
    """
    if publication.publication_type is not PublicationType.JOURNAL_ARTICLE:
        return enrichment
    try:
        candidates, authority_url = _journal_authority_candidates(
            publication, enrichment, opener, timeout
        )
        scored = []
        for candidate in candidates:
            if _first(candidate.get("valid_s")) != "VALID":
                continue
            score, identifier_match = _journal_authority_score(publication, enrichment, candidate)
            scored.append((score, identifier_match, candidate))
        scored.sort(key=lambda item: item[0], reverse=True)
        if (
            not scored
            or (not scored[0][1] and scored[0][0] < 90)
            or (scored[0][1] and scored[0][0] < 75)
        ):
            enrichment.validation_notes.append(
                "No unique high-confidence VALID HAL journal authority found"
            )
            return enrichment
        best_score, identifier_match, best = scored[0]
        if len(scored) > 1 and scored[1][0] >= best_score - 2 and not identifier_match:
            enrichment.validation_notes.append(
                "Ambiguous HAL journal authority candidates require human review"
            )
            return enrichment

        enrichment.journal_id = str(best["docid"])
        enrichment.journal_status = "VALID"
        enrichment.journal_authority_score = best_score
        enrichment.journal = _first(best.get("title_s")) or enrichment.journal
        enrichment.publisher = _first(best.get("publisher_s")) or enrichment.publisher
        enrichment.issn = _values(best.get("issn_s")) or enrichment.issn
        enrichment.eissn = _values(best.get("eissn_s"))
        enrichment.metadata_sources.append(authority_url)

        volume, issue, evidence_ids, issue_title = _same_journal_evidence(
            publication, enrichment, opener, timeout
        )
        enrichment.volume = volume
        enrichment.issue = issue
        enrichment.issue_title = issue_title
        enrichment.metadata_sources.extend(
            f"https://hal.science/{hal_id}" for hal_id in evidence_ids
        )
        enrichment.validation_notes.append(
            f"Validated against HAL journal authority {enrichment.journal_id}"
        )
        return enrichment
    except Exception as exc:
        enrichment.validation_notes.append(f"HAL journal authority validation unavailable: {exc}")
        return enrichment


def enrich_publication(
    publication: Publication,
    opener: Callable[..., object] = urlopen,
) -> Enrichment:
    try:
        crossref = enrich_crossref(publication, opener=opener)
        if crossref.score >= 80:
            best = crossref
        else:
            openalex = enrich_openalex(publication, opener=opener)
            best = openalex if openalex.score > crossref.score else crossref
        return validate_journal_authority(publication, best, opener=opener)
    except Exception as exc:
        return Enrichment(source="error", error=str(exc))


def enrich_publications(publications: list[Publication]) -> list[Publication]:
    for publication in publications:
        if publication.hal_match is None or publication.hal_match.status.value != "found":
            publication.enrichment = enrich_publication(publication)
    return publications
