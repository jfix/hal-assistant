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
- [x] Reconcile seven follow-up production acceptances, bringing workflow-created acceptances to 68.

## Phase 1 — Conference metadata research

- [x] Inventory all 26 source records initially classified as `conference_paper`.
- [x] Reclassify proceedings chapters and prefatory material when authoritative publication evidence requires `COUV` rather than `COMM`.
- [x] Separate confirmed existing records, false-positive matches and records requiring a new deposit.
- [x] Research exact event title, start/end date, city and country for every remaining `COMM` record.
- [x] Record source URL, source name, confidence and ambiguity notes for every changed field.
- [x] Never turn a publication year or a bare event year into an invented full date.
- [x] Produce a completed review workbook and enriched publication data.
- [x] Run the readiness audit and leave unresolved records explicitly flagged.

## Phase 2 — HAL serialization

- [x] Add COMM-specific TEI/XML serialization for conference title, dates, city and country.
- [x] Add schema and regression tests for complete and incomplete COMM records.
- [x] Verify that provenance/review-only fields are not leaked into HAL XML.

## Phase 3 — Preproduction validation

- [ ] Add credential-gated HAL preproduction/SWORD integration tests.
- [x] Submit a deliberately small test batch to preproduction only.
- [x] Capture response diagnostics and make retries idempotent.
- [x] Require an explicit approval gate before any production submission.
- [ ] Regenerate and preproduction-test the current 24-record READY queue from the latest review workbook.

## Phase 4 — Duplicate reconciliation and submission

- [x] Reconcile local production ledgers before preparing a new batch.
- [x] Exclude records already accepted in earlier production runs.
- [x] Match by title, year, container, issue and pages before classifying a duplicate.
- [x] Add a per-publication override for verified HAL title-only false positives.
- [x] Resolve metadata and false-positive matches for the generic `Introduction`, `Avant-propos` and `Préface` records.
- [x] Resolve all other ambiguous HAL matches against the full live IdHAL corpus.
- [ ] Submit the 24 currently READY, unsubmitted records after successful preproduction validation.
- [ ] Regenerate and preproduction-test *Le Paon d'Héra* issues 1 and 6 with journal authority 63383 and ISSN 1779-2746, then retry each independently if the production X-test still reports only a title-level false positive.
- [ ] Reconcile the identity conflict between *Le Paon d'Héra* issues 2 and 3 and live record `hal-05691824`; do not submit, remap or update either issue until the 226/275-page discrepancy is resolved.

## Phase 5 — Source corrections and release

- [x] Import the corrected Mariette citation when the revised DOCX is supplied.
- [x] Add a regression test for the corrected citation and year.
- [x] Refresh user documentation and examples for the gated submission workflow.
- [x] Record the sanitized 2026-07-14 production reconciliation.
- [ ] Bump the release version and publish release notes after the current READY queue is processed.
- [ ] Delete merged feature branches after all dependent PRs are complete.
