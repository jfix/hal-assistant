import json
from pathlib import Path

from openpyxl import Workbook

from hal_assistant.review_import import import_review_workbook, read_publications_sheet


def test_reads_workbook_with_absolute_internal_sheet_target(tmp_path: Path) -> None:
    path = tmp_path / "review.xlsx"
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
        ]
    )
    sheet.append(
        [
            "pub-0001",
            "approve",
            "book",
            "Titre",
            2024,
            "Florence Fix",
        ]
    )
    workbook.save(path)

    records = read_publications_sheet(path)

    assert records[0]["publication_id"] == "pub-0001"


def test_paon_issue_uses_validated_hal_journal_authority(tmp_path: Path) -> None:
    path = tmp_path / "review.xlsx"
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

    result = import_review_workbook(path, tmp_path / "output")
    record = json.loads(result.approved_path.read_text(encoding="utf-8"))[0]

    assert record["container_title"].startswith("Le Paon d'Héra :")
    assert record["journal_id"] == "63383"
    assert record["journal_status"] == "VALID"
