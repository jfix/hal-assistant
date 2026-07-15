import io
import json

from hal_assistant.enrichment import (
    enrich_crossref,
    enrich_openalex,
    validate_journal_authority,
)
from hal_assistant.models import Enrichment, Publication, PublicationType


def publication() -> Publication:
    return Publication(
        publication_type=PublicationType.JOURNAL_ARTICLE,
        section="Article dans revue",
        raw_citation="« Mon article », Revue test, 2024, p. 10-20.",
        title="Mon article",
        year=2024,
        pages="10-20",
        authors=["Florence Fix"],
        journal_title="Revue test",
        source_paragraph=1,
    )


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_crossref_enrichment_extracts_container_metadata() -> None:
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
                    "volume": "12",
                    "issue": "3",
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
    assert result.volume == "12"
    assert result.issue == "3"
    assert result.work_type == "journal-article"
    assert result.suggested_publication_type is PublicationType.JOURNAL_ARTICLE
    assert result.issn == ["1234-5678"]
    assert result.metadata_sources == ["https://doi.org/10.1234/example"]


def test_crossref_prefers_matching_host_for_generic_title() -> None:
    item = publication().model_copy(
        update={
            "publication_type": PublicationType.BOOK_CHAPTER,
            "title": "Introduction",
            "book_title": "Le théâtre et ses objets",
            "journal_title": None,
        }
    )
    payload = {
        "message": {
            "items": [
                {
                    "title": ["Introduction"],
                    "container-title": ["Un autre ouvrage"],
                    "issued": {"date-parts": [[2024]]},
                    "page": "10-20",
                    "type": "book-chapter",
                    "author": [{"given": "Florence", "family": "Fix"}],
                    "DOI": "10.1234/wrong",
                },
                {
                    "title": ["Introduction"],
                    "container-title": ["Le théâtre et ses objets"],
                    "issued": {"date-parts": [[2024]]},
                    "page": "10-20",
                    "type": "book-chapter",
                    "author": [{"given": "Florence", "family": "Fix"}],
                    "DOI": "10.1234/correct",
                },
            ]
        }
    }

    def opener(request, timeout: float):
        return Response(json.dumps(payload).encode())

    result = enrich_crossref(item, opener=opener)
    assert result.score == 100.0
    assert result.doi == "10.1234/correct"
    assert result.container_title == "Le théâtre et ses objets"


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
                    "source": {
                        "display_name": "Revue test",
                        "issn": ["1234-5678"],
                    }
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
    assert result.metadata_sources == ["https://openalex.org/W123"]


def test_openalex_enrichment_accepts_missing_source_issn() -> None:
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W123",
                "title": "Mon article",
                "publication_year": 2024,
                "ids": {},
                "primary_location": {
                    "source": {
                        "display_name": "Revue test",
                        "issn": None,
                    }
                },
            }
        ]
    }

    def opener(request, timeout: float):
        return Response(json.dumps(payload).encode())

    result = enrich_openalex(publication(), opener=opener)
    assert result.score == 100.0
    assert result.journal == "Revue test"
    assert result.issn == []


def test_journal_validation_uses_unique_valid_issn_authority() -> None:
    item = publication().model_copy(update={"journal_title": "Res Futurae"})
    enrichment = Enrichment(
        source="crossref",
        score=100,
        journal="Res Futurae",
        issn=["2264-6949"],
    )
    payload = {
        "response": {
            "docs": [
                {
                    "docid": "88663",
                    "title_s": (
                        "ReS Futurae - Revue d'études sur la science-fiction"
                    ),
                    "issn_s": "2264-6949",
                    "eissn_s": "2264-6949",
                    "publisher_s": "Université de Limoges",
                    "valid_s": "VALID",
                }
            ]
        }
    }

    def opener(request, timeout: float):
        assert "2264-6949" in request.full_url
        return Response(json.dumps(payload).encode())

    result = validate_journal_authority(item, enrichment, opener=opener)
    assert result.journal_id == "88663"
    assert result.journal_status == "VALID"
    assert result.journal_authority_score >= 80
    assert result.journal == (
        "ReS Futurae - Revue d'études sur la science-fiction"
    )
    assert result.publisher == "Université de Limoges"
    assert result.issn == ["2264-6949"]
    assert result.eissn == ["2264-6949"]
    assert "authority 88663" in " ".join(result.validation_notes)


def test_journal_validation_ignores_low_confidence_external_identifiers() -> None:
    item = publication().model_copy(
        update={"journal_title": "Revue d’études culturelles"}
    )
    enrichment = Enrichment(
        source="crossref",
        score=34.2,
        journal="Unrelated journal",
        issn=["1660-9379"],
    )
    payload = {
        "response": {
            "docs": [
                {
                    "docid": "57705",
                    "title_s": "Revue d'études culturelles",
                    "issn_s": "1959-1985",
                    "publisher_s": "ABELL",
                    "valid_s": "VALID",
                }
            ]
        }
    }

    def opener(request, timeout: float):
        assert "1660-9379" not in request.full_url
        assert "title_t" in request.full_url
        return Response(json.dumps(payload).encode())

    result = validate_journal_authority(item, enrichment, opener=opener)
    assert result.journal_id == "57705"
    assert result.journal == "Revue d'études culturelles"
    assert result.issn == ["1959-1985"]


def test_journal_validation_rejects_ambiguous_title_only_authorities() -> None:
    item = publication().model_copy(update={"journal_title": "Revue test"})
    enrichment = Enrichment(source="crossref", score=20)
    payload = {
        "response": {
            "docs": [
                {"docid": "100", "title_s": "Revue test", "valid_s": "VALID"},
                {"docid": "101", "title_s": "Revue test", "valid_s": "VALID"},
            ]
        }
    }

    def opener(request, timeout: float):
        return Response(json.dumps(payload).encode())

    result = validate_journal_authority(item, enrichment, opener=opener)
    assert result.journal_id is None
    assert "Ambiguous" in " ".join(result.validation_notes)
