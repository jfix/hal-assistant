# Approved-review production reconciliation — 2026-07-15

This document records the sanitized outcome of the 24-record Florence Fix review batch. Credentials, SWORD response bodies, and ignored local artifacts are intentionally excluded.

## Inputs and safeguards

- Authoritative source: the shared Google Sheet after Florence’s explicit review decisions
- Workbook SHA-256: `b16599a8decd4190339e060678821d8168bf7765411d66541e73e3d2cd671c66`
- Author IdHAL: `florence-fix`
- HAL domain: `shs.litt`
- Review import: 24 approved, 98 already on HAL, 0 deferred, 0 blocked
- Local readiness: 24/24 ready
- Final XML generation: 24 valid, 0 blocked
- Full-account pre-submission duplicate audit: 0 exact title/year or DOI duplicates
- HAL preproduction validation of final checksums: 24/24 accepted
- Production submission: 24/24 accepted, 0 rejected
- Post-submission reconciliation: every reviewed title resolves to exactly one expected HAL identifier

The batch was submitted in tranches of at most five. Each tranche was reconciled from HAL’s public API before the next tranche began.

## Corrected serialization gate

The first five-record preproduction test isolated four schema failures caused by monograph identifiers appearing after the title. The serializer was corrected to:

- place HAL journal authorities, ISBNs, ISSNs, and eISSNs before the monograph title;
- preserve volume editors as AOfr `monogr/editor` elements;
- preserve publisher cities as AOfr `imprint/pubPlace`;
- keep thematic issue titles and numeric issue fields separate.

The four corrected records then passed 4/4, and the complete regenerated batch passed 24/24. No rejected XML reached production.

## Accepted HAL identifiers

- `hal-05694244` — *Avant-propos : après Kleist, rivalités et artifices*
- `hal-05694245` — *Introduction à Fleuves et flux : approches écocritiques et géocritiques*
- `hal-05694246` — *Avant-propos à Fêtes de fin*
- `hal-05694247` — *Préface à Corneille de circonstance. L’auteur, personnage de théâtre*
- `hal-05694248` — *Petites scènes et grands hommes*
- `hal-05694251` — *Avant-propos à Héloïse et Abélard au XIXe siècle*
- `hal-05694252` — *Octave Mirbeau et la tentation du rien : rire dans le désert*
- `hal-05694253` — *L’Atlantique des prisonniers : récits rétrospectifs des Communards en route vers la Nouvelle-Calédonie*
- `hal-05694254` — *Outrance de soi et démesure de l’Histoire de France chez Sacha Guitry*
- `hal-05694255` — *Alfred Capus, l’aventurier de la morale*
- `hal-05694257` — *Bougresses et vierges rouges : représentations des femmes de la Commune de Paris*
- `hal-05694258` — *Légèreté de la représentation : le député en scène*
- `hal-05694259` — *Introduction à Dissimuler pour mieux régner*
- `hal-05694260` — *Sacha Guitry, auteur de lui-même. Une auctorialité de faiseur*
- `hal-05694261` — *Avant-propos à Jouer Marilyn*
- `hal-05694263` — *Avant-propos à Tous malades. Représentations du corps souffrant*
- `hal-05694264` — *Introduction au Mélodramatique*
- `hal-05694265` — *Avant-propos à Théâtre et science*
- `hal-05694266` — *Garde-barrière : réalités et représentations*
- `hal-05694267` — *Avant-propos au Détour du comparant*
- `hal-05694269` — *Exotique et domestique : l’éléphant asiatique sur les scènes à grand spectacle du XIXe siècle français*
- `hal-05694270` — *Introduction: Growing Old in Nineteenth-Century France: Texts, Fictions, and Representations*
- `hal-05694271` — *La science pour rire : mérite de l’inventeur chez Becque*
- `hal-05694272` — *Détours d’un comparant : le gaz au XIXe siècle*

Florence confirmed that Yohann Deguin is coauthor of the preface recorded as `hal-05694247`; HAL’s public index shows both Florence Fix and Yohann Deguin as authors and scientific editors.

The ignored local production archive and cumulative ledger remain the operational source of truth for payload checksums, assigned identifiers, diagnostics, and idempotent resume behavior. The authoritative Google Sheet was updated and read back successfully for all 24 accepted records.
