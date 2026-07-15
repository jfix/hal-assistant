# Production reconciliation — 2026-07-14

This document records the sanitized outcome of the Florence Fix HAL production run. Credentials, raw server bodies and ignored local artifacts are intentionally excluded.

## Inputs and safeguards

- Corrected source: `A mettre sur HAL-2.docx`
- Source SHA-256: `fc1ad0b67d34e6172a589674b9287cee6daa9d40b79fe0d0566e469ce1b7d176`
- Author IdHAL: `florence-fix`
- HAL domain: `shs.litt`
- Affiliation: structure `95026`, reused from the immutable ledger of four earlier successful deposits
- Parsed records: 122
- Production candidate batch: 64
- Batch SHA-256: `bd43e6cde31cbfc17f7bf7c1c7b57836ec9c62a6cf75a905b37061cf41450d01`

Before submission, the workflow excluded confirmed HAL records, ambiguous matches, conference papers without authoritative required metadata, five generic-title duplicate false positives, and three records found in an earlier local production ledger but not yet visible to the initial HAL candidate search.

## Validation and production result

- Local readiness audit: 64/64 ready
- Local XML validation: 64/64 valid
- HAL preproduction test validation: 64/64 accepted
- HAL production: 61 accepted, 3 rejected, 0 pending
- Corrected Mariette chapter: accepted as `hal-05691845` with publication year 2017

Each notice was processed independently. The three production rejections did not block the other 61 deposits.

## Follow-up production batch — 2026-07-15

Seven additional reviewed records were accepted in HAL production after metadata enrichment and individual duplicate resolution:

- `hal-05692218` — *Un château fond de scène d’un parc. Le garde-chasse de Chambord (1821)*
- `hal-05692220` — *Avant-propos au Pouvoir du médecin au XIXe siècle*
- `hal-05692221` — *La Seine sanglante : flots révolutionnaires et flux mémoriel*
- `hal-05692222` — *Les malades d’Antonio Alámo ou la maladie au pouvoir*
- `hal-05692223` — *Corps âgés et bouches inutiles : de quelques vieillards improductifs chez Zola et Mirbeau*
- `hal-05692224` — *Droit à la guerre et blessures désirées en temps de paix*
- `hal-05692226` — *Le pédant et l’exaltée, impressions littéraires*

This raises the confirmed production acceptances from the submission workflow from 61 to 68. The user-maintained review sheet records all seven as `accepted` and `READY`. The ignored local archive and immutable ledgers remain authoritative for payload checksums, server diagnostics and safe resume behavior.

## Quarantined production rejections

HAL's title-only duplicate protection rejected three distinct journal issues titled *Le Paon d'Héra* after other issues with the same top-level title had been accepted earlier in the batch:

- *Le Paon d'Héra* 1, *Orphée* (1), 2006
- *Le Paon d'Héra* 2, *Orphée* (2), 2007
- *Le Paon d'Héra* 6, *Médée* (2), 2010

They must not be retried with batch-wide duplicate forcing. A future retry requires an explicit per-record override after checking title, year, issue and pagination against HAL production.

## Remaining blocked work

- Five generic `Introduction` or `Préface` records require individual duplicate resolution.
- Eleven ambiguous HAL matches require manual resolution.
- Seventeen unmatched conference records require authoritative event metadata before XML generation.
- Conference dates must not be inferred from publication years or bare event years.

The ignored local archive and its ledgers remain the operational source of truth for checksums, response diagnostics, accepted HAL identifiers and safe resume behavior.
