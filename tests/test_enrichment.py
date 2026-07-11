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
                }
            ]
        }
    }

    def opener(request, timeout: float):
        assert "query.bibliographic=Mon+article" in request.full_url
        return Response(json.dumps(payload).encode())

    result = enrich_crossref(publication(), opener=opener)
    assert result.source == "crossref"
    assert result.score == 100.0
    assert result.doi == "10.1234/example"
    assert result.journal == "Revue test"
    assert result.issn == ["1234-5678"]


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
