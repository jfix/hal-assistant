# HAL Assistant agent guidance

These instructions apply to all work in this repository.

## Mission and priority

The primary goal is to manage Florence Fix's publication metadata safely and to
create or update HAL records without duplicates. Product and tooling work is
valuable only when it preserves that operational safety.

Priority order:

1. protect existing HAL records and the submission history;
2. preserve source evidence and human decisions;
3. process independent publications independently;
4. improve extraction, enrichment, review and submission ergonomics;
5. generalize the system only after the Florence Fix workflow remains correct.

## Non-negotiable safety rules

- Never create a new HAL record when an accepted or sufficiently matching HAL
  record already exists.
- Treat duplicate detection as a multi-field decision using title, year,
  authors, publication type, container, volume/issue, pages and identifiers.
  Title-only similarity is evidence, not a final decision.
- Never invent conference dates, publishers, places, editors, DOI, ISBN, ISSN,
  affiliations or other metadata.
- Preserve the original citation and field-level evidence for every derived or
  corrected value.
- An incomplete or rejected publication must not block other valid records.
- Production submission is allowed only after local validation and successful
  preproduction validation of the exact immutable XML payload.
- Before any network submission, show the exact target environment and action
  to the human reviewer. Production requires an explicit, separate confirmation.
- Preserve immutable ledgers, checksums, response diagnostics, HAL identifiers
  and resumability. Never silently overwrite or delete submission history.
- Record updates and new deposits are different operations. Make that distinction
  visible in data, UI, audit trails and confirmation screens.
- Do not store credentials, passwords, tokens, session cookies or temporary
  credential-file paths in the repository, database fixtures, logs or docs.

## Source and authority rules

- The reviewed publication dataset is authoritative for human-confirmed values.
- `raw_citation`/`original_citation` is immutable source evidence, not a field to
  rewrite after parsing.
- Keep every enrichment value tied to its source URL, source name, retrieval
  time, confidence and review state.
- Prefer authoritative sources: publisher pages, DOI registries, journal sites,
  institutional programmes, HAL, BnF/ISSN/ISBN catalogues and Fabula for events.
- Search-engine results may locate a source but are not themselves sufficient
  evidence for a metadata change.
- Partial dates may assist review but must not make a conference record ready.
  A one-day event confirmed by the author uses the same start and end date.
- French city and country names are used in HAL-facing metadata.

## Architecture and implementation

- Keep parsing, normalization, matching, readiness, XML generation and SWORD
  submission in reusable domain/application modules. Web routes and CLI commands
  should call the same services rather than duplicate business rules.
- Database migrations must be additive and reversible. Never discard evidence,
  review decisions, accepted HAL IDs or submission attempts.
- Use stable publication identifiers. Imports must be idempotent and produce a
  reviewable diff before applying changes.
- Treat the Google Sheet as an import/export and collaborative review surface;
  once migration is accepted, the database becomes the operational source of
  truth.
- External calls must have timeouts, bounded retries and cached source snapshots
  where licensing and privacy allow.
- Keep preproduction and production endpoints visibly and technically separate.

## Verification

For Python changes run:

```bash
uv run ruff check .
uv run pytest
```

Add regression fixtures for every parser or normalization bug. Submission code
must also test environment gates, duplicate protection, independent per-record
failure, ledger immutability and safe resume behavior.

For user-visible metadata changes, provide a before/after view containing the
original citation and supporting evidence before applying or submitting them.
