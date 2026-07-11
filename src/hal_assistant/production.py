from __future__ import annotations

import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .hal_xml import TEI_NS, validate_tei


@dataclass(frozen=True)
class ProductionBatch:
    output_dir: Path
    manifest_path: Path
    files: list[Path]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(root: ET.Element, path: str) -> str | None:
    node = root.find(path, {"tei": TEI_NS})
    if node is None or not node.text:
        return None
    return node.text.strip()


def _inspect(path: Path) -> dict[str, Any]:
    tree = ET.parse(path)
    root = tree.getroot()
    ns = {"tei": TEI_NS}
    authors: list[str] = []
    for author in root.findall(".//tei:analytic/tei:author", ns):
        forename = author.findtext(
            "tei:persName/tei:forename",
            default="",
            namespaces=ns,
        )
        surname = author.findtext(
            "tei:persName/tei:surname",
            default="",
            namespaces=ns,
        )
        parts = (forename, surname)
        full_name = " ".join(
            part.strip() for part in parts if part and part.strip()
        )
        if full_name:
            authors.append(full_name)

    typology = root.find(".//tei:classCode[@scheme='halTypology']", ns)
    return {
        "title": _text(root, ".//tei:analytic/tei:title"),
        "document_type": typology.get("n") if typology is not None else None,
        "publication_date": _text(
            root,
            ".//tei:imprint/tei:date[@type='datePub']",
        ),
        "authors": authors,
        "local_validation_errors": validate_tei(tree),
    }


def prepare_production_batch(
    xml_dir: str | Path,
    *,
    ledger_path: str | Path | None = None,
    output_dir: str | Path = "output/hal-production",
) -> ProductionBatch:
    """Freeze preproduction-validated XML notices into a checksummed production batch."""
    source_dir = Path(xml_dir)
    ledger = Path(ledger_path) if ledger_path else source_dir / "submission-ledger.json"
    if not ledger.exists():
        raise ValueError(f"Preproduction ledger not found: {ledger}")

    payload = json.loads(ledger.read_text(encoding="utf-8"))
    if payload.get("environment") != "preprod" or payload.get("test") is not True:
        raise ValueError("Ledger must come from a preproduction test submission")

    results = payload.get("results")
    if not isinstance(results, list) or not results:
        raise ValueError("Ledger contains no submission results")
    rejected = [item for item in results if not item.get("accepted")]
    if rejected:
        names = ", ".join(str(item.get("xml_file")) for item in rejected)
        raise ValueError(f"Ledger contains rejected notices: {names}")

    target = Path(output_dir)
    if target.exists() and any(target.iterdir()):
        raise ValueError(f"Production directory is not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)

    files: list[Path] = []
    records: list[dict[str, Any]] = []
    try:
        for item in results:
            filename = str(item.get("xml_file") or "")
            if not filename.endswith(".xml") or Path(filename).name != filename:
                raise ValueError(f"Invalid XML filename in ledger: {filename!r}")
            source = source_dir / filename
            if not source.exists():
                raise ValueError(f"Validated XML file is missing: {source}")
            inspection = _inspect(source)
            if inspection["local_validation_errors"]:
                raise ValueError(
                    f"Local validation now fails for {filename}: "
                    + "; ".join(inspection["local_validation_errors"])
                )
            destination = target / filename
            shutil.copy2(source, destination)
            files.append(destination)
            records.append(
                {
                    "xml_file": filename,
                    "sha256": _sha256(destination),
                    "size_bytes": destination.stat().st_size,
                    **inspection,
                    "preprod_status_code": item.get("status_code"),
                }
            )

        manifest = {
            "format": "hal-assistant-production-batch-v1",
            "created_at": datetime.now(UTC).isoformat(),
            "source_directory": str(source_dir),
            "preprod_ledger": str(ledger),
            "environment": "production",
            "test": False,
            "force_duplicate_by_title": False,
            "load_filter": payload.get("load_filter", "noaffiliation"),
            "file_count": len(records),
            "files": records,
        }
        manifest_path = target / "production-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise

    return ProductionBatch(target, manifest_path, files)
