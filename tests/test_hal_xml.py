import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from hal_assistant.hal_xml import TEI_NS, build_tei, build_xml_batch, validate_tei
from hal_assistant.review_cli import add_hal_document_types
from hal_assistant.sword import submit_batch


def sample_record() -> dict[str, object]:
    return {
        "publication_id": "pub-0001",
        "document_type": "ART",
        "title": "Un article sur le XIXe siècle",
        "year": 2024,
        "authors": "Florence Fix; Jeanne Exemple",
        "container_title": "Revue test",
        "issue": "8",
        "pages": "12-19",
        "language": "fr",
        "doi": "10.1234/example",
        "source_url": "https://example.org/article",
    }


def test_build_tei_contains_mandatory_hal_metadata() -> None:
    tree = build_tei(
        sample_record(),
        domain="shs.litt",
        domain_label="Littératures",
        idhal="florence-fix",
        idhal_author="Florence Fix",
    )
    assert validate_tei(tree) == []

    root = tree.getroot()
    ns = {"tei": TEI_NS}
    assert root.findtext(".//tei:analytic/tei:title", namespaces=ns) == (
        "Un article sur le XIXe siècle"
    )
    assert root.findtext(".//tei:author/tei:idno[@type='idhal']", namespaces=ns) == ("florence-fix")
    assert root.find(".//tei:classCode[@scheme='halDomain'][@n='shs.litt']", ns) is not None
    assert root.find(".//tei:classCode[@scheme='halTypology'][@n='ART']", ns) is not None
    assert root.findtext(".//tei:biblScope[@unit='issue']", namespaces=ns) == "8"
    assert root.findtext(".//tei:idno[@type='doi']", namespaces=ns) == "10.1234/example"


def test_publication_identifiers_use_aofr_container_levels() -> None:
    record = sample_record() | {
        "journalId": "88663",
        "journalStatus": "VALID",
        "isbn": "978-2-406-18678-6",
        "issn": "1234-5678",
        "eissn": "8765-4321",
        "issueTitle": "Issue theme",
    }
    root = build_tei(record, domain="shs.litt").getroot()
    ns = {"tei": TEI_NS}
    bibl_struct = root.find(".//tei:biblStruct", ns)
    assert bibl_struct is not None
    assert bibl_struct.findtext("tei:idno[@type='doi']", namespaces=ns) == "10.1234/example"
    assert (
        bibl_struct.findtext("tei:monogr/tei:idno[@type='isbn']", namespaces=ns)
        == "978-2-406-18678-6"
    )
    assert bibl_struct.findtext("tei:monogr/tei:idno[@type='issn']", namespaces=ns) == "1234-5678"
    assert bibl_struct.findtext("tei:monogr/tei:idno[@type='eissn']", namespaces=ns) == "8765-4321"
    journal_id = bibl_struct.find("tei:monogr/tei:idno[@type='halJournalId']", ns)
    assert journal_id is not None
    assert journal_id.text == "88663"
    assert journal_id.attrib["status"] == "VALID"
    assert (
        bibl_struct.findtext("tei:monogr/tei:imprint/tei:biblScope[@unit='serie']", namespaces=ns)
        == "Issue theme"
    )
    assert bibl_struct.find("tei:idno[@type='isbn']", ns) is None
    assert bibl_struct.find("tei:idno[@type='issn']", ns) is None
    children = list(bibl_struct)
    assert children.index(bibl_struct.find("tei:monogr", ns)) < children.index(
        bibl_struct.find("tei:idno[@type='doi']", ns)
    )
    monogr = bibl_struct.find("tei:monogr", ns)
    assert monogr is not None
    monogr_children = list(monogr)
    assert monogr_children.index(monogr.find("tei:idno[@type='isbn']", ns)) < (
        monogr_children.index(monogr.find("tei:title", ns))
    )


def test_aofr_orders_bibliographic_scopes_before_publication_date() -> None:
    root = build_tei(sample_record(), domain="shs.litt").getroot()
    ns = {"tei": TEI_NS}
    imprint = root.find(".//tei:imprint", ns)
    assert imprint is not None
    children = list(imprint)
    assert children.index(imprint.find("tei:biblScope", ns)) < children.index(
        imprint.find("tei:date[@type='datePub']", ns)
    )


def test_local_validation_rejects_aofr_element_ordering_errors() -> None:
    tree = build_tei(sample_record(), domain="shs.litt")
    root = tree.getroot()
    ns = {"tei": TEI_NS}
    bibl_struct = root.find(".//tei:biblStruct", ns)
    monogr = root.find(".//tei:biblStruct/tei:monogr", ns)
    doi = root.find(".//tei:biblStruct/tei:idno[@type='doi']", ns)
    imprint = root.find(".//tei:imprint", ns)
    date = root.find(".//tei:imprint/tei:date[@type='datePub']", ns)
    assert bibl_struct is not None and monogr is not None and doi is not None
    assert imprint is not None and date is not None

    bibl_struct.remove(doi)
    bibl_struct.insert(list(bibl_struct).index(monogr), doi)
    imprint.remove(date)
    first_scope = next(
        index for index, child in enumerate(imprint) if child.tag == f"{{{TEI_NS}}}biblScope"
    )
    imprint.insert(first_scope, date)

    errors = validate_tei(tree)
    assert "AOfr requires publication identifiers after monogr" in errors
    assert "AOfr requires biblScope before publication date" in errors


