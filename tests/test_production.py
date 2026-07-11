import json
from pathlib import Path

import pytest

from hal_assistant.hal_xml import build_tei, write_tei
from hal_assistant.production import prepare_production_batch


def _record() -> dict[str, object]:
    return {
        "publication_id": "pub-0002",
        "document_type": "OUV",
        "title": "Livre validé",
        "year": 2020,
        "authors": ["Florence Fix"],
        "language": "fr",
        "pages": "200",
        "hal_structure_id": "95026",
    }


def _write_ledger(
    path: Path,
    *,
    accepted: bool = True,
    environment: str = "preprod",
) -> None:
    path.write_text(
        json.dumps(
            {
                "environment": environment,
                "test": True,
                "load_filter": "noaffiliation",
                "submitted": 1,
                "accepted": int(accepted),
                "results": [
                    {
                        "xml_file": "pub-0002.xml",
                        "status_code": 202 if accepted else 400,
                        "accepted": accepted,
                    }
                ],
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
    assert manifest["files"][0]["sha256"]
    assert manifest["files"][0]["title"] == "Livre validé"


def test_prepare_production_batch_rejects_failed_preprod_result(
    tmp_path: Path,
) -> None:
    xml_dir = tmp_path / "hal-xml"
    xml_dir.mkdir()
    (xml_dir / "pub-0002.xml").write_text("<TEI/>", encoding="utf-8")
    _write_ledger(xml_dir / "submission-ledger.json", accepted=False)

    with pytest.raises(ValueError, match="rejected notices"):
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
