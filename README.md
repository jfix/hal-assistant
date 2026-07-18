# HAL Assistant

HAL Assistant turns academic publication lists into structured data that can be reviewed before creating or updating records in [HAL](https://hal.science/).

The current release parses French humanities CVs written in Word, searches HAL read-only, audits HAL requirements, generates AOfr TEI XML, validates notices in HAL preproduction, and performs explicitly gated, resumable production submissions.

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

## Web application handover

The next product phase is documented in:

- [web application handover](docs/WEB_APP_HANDOFF.md);
- [proposed data model](docs/DATA_MODEL.md);
- [recommended architecture](docs/WEB_APP_ARCHITECTURE.md);
- [regression fixture plan](docs/TEST_FIXTURES.md);
- [new-task kickoff prompt](docs/NEW_CONVERSATION_KICKOFF.md).

Repository-wide safety and implementation rules are in [AGENTS.md](AGENTS.md).

## License

MIT
