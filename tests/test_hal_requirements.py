from hal_assistant.hal_requirements import audit_record, audit_records


def _base(document_type: str) -> dict[str, object]:
    return {
        "publication_id": "pub-0001",
        "document_type": document_type,
        "title": "Titre",
        "authors": "Florence Fix",
        "year": 2020,
        "language": "fr",
    }


def test_art_requires_journal_title() -> None:
    result = audit_record(_base("ART"))
    assert result.ready is False
    assert result.missing_required_fields == ["journal_title"]


def test_art_accepts_legacy_container_title() -> None:
    record = _base("ART")
    record["container_title"] = "Revue d'histoire littéraire"
    result = audit_record(record)
    assert result.ready is True


def test_couv_requires_book_title() -> None:
    result = audit_record(_base("COUV"))
    assert result.missing_required_fields == ["book_title"]


def test_comm_requires_conference_metadata() -> None:
    result = audit_record(_base("COMM"))
    assert result.missing_required_fields == [
        "conference_title",
        "conference_start_date",
        "conference_end_date",
        "conference_city",
        "conference_country",
    ]


def test_douv_uses_common_required_fields() -> None:
    assert audit_record(_base("DOUV")).ready is True


def test_audit_summary_groups_missing_fields() -> None:
    art = _base("ART")
    comm = _base("COMM")
    comm["publication_id"] = "pub-0002"
    audit = audit_records([art, comm])
    assert audit["total"] == 2
    assert audit["ready"] == 0
    assert audit["blocked"] == 2
    assert audit["types"]["ART"]["missing_fields"] == {"journal_title": 1}
    assert audit["types"]["COMM"]["missing_fields"]["conference_title"] == 1
