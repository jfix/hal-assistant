# HAL Assistant

HAL Assistant turns academic publication lists into structured data that can be reviewed before creating or updating records in [HAL](https://hal.science/).

The first release focuses on French humanities CVs written in Word. It parses sectioned bibliographies and exports both JSON and an Excel review workbook. It does **not** upload anything to HAL yet.

## Status

Early development (`0.1.0`). The parser is intentionally conservative: it preserves every original citation in `raw_citation` so no source information is lost while parsing improves.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)

## Run from the repository

```bash
uv sync --extra dev
uv run hal-assistant parse "A mettre sur HAL.docx" --author "Florence Fix"
```

Outputs are written to `output/`:

- `publications.json` for machine processing
- `publications.xlsx` for review and correction

Choose a different output folder with `--output-dir`:

```bash
uv run hal-assistant parse cv.docx --author "Florence Fix" --output-dir review
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
2. Enrich records through Crossref and OpenAlex.
3. Search HAL and detect likely duplicates.
4. Produce reviewed HAL deposit packages.
5. Add opt-in API deposits with dry-run safeguards.

## License

MIT
