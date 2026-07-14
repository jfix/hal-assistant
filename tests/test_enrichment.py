import io
import json

from hal_assistant.enrichment import enrich_crossref, enrich_openalex
from hal_assistant.models import Publication, PublicationType


def publication() -> Publication:
    return Publication(
        publication_type=PublicationType.JOURNAL_ARTICLE,
        section="Article dans revue",
        raw_citation="« Mon article », Revue test, 2024.",
        title="Mon article",
        year=2024,
        authors=["Florence Fix"],
        source_paragraph=1,
        journal_title="Revue test",
        pages="10-20",
    )


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_crossref_enrichment_extracts_identifiers() -> None:
    payload = {
        "message": {
            "items": [
                {
                    "title": ["Mon article"],
                    "issued": {"date-parts": [[2024]]},
                    "DOI": "10.1234/example",
                    "container-title": ["Revue test"],
                    "publisher": "Example Press",
                    "ISSN": ["1234-5678"],
                    "URL": "https://doi.org/10.1234/example",
                    "page": "10-20",
                    "type": "journal-article",
                    "author": [{"given": "Florence", "family": "Fix"}],
                }
            ]
        }
    }

    def opener(request, timeout: float):
        assert "query.bibliographic=Mon+article+Revue+test" in request.full_url
        assert "query.author=Florence+Fix" in request.full_url
        return Response(json.dumps(payload).encode())

    result = enrich_crossref(publication(), opener=opener)
    assert result.source == "crossref"
    assert result.score == 100.0
    assert result.doi == "10.1234/example"
    assert result.journal == "Revue test"
    assert result.container_title == "Revue test"
    assert result.pages == "10-20"
    assert result.work_type == "journal-article"
    assert result.suggested_publication_type is PublicationType.JOURNAL_ARTICLE
    assert result.issn == ["1234-5678"]


def test_crossref_flags_book_chapter_type_disagreement() -> None:
    item = publication().model_copy(
        update={
            "publication_type": PublicationType.CONFERENCE_PAPER,
            "journal_title": None,
            "book_title": "Collective volume",
        }
    )
    payload = {
        "message": {
            "items": [
                {
                    "title": ["Mon article"],
                    "container-title": ["Collective volume"],
                    "issued": {"date-parts": [[2024]]},
                    "page": "10-20",
                    "type": "book-chapter",
                    "author": [{"given": "Florence", "family": "Fix"}],
                }
            ]
        }
    }

    def opener(request, timeout: float):
        return Response(json.dumps(payload).encode())

    result = enrich_crossref(item, opener=opener)
    assert result.score == 100.0
    assert result.suggested_publication_type is PublicationType.BOOK_CHAPTER
    assert result.type_review_reason is not None


def test_openalex_enrichment_extracts_source() -> None:
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W123",
                "title": "Mon article",
                "publication_year": 2024,
                "ids": {"doi": "https://doi.org/10.1234/example"},
                "primary_location": {
                    "source": {"display_name": "Revue test", "issn": ["1234-5678"]}
                },
            }
        ]
    }

    def opener(request, timeout: float):
        assert "search=Mon+article" in request.full_url
        return Response(json.dumps(payload).encode())

    result = enrich_openalex(publication(), opener=opener)
    assert result.source == "openalex"
    assert result.score == 100.0
    assert result.doi == "10.1234/example"
    assert result.journal == "Revue test"
