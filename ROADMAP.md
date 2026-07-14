# HAL Assistant roadmap

This roadmap is ordered by dependency. A phase is complete only when its tests pass and the pull request is merged.

## Completed

- [x] Parse the source Word bibliography into structured publication records.
- [x] Add deterministic publication IDs and field-level metadata provenance.
- [x] Generate a conference-enrichment queue and review workbook.
- [x] Import accepted conference reviews safely by publication ID.

## Phase 1 — Conference metadata research

- [ ] Inventory all 26 `conference_paper` records from the source bibliography.
- [ ] Separate records already present in HAL from records requiring a new deposit.
- [ ] Research exact event title, start/end date, city and country from authoritative sources.
- [ ] Record source URL, source name, confidence and ambiguity notes for every changed field.
- [ ] Never turn a publication year or a bare event year into an invented full date.
- [ ] Produce a completed review workbook and enriched publications JSON.
- [ ] Run the readiness audit and leave unresolved records explicitly flagged.

## Phase 2 — HAL serialization

- [ ] Add COMM-specific TEI/XML serialization for conference title, dates, city and country.
- [ ] Add schema and regression tests for complete and incomplete COMM records.
- [ ] Verify that provenance/review-only fields are not leaked into HAL XML.

## Phase 3 — Preproduction validation

- [ ] Add credential-gated HAL preproduction/SWORD integration tests.
- [ ] Submit a deliberately small test batch to preproduction only.
- [ ] Capture response diagnostics and make retries idempotent.
- [ ] Require an explicit approval gate before any production submission.

## Phase 4 — Source corrections and release

- [x] Import the corrected Mariette citation when the revised DOCX is supplied.
- [x] Add a regression test for the corrected citation and year.
- [ ] Refresh user documentation and examples.
- [ ] Bump the release version and publish release notes.
- [ ] Delete merged feature branches after all dependent PRs are complete.
