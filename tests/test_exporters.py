import json
from pathlib import Path

from openpyxl import load_workbook

from hal_assistant.exporters import export_excel, export_json
from hal_assistant.models import Publication, PublicationType


def sample_publication() -> Publication:
    return Publication(
        publication_type=PublicationType.JOURNAL_ARTICLE,
        section="Article dans revue",
        raw_citation="« Test », Revue, 2024, p.1-2.",
        title="Test",
        year=2024,
        pages="1-2",
        authors=["Florence Fix"],
        source_paragraph=2,
    )


def test_json_export(tmp_path: Path) -> None:
    path = export_json([sample_publication()], tmp_path / "out.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data[0]["title"] == "Test"


def test_excel_export(tmp_path: Path) -> None:
    path = export_excel([sample_publication()], tmp_path / "out.xlsx")
    sheet = load_workbook(path).active
    assert sheet["C2"].value == "Test"
