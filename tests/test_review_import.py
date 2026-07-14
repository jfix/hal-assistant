from pathlib import Path

from openpyxl import Workbook

from hal_assistant.review_import import read_publications_sheet


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
