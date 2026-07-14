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


def test_openalex_enrichment_accepts_missing_source_issn() -> None:
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W123",
                "title": "Mon article",
                "publication_year": 2024,
                "ids": {},
                "primary_location": {"source": {"display_name": "Revue test", "issn": None}},
            }
        ]
    }

    def opener(request, timeout: float):
        return Response(json.dumps(payload).encode())

    result = enrich_openalex(publication(), opener=opener)
    assert result.score == 100.0
    assert result.journal == "Revue test"
    assert result.issn == []


def test_journal_validation_ignores_low_confidence_external_identifiers() -> None:
    item = publication().model_copy(
        update={"journal_title": "Revue d’études culturelles", "issue": "8"}
    )
    enrichment = Enrichment(
        source="crossref",
        score=34.2,
        journal="Unrelated journal",
        issn=["1660-9379"],
    )
    authority_payload = {
        "response": {
            "docs": [
                {
                    "docid": "57705",
                    "title_s": "Revue d'études culturelles",
                    "issn_s": "1959-1985",
                    "eissn_s": "3099-1609",
                    "publisher_s": "ABELL",
                    "valid_s": "VALID",
                }
            ]
        }
    }
    evidence_payload = {"response": {"docs": [{"issue_s": ["8"]}]}}

    def opener(request, timeout: float):
        if "/ref/journal/" in request.full_url:
            assert "1660-9379" not in request.full_url
            assert "Revue+d%E2%80%99%C3%A9tudes+culturelles" in request.full_url
            return Response(json.dumps(authority_payload).encode())
        return Response(json.dumps(evidence_payload).encode())

    result = validate_journal_authority(item, enrichment, opener=opener)
    assert result.journal_id == "57705"
    assert result.journal == "Revue d'études culturelles"
    assert result.issue == "8"


def test_journal_validation_uses_valid_authority_and_hal_issue_conventions() -> None:
    item = publication().model_copy(update={"journal_title": "Res Futurae", "issue": "18"})
    enrichment = Enrichment(
        source="crossref",
        score=100,
        journal="Res Futurae",
        volume="18",
        issn=["2264-6949"],
    )
    authority_payload = {
        "response": {
            "docs": [
                {
                    "docid": "88663",
                    "title_s": "ReS Futurae - Revue d'études sur la science-fiction",
                    "issn_s": "2264-6949",
                    "eissn_s": "2264-6949",
                    "publisher_s": "Université de Limoges",
                    "valid_s": "VALID",
                }
            ]
        }
    }
    evidence_payload = {
        "response": {
            "docs": [
                {
                    "halId_s": "hal-03501358",
                    "issue_s": ["18"],
                    "label_xml": (
                        '<biblScope unit="serie">Le Théâtre de science-fiction : '
                        "premiers éléments de cartographie</biblScope>"
                    ),
                }
            ]
        }
    }

    def opener(request, timeout: float):
        payload = authority_payload if "/ref/journal/" in request.full_url else evidence_payload
        return Response(json.dumps(payload).encode())

    result = validate_journal_authority(item, enrichment, opener=opener)
    assert result.journal_id == "88663"
    assert result.journal_status == "VALID"
    assert result.journal_authority_score >= 80
    assert result.journal == "ReS Futurae - Revue d'études sur la science-fiction"
    assert result.issue == "18"
    assert result.volume is None
    assert result.issue_title == "Le Théâtre de science-fiction : premiers éléments de cartographie"
    assert result.issn == ["2264-6949"]
    assert result.eissn == ["2264-6949"]
    assert "hal-03501358" in " ".join(result.metadata_sources)
