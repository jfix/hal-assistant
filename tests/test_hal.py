import io
import json

from hal_assistant.hal import (
    build_idhal_url,
    build_search_url,
    match_publications,
    score_candidate,
    search_publication,
)
from hal_assistant.models import HALMatchStatus, Publication, PublicationType


def publication() -> Publication:
    return Publication(
        publication_type=PublicationType.JOURNAL_ARTICLE,
        section="Article dans revue",
        raw_citation="« Mon article », Revue test, 2024.",
        title="Mon article",
        year=2024,
        authors=["Florence Fix"],
        source_paragraph=1,
    )


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_build_search_url_contains_title_and_year() -> None:
    url = build_search_url(publication())
    assert "api.archives-ouvertes.fr/search/hal" in url
    assert "producedDateY_i%3A2024" in url
    assert "title_t%3A%22Mon+article%22" in url


def test_build_idhal_url_uses_author_identifier() -> None:
    url = build_idhal_url("florence-fix")
    assert "authIdHal_s%3A%22florence-fix%22" in url
    assert "rows=1000" in url


def test_score_candidate_uses_title_year_and_author() -> None:
    candidate = {
        "title_s": ["Mon article"],
        "producedDateY_i": 2024,
        "authFullName_s": ["Florence Fix"],
    }
    assert score_candidate(publication(), candidate) == 100.0


def test_search_publication_returns_best_match() -> None:
    payload = {
        "response": {
            "docs": [
                {
                    "halId_s": "hal-12345678",
                    "title_s": ["Mon article"],
                    "producedDateY_i": 2024,
                    "authFullName_s": ["Florence Fix"],
                    "docType_s": "ART",
                }
            ]
        }
    }

    def opener(url: str, timeout: float):
        assert timeout == 20.0
        return Response(json.dumps(payload).encode())

    match = search_publication(publication(), opener=opener)
    assert match.status is HALMatchStatus.FOUND
    assert match.hal_id == "hal-12345678"
    assert match.score == 100.0
    assert match.url == "https://hal.science/hal-12345678"


def test_match_publications_fetches_idhal_candidates_once() -> None:
    payload = {
        "response": {
            "docs": [
                {
                    "halId_s": "hal-12345678",
                    "title_s": ["Mon article"],
                    "producedDateY_i": 2024,
                    "authFullName_s": ["Florence Fix"],
                    "docType_s": "ART",
                }
            ]
        }
    }
    calls = 0

    def opener(url: str, timeout: float):
        nonlocal calls
        calls += 1
        assert "authIdHal_s" in url
        return Response(json.dumps(payload).encode())

    publications = [publication(), publication()]
    match_publications(publications, idhal="florence-fix", opener=opener)
    assert calls == 1
    assert all(item.hal_match.status is HALMatchStatus.FOUND for item in publications)


def test_search_publication_handles_no_results() -> None:
    def opener(url: str, timeout: float):
        return Response(b'{"response":{"docs":[]}}')

    match = search_publication(publication(), opener=opener)
    assert match.status is HALMatchStatus.NOT_FOUND
