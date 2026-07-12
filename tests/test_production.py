import json
from pathlib import Path

import pytest

from hal_assistant.hal_xml import build_tei, write_tei
from hal_assistant.production import prepare_production_batch


def _record(publication_id: str = "pub-0002", title: str = "Livre validé") -> dict[str, object]:
    return {
        "publication_id": publication_id,
        "document_type": "OUV",
        "title": title,
        "year": 2020,
        "authors": ["Florence Fix"],
        "language": "fr",
        "pages": "200",
        "hal_structure_id": "95026",
    }


def _write_ledger(
    path: Path,
    *,
    results: list[dict[str, object]] | None = None,
    accepted: bool = True,
    environment: str = "preprod",
) -> None:
    if results is None:
        results = [
            {
                "xml_file": "pub-0002.xml",
                "status_code": 202 if accepted else 400,
                "accepted": accepted,
            }
        ]
    path.write_text(
        json.dumps(
            {
                "environment": environment,
                "test": True,
                "load_filter": "noaffiliation",
                "submitted": len(results),
                "accepted": sum(item.get("accepted") is True for item in results),
                "results": results,
            }
        ),
        encoding="utf-8",
    )


def test_prepare_production_batch_copies_only_preprod_accepted_files(
    tmp_path: Path,
) -> None:
    xml_dir = tmp_path / "hal-xml"
    xml_dir.mkdir()
    tree = build_tei(
        _record(),
        domain="shs.litt",
        domain_label="Littératures",
    )
    write_tei(tree, xml_dir / "pub-0002.xml")
    _write_ledger(xml_dir / "submission-ledger.json")

    batch = prepare_production_batch(
        xml_dir,
        output_dir=tmp_path / "production",
    )

    assert [path.name for path in batch.files] == ["pub-0002.xml"]
    manifest = json.loads(batch.manifest_path.read_text(encoding="utf-8"))
    assert manifest["environment"] == "production"
    assert manifest["test"] is False
    assert manifest["force_duplicate_by_title"] is False
    assert manifest["file_count"] == 1
    assert manifest["excluded_count"] == 0
    assert manifest["files"][0]["sha256"]
    assert manifest["files"][0]["title"] == "Livre validé"


def test_prepare_production_batch_excludes_rejected_results(tmp_path: Path) -> None:
    xml_dir = tmp_path / "hal-xml"
    xml_dir.mkdir()
    accepted_tree = build_tei(
        _record(),
        domain="shs.litt",
        domain_label="Littératures",
    )
    rejected_tree = build_tei(
        _record("pub-0003", "Notice rejetée"),
        domain="shs.litt",
        domain_label="Littératures",
    )
    write_tei(accepted_tree, xml_dir / "pub-0002.xml")
    write_tei(rejected_tree, xml_dir / "pub-0003.xml")
    _write_ledger(
        xml_dir / "submission-ledger.json",
        results=[
            {"xml_file": "pub-0002.xml", "status_code": 202, "accepted": True},
            {
                "xml_file": "pub-0003.xml",
                "status_code": 400,
                "accepted": False,
                "error": "HAL returned HTTP 400",
            },
        ],
    )

    batch = prepare_production_batch(
        xml_dir,
        output_dir=tmp_path / "production",
    )

    assert [path.name for path in batch.files] == ["pub-0002.xml"]
    manifest = json.loads(batch.manifest_path.read_text(encoding="utf-8"))
    assert manifest["file_count"] == 1
    assert manifest["excluded_count"] == 1
    assert manifest["excluded"][0]["xml_file"] == "pub-0003.xml"


def test_prepare_production_batch_rejects_ledger_without_accepted_results(
    tmp_path: Path,
) -> None:
    xml_dir = tmp_path / "hal-xml"
    xml_dir.mkdir()
    (xml_dir / "pub-0002.xml").write_text("<TEI/>", encoding="utf-8")
    _write_ledger(xml_dir / "submission-ledger.json", accepted=False)

    with pytest.raises(ValueError, match="no accepted notices"):
        prepare_production_batch(
            xml_dir,
            output_dir=tmp_path / "production",
        )


def test_prepare_production_batch_rejects_non_preprod_ledger(
    tmp_path: Path,
) -> None:
    xml_dir = tmp_path / "hal-xml"
    xml_dir.mkdir()
    _write_ledger(
        xml_dir / "submission-ledger.json",
        environment="production",
    )

    with pytest.raises(ValueError, match="preproduction test"):
        prepare_production_batch(
            xml_dir,
            output_dir=tmp_path / "production",
        )
