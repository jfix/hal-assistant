from pathlib import Path

from docx import Document

from hal_assistant.models import PublicationType
from hal_assistant.parser import extract_title, parse_docx


def test_extract_quoted_title() -> None:
    assert extract_title("« Un titre », in Une revue, 2024, p.1-10.") == "Un titre"


def test_parse_docx_sections_and_metadata(tmp_path: Path) -> None:
    source = tmp_path / "sample.docx"
    document = Document()
    document.add_paragraph("Ouvrages")
    document.add_paragraph("Mon livre, Paris, Exemple, 2020, 230p.")
    document.add_paragraph("Article dans revue")
    document.add_paragraph("« Mon article », Revue test, 2024, p. 12-19. https://example.org/a")
    document.save(source)

    items = parse_docx(source, default_author="Florence Fix")

    assert len(items) == 2
    assert items[0].publication_type is PublicationType.BOOK
    assert items[0].year == 2020
    assert items[0].pages == "230"
    assert items[1].publication_type is PublicationType.JOURNAL_ARTICLE
    assert items[1].title == "Mon article"
    assert items[1].url == "https://example.org/a"
    assert items[1].authors == ["Florence Fix"]
