from pathlib import Path

from typer.testing import CliRunner

from hal_assistant.cli import app
from hal_assistant.models import HALMatch, HALMatchStatus, Publication, PublicationType

runner = CliRunner()


def test_run_command_processes_docx_end_to_end(tmp_path: Path, monkeypatch) -> None:
    document = tmp_path / "publications.docx"
    document.write_bytes(b"placeholder")
    output_dir = tmp_path / "output"

    publication = Publication(
        publication_type=PublicationType.JOURNAL_ARTICLE,
        section="Article dans revue",
        raw_citation="Mon article, Revue test, 2024.",
        title="Mon article",
        year=2024,
        authors=["Florence Fix"],
        source_paragraph=1,
    )

    def fake_parse_docx(path: Path, default_author: str | None = None):
        assert path == document
        assert default_author == "Florence Fix"
        return [publication]

    def fake_match_publications(publications, idhal: str | None = None):
        assert idhal == "florence-fix"
        publications[0].hal_match = HALMatch(status=HALMatchStatus.NOT_FOUND)
        return publications

    def fake_enrich_publications(publications):
        return publications

    monkeypatch.setattr("hal_assistant.cli.parse_docx", fake_parse_docx)
    monkeypatch.setattr("hal_assistant.cli.match_publications", fake_match_publications)
    monkeypatch.setattr("hal_assistant.cli.enrich_publications", fake_enrich_publications)

    result = runner.invoke(
        app,
        [
            "run",
            str(document),
            "--idhal",
            "florence-fix",
            "--author",
            "Florence Fix",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Parsed 1 publications" in result.output
    assert (output_dir / "parsed" / "publications.json").exists()
    assert (output_dir / "hal-review" / "publications-with-hal.json").exists()
    assert (output_dir / "dry-run" / "deposit-plan.json").exists()
    assert (output_dir / "dry-run" / "deposit-plan.xlsx").exists()
