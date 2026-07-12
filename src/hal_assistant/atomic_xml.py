from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .hal_xml import XMLBuildResult, _first, build_tei, validate_tei, write_tei


def _metadata_errors(record: dict[str, Any]) -> list[str]:
    document_type = str(_first(record, "docType", "document_type") or "")
    container = _first(record, "journalOrBookTitle", "container_title", "journal")
    if document_type == "COUV" and not container:
        return ["COUV requires container_title (the containing book title)"]
    return []


def build_xml_batch(
    source: str | Path,
    output_dir: str | Path,
    *,
    domain: str,
    domain_label: str | None = None,
    idhal: str | None = None,
    idhal_author: str | None = None,
    structure_id: str | None = None,
    limit: int | None = None,
) -> list[XMLBuildResult]:
    """Build XML while applying HAL document-type requirements per publication."""
    payload = json.loads(Path(source).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("HAL-ready source must be a JSON array")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    results: list[XMLBuildResult] = []
    selected = payload[:limit] if limit else payload

    for index, record in enumerate(selected, start=1):
        publication_id = str(record.get("publication_id") or f"record-{index:04d}")
        path = output / f"{publication_id}.xml"
        errors = _metadata_errors(record)
        if not errors:
            try:
                tree = build_tei(
                    record,
                    domain=domain,
                    domain_label=domain_label,
                    idhal=idhal,
                    idhal_author=idhal_author,
                    structure_id=structure_id,
                )
                errors = validate_tei(tree)
                if not errors:
                    write_tei(tree, path)
            except (TypeError, ValueError) as exc:
                errors = [str(exc)]
        results.append(XMLBuildResult(publication_id, path, errors))

    manifest = {
        "source": str(source),
        "domain": domain,
        "domain_label": domain_label,
        "idhal": idhal,
        "structure_id": structure_id or os.getenv("HAL_STRUCTURE_ID"),
        "count": len(results),
        "valid": sum(not item.errors for item in results),
        "blocked": sum(bool(item.errors) for item in results),
        "records": [
            {
                "publication_id": item.publication_id,
                "xml": item.path.name if not item.errors else None,
                "errors": item.errors,
            }
            for item in results
        ],
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return results
