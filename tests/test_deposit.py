from hal_assistant.deposit import DepositStatus, build_deposit_plan
from hal_assistant.models import (
    Enrichment,
    HALMatch,
    HALMatchStatus,
    Publication,
    PublicationType,
)


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


def test_existing_hal_record_is_skipped() -> None:
    item = publication()
    item.hal_match = HALMatch(
        status=HALMatchStatus.FOUND,
        hal_id="hal-12345678",
        document_type="ART",
        score=100.0,
    )
    plan = build_deposit_plan(item, 1)
    assert plan.status is DepositStatus.SKIPPED_EXISTING
    assert plan.payload == {}


def test_complete_enriched_record_is_ready() -> None:
    item = publication()
    item.hal_match = HALMatch(status=HALMatchStatus.NOT_FOUND)
    item.enrichment = Enrichment(
        source="crossref",
        score=100.0,
        canonical_title="Mon article",
        doi="10.1234/example",
        journal="Revue test",
        journal_id="12345",
        journal_status="VALID",
        issue="8",
        issue_title="Issue theme",
        issn=["1234-5678"],
    )
    plan = build_deposit_plan(item, 1)
    assert plan.status is DepositStatus.READY
    assert plan.payload["docType"] == "ART"
    assert plan.payload["doi"] == "10.1234/example"
    assert plan.payload["journalId"] == "12345"
    assert plan.payload["journalStatus"] == "VALID"
    assert plan.payload["issue"] == "8"
    assert plan.payload["issueTitle"] == "Issue theme"


def test_missing_year_blocks_deposit() -> None:
    item = publication()
    item.year = None
    item.hal_match = HALMatch(status=HALMatchStatus.NOT_FOUND)
    plan = build_deposit_plan(item, 1)
    assert plan.status is DepositStatus.BLOCKED
    assert "Missing publication year" in plan.errors


def test_unenriched_record_needs_review() -> None:
    item = publication()
    item.hal_match = HALMatch(status=HALMatchStatus.NOT_FOUND)
    plan = build_deposit_plan(item, 1)
    assert plan.status is DepositStatus.NEEDS_REVIEW
    assert "No external metadata enrichment available" in plan.warnings
