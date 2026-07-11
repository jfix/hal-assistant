import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from hal_assistant.hal_xml import TEI_NS, build_tei, build_xml_batch, validate_tei
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
    assert root.findtext(".//tei:author/tei:idno[@type='idhal']", namespaces=ns) == (
        "florence-fix"
    )
    assert root.find(".//tei:classCode[@scheme='halDomain'][@n='shs.litt']", ns) is not None
    assert root.find(".//tei:classCode[@scheme='halTypology'][@n='ART']", ns) is not None
    assert root.findtext(".//tei:biblScope[@unit='issue']", namespaces=ns) == "8"
    assert root.findtext(".//tei:idno[@type='doi']", namespaces=ns) == "10.1234/example"


def test_build_tei_requires_domain() -> None:
    with pytest.raises(ValueError, match="domain"):
        build_tei(sample_record(), domain="")


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
