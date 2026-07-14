from pathlib import Path

from docx import Document

from hal_assistant.models import PublicationType
from hal_assistant.parser import (
    extract_book_title,
    extract_conference_metadata,
    extract_journal_title,
    extract_title,
    normalize_centuries,
    parse_docx,
)


def test_extract_quoted_title() -> None:
    assert extract_title("« Un titre », in Une revue, 2024, p.1-10.") == "Un titre"


def test_extract_title_with_nested_french_guillemets() -> None:
    citation = (
        "« Qu’est-ce qu’un « mauvais » théâtre de science-fiction (avant 1920) ? », "
        "in Res Futurae, n°18, 2021."
    )
    assert (
        extract_title(citation)
        == "Qu’est-ce qu’un « mauvais » théâtre de science-fiction (avant 1920) ?"
    )


def test_normalize_centuries_uppercases_explicit_roman_numerals() -> None:
    assert normalize_centuries("Femmes de spectacle au xixe siècle") == (
        "Femmes de spectacle au XIXe siècle"
    )
    assert normalize_centuries("du xviie-xixe siècles") == "du XVIIe-XIXe siècles"


def test_normalize_centuries_does_not_change_ordinary_words() -> None:
    assert normalize_centuries("Pauvreté, maladie et fin de vie") == (
        "Pauvreté, maladie et fin de vie"
    )


def test_extract_book_title_after_editor_prefix() -> None:
    citation = (
        "« La faim après la faim », avant-propos in Florence Fix (éd.), "
        "Manger et être mangé, L’alimentation et ses récits, Paris, Orizons, 2016, p.11-25."
    )
    assert extract_book_title(citation) == (
        "Manger et être mangé, L’alimentation et ses récits"
    )


def test_parse_mariette_chapter_with_corrected_2017_year(tmp_path: Path) -> None:
    source = tmp_path / "mariette.docx"
    document = Document()
    document.add_paragraph("Chapitre d’ouvrage")
    document.add_paragraph(
        "« Mariette, texte de Sacha Guitry, musique d’Oscar Straus, l’histoire "
        "‘dans le genre de Joséphine’ », in Fedora Wesseler et Stefan Schmidl (éd.), "
        "Oscar Straus, Annäherungen an einen zu Unrecht Vergessenen, New Academic "
        "Essays on A Mostly Forgotten Composer, Amsterdam, "
        "http://operetta-research-center.org/oscar-straus-essays/, 2017, p.98-107."
    )
    document.save(source)

    items = parse_docx(source, default_author="Florence Fix")

    assert len(items) == 1
    assert items[0].title.startswith("Mariette, texte de Sacha Guitry")
    assert items[0].year == 2017
    assert items[0].pages == "98-107"
    assert items[0].book_title == (
        "Oscar Straus, Annäherungen an einen zu Unrecht Vergessenen, "
        "New Academic Essays on A Mostly Forgotten Composer"
    )


def test_extract_journal_title_from_article_citation() -> None:
    citation = (
        "« Le corps pétrifié », in Études Francophones, vol. 37, n°2, "
        "Représentations du corps, automne 2024, p.1-17."
    )
    assert extract_journal_title(citation) == "Études Francophones"


def test_extract_journal_title_after_issue_editor() -> None:
    citation = (
        "« Jeanne d’Arc », in Laurence Le Diagon-Jacquin (éd.), "
        "Le Paon d’Héra, N°8, Dijon, 2011, p.155-164."
    )
    assert extract_journal_title(citation) == "Le Paon d’Héra"


def test_extract_conference_title_city_and_country_without_inventing_date() -> None:
    citation = (
        "« Fragmentation », in Peter Schnyder (éd.), De l’écriture et des fragments. "
        "Fragmentation et sciences humaines, [actes du colloque à l’Université de "
        "Haute-Alsace, Mulhouse, 2014], Paris, Classiques Garnier, 2016, p.151-163."
    )
    metadata = extract_conference_metadata(citation)
    assert metadata["conference_title"] == (
        "De l’écriture et des fragments. Fragmentation et sciences humaines"
    )
    assert metadata["conference_city"] == "Mulhouse"
    assert metadata["conference_country"] == "France"
    assert metadata["conference_start_date"] is None
    assert metadata["conference_year_evidence"] == "2014"


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
    assert items[1].journal_title == "Revue test"
    assert items[1].url == "https://example.org/a"
    assert items[1].authors == ["Florence Fix"]


def test_leading_italic_span_is_used_as_complete_title(tmp_path: Path) -> None:
    source = tmp_path / "italic-title.docx"
    document = Document()
    document.add_paragraph("N°spécial de revue")
    paragraph = document.add_paragraph()
    title = "Growing Old in Nineteenth-Century France. Texts, Fictions, Representations"
    title_run = paragraph.add_run(title)
    title_run.italic = True
    paragraph.add_run(", numéro de L’Esprit créateur, Summer 2024, vol. 64, n°2, 132p.")
    document.save(source)

    items = parse_docx(source, default_author="Florence Fix")

    assert len(items) == 1
    assert items[0].title == title
    assert items[0].year == 2024
    assert items[0].pages == "132"


def test_nonitalic_space_inside_italic_title_is_preserved(tmp_path: Path) -> None:
    source = tmp_path / "century-title.docx"
    document = Document()
    document.add_paragraph("Ouvrages")
    paragraph = document.add_paragraph()
    first = paragraph.add_run("Femmes de spectacle au xixe")
    first.italic = True
    paragraph.add_run("\u00a0")
    century = paragraph.add_run("siècle")
    century.italic = True
    paragraph.add_run(", Paris, Exemple, 2022, 196p.")
    document.save(source)

    items = parse_docx(source, default_author="Florence Fix")

    assert items[0].title == "Femmes de spectacle au XIXe siècle"


def test_quoted_title_wins_over_later_italic_text(tmp_path: Path) -> None:
    source = tmp_path / "quoted-title.docx"
    document = Document()
    document.add_paragraph("Article dans revue")
    paragraph = document.add_paragraph()
    paragraph.add_run("« Mon article », in ")
    journal = paragraph.add_run("Revue test")
    journal.italic = True
    paragraph.add_run(", 2024, p.1-10.")
    document.save(source)

    items = parse_docx(source, default_author="Florence Fix")

    assert items[0].title == "Mon article"
    assert items[0].journal_title == "Revue test"


def test_url_only_paragraph_is_attached_to_previous_citation(tmp_path: Path) -> None:
    source = tmp_path / "continuation.docx"
    document = Document()
    document.add_paragraph("Communication dans un congrès")
    document.add_paragraph(
        "« Une communication », in Actes du colloque, Paris, 2025, p.19-31."
    )
    document.add_paragraph("https://example.org/book/99.")
    document.save(source)

    items = parse_docx(source, default_author="Florence Fix")

    assert len(items) == 1
    assert items[0].title == "Une communication"
    assert items[0].url == "https://example.org/book/99"
    assert "https://example.org/book/99" in items[0].raw_citation
