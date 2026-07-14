# HAL Assistant

HAL Assistant turns academic publication lists into structured data that can be reviewed before creating or updating records in [HAL](https://hal.science/).

The current release parses French humanities CVs written in Word, searches HAL read-only, enriches unmatched records through Crossref, OpenAlex, and HAL authority referentials, and generates a credential-free deposit dry run. The default `run` command does **not** upload or modify anything in HAL; separately gated update and submission commands require explicit credentials and confirmation.

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
3. enrich unmatched records through Crossref and OpenAlex, then validate journal articles against HAL's journal referential and same-journal records;
4. generate a credential-free HAL deposit plan.

Outputs are written under `output/`:

- `parsed/publications.json` and `parsed/publications.xlsx`;
- `hal-review/publications-with-hal.json` and `.xlsx`;
- `dry-run/deposit-plan.json` and `.xlsx`;
- `dry-run/packages/` with one JSON package per actionable publication.

Disable external enrichment with `--no-enrich`, or choose another destination with `--output-dir`.

### Journal authority validation

For journal articles, enrichment now performs a conservative validation pass:

1. extract explicit issue numbers from the original citation without treating years or URLs as metadata;
2. resolve only `VALID` HAL journal authorities using journal title and ISSN evidence;
3. inspect existing records from the same HAL journal authority to infer issue-versus-volume conventions and recover issue themes;
4. retain the authority ID, canonical title, print/electronic ISSNs, publisher, issue metadata, evidence URLs, confidence score, and validation notes in the review output;
5. leave ambiguous or low-confidence authority matches for human review.

This stage enriches review data and deposit packages; it never updates an existing HAL record by itself.

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
