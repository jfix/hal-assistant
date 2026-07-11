# HAL Assistant

HAL Assistant turns academic publication lists into structured data that can be reviewed before creating or updating records in [HAL](https://hal.science/).

The current release parses French humanities CVs written in Word, searches HAL read-only, enriches unmatched records through Crossref and OpenAlex, and generates a credential-free deposit dry run. It does **not** upload or modify anything in HAL.

## Status

Version `0.5.0`. The workflow is intentionally conservative: every original citation is preserved in `raw_citation`, HAL searches are read-only, and enrichment is review data rather than an automatic overwrite.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)

## One-command dry run

Provide the DOCX, the author's HAL Id, and the default author name:

```bash
uv sync --extra dev
uv run hal-assistant run "A mettre sur HAL.docx" \
  --idhal florence-fix \
  --author "Florence Fix"
```

This runs the whole workflow automatically:

1. parse the DOCX;
2. match records against the author's HAL Id;
3. enrich unmatched records through Crossref and OpenAlex;
4. generate a credential-free HAL deposit plan.

Outputs are written under `output/`:

- `parsed/publications.json` and `parsed/publications.xlsx`;
- `hal-review/publications-with-hal.json` and `.xlsx`;
- `dry-run/deposit-plan.json` and `.xlsx`;
- `dry-run/packages/` with one JSON package per actionable publication.

Disable external enrichment with `--no-enrich`, or choose another destination with `--output-dir`.

## Individual commands

The individual stages remain available for debugging and advanced use:

```bash
uv run hal-assistant parse "A mettre sur HAL.docx" --author "Florence Fix"
uv run hal-assistant match-hal output/publications.json --idhal florence-fix --enrich
uv run hal-assistant prepare-deposits output/hal-review/publications-with-hal.json
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
2. Improve the one-command review experience and deposit package fidelity.
3. Add interactive approval of prepared deposit packages.
4. Add separately gated, opt-in API deposits.

## License

MIT
