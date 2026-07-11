from pathlib import Path

from hal_assistant.hal_xml import build_tei, write_tei


def test_aofr_uses_default_tei_namespace_and_existing_structure(tmp_path: Path) -> None:
    tree = build_tei(
        {
            "publication_id": "pub-0001",
            "document_type": "OUV",
            "title": "Barbe-Bleue",
            "year": 2014,
            "authors": "Florence Fix",
            "pages": "230",
            "language": "fr",
        },
        domain="shs.litt",
        domain_label="Littératures",
        idhal_author="Florence Fix",
        structure_id="95026",
    )

    path = write_tei(tree, tmp_path / "pub-0001.xml")
    xml = path.read_text(encoding="utf-8")

    assert '<TEI xmlns="http://www.tei-c.org/ns/1.0"' in xml
    assert "ns0:" not in xml
    assert '<affiliation ref="#struct-95026"' in xml
    assert '<note type="audience" n="2"' in xml
    assert '<note type="popular" n="0"' in xml
    assert '<title level="m">Barbe-Bleue</title>' in xml
    assert '<date type="datePub">2014</date>' in xml
