# Paon d’Héra production reconciliation — 2026-07-15

This document records the sanitized outcome of the Florence Fix *Paon d’Héra* correction run. Credentials, SWORD response bodies, and ignored local artifacts are intentionally excluded.

## Safeguards

- The authoritative review workbook was exported from the shared Google Sheet and checksummed.
- Existing notices were addressed by exact HAL identifiers and exact versioned SWORD `PUT` endpoints.
- Every existing-record payload passed a checksum-matched production `X-test` before execution.
- The three new notices passed local readiness and XML validation, a full-account duplicate audit, and HAL preproduction `X-test` validation.
- Production inputs were frozen in an immutable archive with a checksum manifest.
- Every record was processed independently so that a failure could not block the remaining records.

## Existing-record corrections

Ten existing issue notices were accepted by HAL and reconciled from the public API:

- `hal-05691824`: issue 2, *Orphée (2)*, 226 pages
- `hal-05691820`: issue 4, *Saint François d’Assise*, 282 pages
- `hal-05691791`: issue 5, *Médée (1)*, 261 pages
- `hal-05691789`: issue 7, *Don Juan*, 360 pages
- `hal-05691803`: issue 8, *Jeanne d’Arc*, 300 pages
- `hal-05691812`: issue 9, *Ulysse (1)*, 318 pages
- `hal-05691846`: issue 10, *Ulysse (2)*, 306 pages
- `hal-05691825`: issue 11, *Le roi Lear*, 195 pages
- `hal-05691830`: issue 12, *Tristan et Isolde*, 273 pages
- `hal-05691808`: issue 13, *Mythologies du fil*, 346 pages

All ten now resolve as HAL `ISSUE` records using journal authority `63383`, ISSN `1779-2746`, the canonical journal title, a numeric issue field, and the thematic issue title as the AOfr `serie` field.

## New notices

Three notices absent from Florence Fix’s HAL corpus were accepted in production and reconciled from the public API:

- `hal-05694220`: issue 1, *Orphée (1)*, 2006, 134 pages
- `hal-05694219`: issue 3, *Roméo et Juliette*, 2007, 275 pages
- `hal-05694221`: issue 6, *Médée (2)*, 2010, 219 pages

The assigned identifiers and accepted states were written back to the authoritative Google Sheet. The ignored local ledgers and production archive remain the operational source of truth for checksums, diagnostics, and idempotent reconciliation.
