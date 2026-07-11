import io
import json

from hal_assistant.hal import build_search_url, score_candidate, search_publication
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


def test_build_search_url_contains_title_and_year() -> None:
    url = build_search_url(publication())
    assert "api.archives-ouvertes.fr/search/hal" in url
    assert "producedDateY_i%3A2024" in url
    assert "title_t%3A%22Mon+article%22" in url


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

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    def opener(url: str, timeout: float):
        assert timeout == 20.0
        return Response(json.dumps(payload).encode())

    match = search_publication(publication(), opener=opener)
    assert match.status is HALMatchStatus.FOUND
    assert match.hal_id == "hal-12345678"
    assert match.score == 100.0
    assert match.url == "https://hal.science/hal-12345678"


def test_search_publication_handles_no_results() -> None:
    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    def opener(url: str, timeout: float):
        return Response(b'{"response":{"docs":[]}}')

    match = search_publication(publication(), opener=opener)
    assert match.status is HALMatchStatus.NOT_FOUND
