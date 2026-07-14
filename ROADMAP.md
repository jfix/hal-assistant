# HAL Assistant roadmap

This roadmap is ordered by dependency. A phase is complete only when its tests pass and the pull request is merged.

## Completed

- [x] Parse the source Word bibliography into structured publication records.
- [x] Add deterministic publication IDs and field-level metadata provenance.
- [x] Generate a conference-enrichment queue and review workbook.
- [x] Import accepted conference reviews safely by publication ID.
- [x] Add AOfr TEI XML generation, readiness auditing and immutable production batches.
- [x] Add atomic, resumable preproduction and production submission ledgers.
- [x] Complete the first gated production batch and preserve its reconciliation record.

## Phase 1 — Conference metadata research

- [x] Inventory all 26 `conference_paper` records from the source bibliography.
- [x] Separate confirmed existing records, ambiguous matches and records requiring a new deposit.
- [ ] Research exact event title, start/end date, city and country from authoritative sources.
- [ ] Record source URL, source name, confidence and ambiguity notes for every changed field.
- [ ] Never turn a publication year or a bare event year into an invented full date.
- [ ] Produce a completed review workbook and enriched publications JSON.
- [x] Run the readiness audit and leave unresolved records explicitly flagged.

## Phase 2 — HAL serialization

- [ ] Add COMM-specific TEI/XML serialization for conference title, dates, city and country.
- [ ] Add schema and regression tests for complete and incomplete COMM records.
- [ ] Verify that provenance/review-only fields are not leaked into HAL XML.

## Phase 3 — Preproduction validation

- [ ] Add credential-gated HAL preproduction/SWORD integration tests.
- [x] Submit a deliberately small test batch to preproduction only.
- [x] Capture response diagnostics and make retries idempotent.
- [x] Require an explicit approval gate before any production submission.

## Phase 4 — Duplicate reconciliation

- [x] Reconcile local production ledgers before preparing a new batch.
- [x] Exclude records already accepted in earlier production runs.
- [ ] Match by title, year, container, issue and pages before classifying a duplicate.
- [ ] Add a per-publication override for verified HAL title-only false positives.
- [ ] Revalidate and submit the three quarantined *Le Paon d'Héra* issues independently.
- [ ] Resolve the quarantined generic `Introduction` and `Préface` records independently.
- [ ] Resolve the remaining ambiguous HAL matches before generating submission XML.

## Phase 5 — Source corrections and release

- [x] Import the corrected Mariette citation when the revised DOCX is supplied.
- [x] Add a regression test for the corrected citation and year.
- [x] Refresh user documentation and examples for the gated submission workflow.
- [x] Record the sanitized 2026-07-14 production reconciliation.
- [ ] Bump the release version and publish release notes.
- [ ] Delete merged feature branches after all dependent PRs are complete.
