import json
from pathlib import Path

from openpyxl import Workbook

from hal_assistant.review_cli import add_hal_document_types
from hal_assistant.review_import import import_review_workbook


def _write_review_workbook(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Publications"
    sheet.append(
        [
            "publication_id",
            "decision",
            "publication_type",
            "title",
            "year",
            "authors",
            "journal_title",
            "issn",
            "original_citation",
        ]
    )
    sheet.append(
        [
            "pub-paon-1",
            "approve",
            "journal_issue",
            "Le Paon d’Héra 1, Orphée (1)",
            2006,
            "Florence Fix",
            None,
            "1779-2746",
            "Le Paon d’Héra 1, Orphée (1), 2006, 134p.",
        ]
    )
    workbook.save(path)


def test_paon_issue_uses_validated_hal_journal_authority(tmp_path: Path) -> None:
    workbook_path = tmp_path / "review.xlsx"
    _write_review_workbook(workbook_path)

    result = import_review_workbook(workbook_path, tmp_path / "output")
    record = json.loads(result.approved_path.read_text(encoding="utf-8"))[0]

    assert record["container_title"].startswith("Le Paon d'Héra :")
    assert record["journal_id"] == "63383"
    assert record["journal_status"] == "VALID"
    assert record["issue"] == "1"
    assert record["thematic_title"] == "Orphée (1)"


def test_journal_issue_maps_to_douv_and_keeps_journal_container(tmp_path: Path) -> None:
    source = tmp_path / "hal-ready.json"
    source.write_text(
        json.dumps(
            [
                {
                    "publication_id": "pub-paon-1",
                    "publication_type": "journal_issue",
                    "title": "Le Paon d’Héra 1",
                    "journal_title": "Le Paon d’Héra",
                }
            ]
        ),
        encoding="utf-8",
    )

    records = add_hal_document_types(source)

    assert records[0]["document_type"] == "DOUV"
    assert records[0]["container_title"] == "Le Paon d’Héra"
