# HAL Assistant

HAL Assistant turns academic publication lists into structured data that can be reviewed before creating or updating records in [HAL](https://hal.science/).

The current release parses French humanities CVs written in Word, searches HAL read-only, and enriches unmatched records through Crossref and OpenAlex. It does **not** upload or modify anything in HAL.

## Status

Version `0.3.0`. The workflow is intentionally conservative: every original citation is preserved in `raw_citation`, HAL searches are read-only, and enrichment is review data rather than an automatic overwrite.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)

## Run from the repository

```bash
uv sync --extra dev
uv run hal-assistant parse "A mettre sur HAL.docx" --author "Florence Fix"
```

Outputs are written to `output/`:

- `publications.json` for machine processing
- `publications.xlsx` for review and correction

## Match against HAL

Use an IdHAL whenever possible. This fetches the authoritative author publication set once and compares every bibliography entry locally:

```bash
uv run hal-assistant match-hal output/publications.json \
  --idhal florence-fix \
  --enrich
```

The `--enrich` option queries Crossref first and OpenAlex as a fallback for records not confidently found in HAL. The Excel report includes DOI, canonical title, journal, publisher, ISSN, ISBN, source, score, URL, and any error.

Without `--idhal`, the command falls back to title-and-year searches in HAL:

```bash
uv run hal-assistant match-hal output/publications.json
```

## Recognized sections

- Ouvrages
- Ouvrages en co-direction
- Numéros spéciaux de revue
- Chapitres d’ouvrage
- Notices d’encyclopédie ou de dictionnaire
- Communications dans un congrès
- Articles dans une revue

## Development

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest
```

## Roadmap

1. Improve citation parsing and validation from real CV samples.
2. Add IdHAL-aware HAL matching and metadata enrichment.
3. Produce reviewed HAL deposit packages.
4. Add opt-in API deposits with dry-run safeguards.

## License

MIT
