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
        forename = author.findtext("tei:persName/tei:forename", default="", namespaces=ns)
        surname = author.findtext("tei:persName/tei:surname", default="", namespaces=ns)
        full_name = " ".join(part.strip() for part in (forename, surname) if part.strip())
        if full_name:
            authors.append(full_name)

    typology = root.find(".//tei:classCode[@scheme='halTypology']", ns)
    return {
        "title": _text(root, ".//tei:analytic/tei:title"),
        "document_type": typology.get("n") if typology is not None else None,
        "publication_date": _text(root, ".//tei:imprint/tei:date[@type='datePub']"),
        "authors": authors,
        "local_validation_errors": validate_tei(tree),
    }


def _default_ledger(source_dir: Path) -> Path:
    preferred = source_dir / "submission-ledger-preprod-test.json"
    legacy = source_dir / "submission-ledger.json"
    return preferred if preferred.exists() else legacy


def _write_index(archive_root: Path, entry: dict[str, Any]) -> None:
    index_path = archive_root / "index.json"
    payload = {"format": "hal-assistant-archive-index-v1", "batches": []}
    if index_path.exists():
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    batches = payload.setdefault("batches", [])
    if any(item.get("batch_id") == entry["batch_id"] for item in batches):
        raise ValueError(f"Batch already indexed: {entry['batch_id']}")
    batches.append(entry)
    index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_production_batch(
    xml_dir: str | Path,
    *,
    ledger_path: str | Path | None = None,
    output_dir: str | Path = "output/hal-archive",
) -> ProductionBatch:
    """Freeze accepted preproduction notices into a unique immutable archive batch."""
    source_dir = Path(xml_dir)
    ledger = Path(ledger_path) if ledger_path else _default_ledger(source_dir)
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

    source_records: list[tuple[Path, dict[str, Any], str]] = []
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
        source_records.append((source, inspection, _sha256(source)))

    batch_digest = hashlib.sha256(
        "\n".join(f"{path.name}:{digest}" for path, _, digest in source_records).encode()
    ).hexdigest()
    created = datetime.now(UTC)
    batch_id = f"{created.strftime('%Y-%m-%dT%H%M%SZ')}-{batch_digest[:8]}"
    archive_root = Path(output_dir)
    target = archive_root / batch_id
    if target.exists():
        raise ValueError(f"Archive batch already exists: {target}")
    target.mkdir(parents=True, exist_ok=False)

    files: list[Path] = []
    records: list[dict[str, Any]] = []
    try:
        for source, inspection, digest in source_records:
            destination = target / source.name
            shutil.copy2(source, destination)
            files.append(destination)
            result = next(item for item in results if item.get("xml_file") == source.name)
            records.append(
                {
                    "xml_file": source.name,
                    "sha256": digest,
                    "size_bytes": destination.stat().st_size,
                    **inspection,
                    "preprod_status_code": result.get("status_code"),
                }
            )

        shutil.copy2(ledger, target / "submission-ledger-preprod-test.json")
        manifest = {
            "format": "hal-assistant-production-batch-v2",
            "batch_id": batch_id,
            "batch_sha256": batch_digest,
            "created_at": created.isoformat(),
            "status": "production-ready",
            "source_directory": str(source_dir),
            "environment": "production",
            "test": False,
            "force_duplicate_by_title": False,
            "load_filter": payload.get("load_filter", "noaffiliation"),
            "file_count": len(records),
            "files": records,
        }
        manifest_path = target / "production-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _write_index(
            archive_root,
            {
                "batch_id": batch_id,
                "created_at": manifest["created_at"],
                "status": manifest["status"],
                "file_count": len(records),
                "directory": str(target),
                "batch_sha256": batch_digest,
            },
        )
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise

    return ProductionBatch(target, manifest_path, files)