def test_local_validation_rejects_isbn_at_bibl_struct_level() -> None:
    tree = build_tei(sample_record() | {"isbn": "978-2-406-18678-6"}, domain="shs.litt")
    root = tree.getroot()
    ns = {"tei": TEI_NS}
    bibl_struct = root.find(".//tei:biblStruct", ns)
    monogr = root.find(".//tei:biblStruct/tei:monogr", ns)
    isbn = root.find(".//tei:monogr/tei:idno[@type='isbn']", ns)
    assert bibl_struct is not None and monogr is not None and isbn is not None
    monogr.remove(isbn)
    bibl_struct.append(isbn)

    assert "AOfr requires ISBN and ISSN identifiers inside monogr" in validate_tei(tree)


def test_build_tei_requires_domain() -> None:
    with pytest.raises(ValueError, match="domain"):
        build_tei(sample_record(), domain="")


def test_review_mapping_preserves_douv_and_container_titles(tmp_path: Path) -> None:
    path = tmp_path / "records.json"
    path.write_text(
        json.dumps(
            [
                {
                    "publication_type": "edited_book",
                    "title": "Livre dirigé",
                },
                {
                    "publication_type": "book_chapter",
                    "title": "Chapitre",
                    "book_title": "Livre collectif",
                },
                {
                    "publication_type": "journal_article",
                    "title": "Article",
                    "journal_title": "Revue test",
                },
            ]
        ),
        encoding="utf-8",
    )

    records = add_hal_document_types(path)

    assert records[0]["document_type"] == "DOUV"
    assert records[1]["container_title"] == "Livre collectif"
    assert records[2]["container_title"] == "Revue test"


def test_douv_serializes_as_monograph_title() -> None:
    record = sample_record() | {
        "document_type": "DOUV",
        "title": "Ouvrage dirigé",
        "container_title": None,
    }
    root = build_tei(record, domain="shs.litt").getroot()
    ns = {"tei": TEI_NS}
    assert root.findtext(".//tei:monogr/tei:title[@level='m']", namespaces=ns) == ("Ouvrage dirigé")


def test_comm_serializes_required_meeting_metadata() -> None:
    record = sample_record() | {
        "document_type": "COMM",
        "conference_title": "Colloque test",
        "conference_start_date": "2024-05-02",
        "conference_end_date": "2024-05-03",
        "conference_city": "Rouen",
        "conference_country": "France",
        "conference_country_code": "fr",
    }
    tree = build_tei(record, domain="shs.litt")
    assert validate_tei(tree) == []

    root = tree.getroot()
    ns = {"tei": TEI_NS}
    assert root.findtext(".//tei:meeting/tei:title", namespaces=ns) == "Colloque test"
    assert root.findtext(".//tei:meeting/tei:date[@type='start']", namespaces=ns) == "2024-05-02"
    assert root.findtext(".//tei:meeting/tei:date[@type='end']", namespaces=ns) == "2024-05-03"
    country = root.find(".//tei:meeting/tei:country", ns)
    assert country is not None
    assert country.attrib["key"] == "FR"


def test_comm_validation_blocks_missing_meeting_metadata() -> None:
    record = sample_record() | {"document_type": "COMM"}
    errors = validate_tei(build_tei(record, domain="shs.litt"))
    assert "Missing conference title" in errors
    assert "Missing conference end date" in errors


def test_comm_serializes_french_conference_place_names() -> None:
    record = sample_record() | {
        "document_type": "COMM",
        "conference_title": "Colloque test",
        "conference_start_date": "2024-05-02",
        "conference_end_date": "2024-05-03",
        "conference_city": "Vienna",
        "conference_country": "Austria",
        "conference_country_code": "at",
    }
    root = build_tei(record, domain="shs.litt").getroot()
    ns = {"tei": TEI_NS}
    assert root.findtext(".//tei:meeting/tei:settlement", namespaces=ns) == "Vienne"
    assert root.findtext(".//tei:meeting/tei:country", namespaces=ns) == "Autriche"


def test_build_xml_batch_writes_manifest_and_well_formed_xml(tmp_path: Path) -> None:
    source = tmp_path / "records.json"
    source.write_text(json.dumps([sample_record()]), encoding="utf-8")

    results = build_xml_batch(
        source,
        tmp_path / "xml",
        domain="shs.litt",
        idhal="florence-fix",
        idhal_author="Florence Fix",
    )

    assert len(results) == 1
    assert results[0].errors == []
    ET.parse(results[0].path)
    manifest = json.loads((tmp_path / "xml" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["valid"] == 1
    assert manifest["blocked"] == 0


def test_production_submission_requires_execute(tmp_path: Path) -> None:
    (tmp_path / "pub-0001.xml").write_text("<TEI/>", encoding="utf-8")
    with pytest.raises(ValueError, match="--execute"):
        submit_batch(
            tmp_path,
            environment="production",
            test=False,
            execute=False,
            on_behalf_of=None,
        )


def test_production_submission_requires_confirmation_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pub-0001.xml").write_text("<TEI/>", encoding="utf-8")
    monkeypatch.delenv("HAL_SWORD_CONFIRM_PRODUCTION", raising=False)
    with pytest.raises(RuntimeError, match="HAL_SWORD_CONFIRM_PRODUCTION"):
        submit_batch(
            tmp_path,
            environment="production",
            test=False,
            execute=True,
            on_behalf_of=None,
        )
