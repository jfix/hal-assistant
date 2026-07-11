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
        "type", "section", "title", "year", "pages", "url", "authors",
        "HAL status", "HAL ID", "HAL score", "HAL title", "HAL year",
        "HAL authors", "HAL URL", "HAL error",
        "enrichment source", "enrichment score", "canonical title", "DOI",
        "journal", "publisher", "ISSN", "ISBN", "enrichment URL", "enrichment error",
        "raw_citation", "source_paragraph",
    ]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:AA{max(1, len(publications) + 1)}"

    for item in publications:
        match = item.hal_match
        enrichment = item.enrichment
        sheet.append([
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
            enrichment.source if enrichment else None,
            enrichment.score if enrichment else None,
            enrichment.canonical_title if enrichment else None,
            enrichment.doi if enrichment else None,
            enrichment.journal if enrichment else None,
            enrichment.publisher if enrichment else None,
            "; ".join(enrichment.issn) if enrichment else None,
            "; ".join(enrichment.isbn) if enrichment else None,
            enrichment.url if enrichment else None,
            enrichment.error if enrichment else None,
            item.raw_citation,
            item.source_paragraph,
        ])

    widths = {
        "A": 20, "B": 34, "C": 58, "D": 10, "E": 14, "F": 40, "G": 24,
        "H": 16, "I": 20, "J": 12, "K": 58, "L": 10, "M": 34, "N": 42,
        "O": 36, "P": 18, "Q": 14, "R": 58, "S": 28, "T": 34, "U": 34,
        "V": 24, "W": 24, "X": 42, "Y": 36, "Z": 100, "AA": 18,
    }
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width
    workbook.save(output)
    return output
