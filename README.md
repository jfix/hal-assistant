# HAL Assistant

HAL Assistant turns academic publication lists into structured data that can be reviewed before creating or updating records in [HAL](https://hal.science/).

The current release parses French humanities CVs written in Word, searches HAL read-only, enriches unmatched records through Crossref, OpenAlex, and HAL authority referentials, audits HAL requirements, generates AOfr TEI XML, validates notices in HAL preproduction, and performs explicitly gated, resumable production submissions. The default `run` command does **not** upload or modify anything in HAL; separately gated update and submission commands require explicit credentials and confirmation.

## Status

Version `0.12.0`. The workflow is intentionally conservative: every original citation is preserved in `raw_citation`, ambiguous matches remain blocked for review, one rejected publication does not block the batch, and production writes require both a command-line gate and a separate confirmation environment variable.

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

The reviewed submission stages are separate on purpose:

```bash
uv run hal-audit output/reviewed-publications.json --show-records
uv run hal-build-xml output/reviewed-publications.json \
  --domain shs.litt \
  --idhal florence-fix \
  --idhal-author "Florence Fix"
uv run hal-submit output/hal-xml --environment preprod --test --limit 3
uv run hal-prepare-production output/hal-xml
```

Do not treat a successful preproduction test as production authorization. Production also requires `--no-test`, `--execute`, and `HAL_SWORD_CONFIRM_PRODUCTION=SUBMIT_TO_HAL`. Preserve the generated ledgers and production archive because they are the authoritative idempotency and duplicate-safety record.

### Verified title-only duplicate false positives

HAL can reject distinct records that share a short top-level title. Retry such a record only after checking its title, year, container, issue, and pages against HAL production. The override accepts one exact XML basename and first requires a successful checksum-matched X-test against the production endpoint:

```bash
uv run hal-submit output/hal-archive/BATCH_ID \
  --environment production \
  --test \
  --resume \
  --force-title-duplicate pub-0017.xml
```

For the real write, confirm both production submission and that same exact filename:

```bash
export HAL_SWORD_CONFIRM_PRODUCTION=SUBMIT_TO_HAL
export HAL_SWORD_CONFIRM_TITLE_DUPLICATE=pub-0017.xml
uv run hal-submit output/hal-archive/BATCH_ID \
  --environment production \
  --no-test \
  --execute \
  --resume \
  --force-title-duplicate pub-0017.xml
```

The tool refuses paths, wildcards, multi-record forcing, a changed XML checksum, and a production write without the matching forced production X-test. Process each verified false positive independently.

See [the 2026-07-14 production reconciliation](docs/production-run-2026-07-14.md) for the latest sanitized operational result.

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

See [ROADMAP.md](ROADMAP.md). The current priorities are authoritative conference metadata research, per-record handling of HAL title-only duplicate false positives, and release documentation.

## License

MIT
