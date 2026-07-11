from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from .models import Publication


def export_json(publications: list[Publication], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in publications],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return output


def export_excel(publications: list[Publication], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Publications"
    headers = [
        "type",
        "section",
        "title",
        "year",
        "pages",
        "url",
        "authors",
        "HAL status",
        "HAL ID",
        "HAL score",
        "HAL title",
        "HAL year",
        "HAL authors",
        "HAL URL",
        "HAL error",
        "raw_citation",
        "source_paragraph",
    ]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:Q{max(1, len(publications) + 1)}"

    for item in publications:
        match = item.hal_match
        sheet.append(
            [
                item.publication_type.value,
                item.section,
                item.title,
                item.year,
                item.pages,
                item.url,
                "; ".join(item.authors),
                match.status.value if match else None,
                match.hal_id if match else None,
                match.score if match else None,
                match.title if match else None,
                match.year if match else None,
                "; ".join(match.authors) if match else None,
                match.url if match else None,
                match.error if match else None,
                item.raw_citation,
                item.source_paragraph,
            ]
        )

    widths = {
        "A": 20,
        "B": 34,
        "C": 58,
        "D": 10,
        "E": 14,
        "F": 48,
        "G": 24,
        "H": 16,
        "I": 20,
        "J": 12,
        "K": 58,
        "L": 10,
        "M": 34,
        "N": 42,
        "O": 40,
        "P": 100,
        "Q": 18,
    }
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width
    workbook.save(output)
    return output
