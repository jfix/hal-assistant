from __future__ import annotations

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

REQUIRED_COLUMNS = {
    "publication_id",
    "decision",
    "publication_type",
    "title",
    "year",
    "authors",
}
CENTURY_RE = re.compile(
    r"\b([ivxlcdm]+)e(?=(?:\s+siècles?\b|\s*[-–—]\s*[ivxlcdm]+e\s+siècles?\b))",
    re.IGNORECASE,
)
LE_PAON_RE = re.compile(
    r"Le Paon d[’']Héra\s+(\d+)(?:\s*,.*)?$",
    re.IGNORECASE,
)
LE_PAON_HAL_JOURNAL_ID = "63383"
LE_PAON_CANONICAL_TITLE = (
    "Le Paon d'Héra : gazette interdisciplinaire thématique internationale = "
    "Hera's Peacock: an international thematic interdisciplinary journal"
)


@dataclass(frozen=True)
class ReviewImportResult:
    approved_path: Path
    report_path: Path
    approved_count: int
    already_on_hal_count: int
    blocked_count: int
    warning_count: int
    deferred_count: int = 0


def _column_number(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    value = 0
    for letter in letters:
        value = value * 26 + ord(letter.upper()) - ord("A") + 1
    return value


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [
        "".join(node.text or "" for node in item.iter(f"{{{SHEET_NS}}}t"))
        for item in root.findall(f"{{{SHEET_NS}}}si")
    ]


def _sheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in relationships.findall(f"{{{PKG_REL_NS}}}Relationship")
    }
    for sheet in workbook.findall(f".//{{{SHEET_NS}}}sheet"):
        if sheet.attrib.get("name") == sheet_name:
            target = targets[sheet.attrib[f"{{{REL_NS}}}id"]]
            normalized = target.lstrip("/")
            return normalized if normalized.startswith("xl/") else f"xl/{normalized}"
    raise ValueError(f"Workbook has no sheet named {sheet_name!r}")


def _cell_value(cell: ET.Element, shared: list[str]) -> Any:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{{{SHEET_NS}}}t"))
    value = cell.find(f"{{{SHEET_NS}}}v")
    if value is None or value.text is None:
        return None
    raw = value.text
    if cell_type == "s":
        return shared[int(raw)]
    if cell_type == "b":
        return raw == "1"
    if cell_type in {"str", "e"}:
        return raw
    try:
        number = float(raw)
        return int(number) if number.is_integer() else number
    except ValueError:
        return raw


def read_publications_sheet(path: str | Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(Path(path)) as archive:
        shared = _shared_strings(archive)
        worksheet = ET.fromstring(archive.read(_sheet_path(archive, "Publications")))

    matrix: list[list[Any]] = []
    for row in worksheet.findall(f".//{{{SHEET_NS}}}row"):
        cells: dict[int, Any] = {}
        for cell in row.findall(f"{{{SHEET_NS}}}c"):
            cells[_column_number(cell.attrib.get("r", "A1"))] = _cell_value(cell, shared)
        width = max(cells, default=0)
        matrix.append([cells.get(index) for index in range(1, width + 1)])

    if not matrix:
        raise ValueError("The Publications sheet is empty")
    headers = [str(value or "").strip() for value in matrix[0]]
    missing = REQUIRED_COLUMNS.difference(headers)
    if missing:
        raise ValueError("Missing required workbook columns: " + ", ".join(sorted(missing)))

    records: list[dict[str, Any]] = []
    for row in matrix[1:]:
        padded = row + [None] * (len(headers) - len(row))
        record = dict(zip(headers, padded, strict=False))
        if any(value not in (None, "") for value in record.values()):
            records.append(record)
    return records


def _normalize_centuries(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    normalized = " ".join(value.replace("\u00a0", " ").split())
    return CENTURY_RE.sub(lambda match: f"{match.group(1).upper()}e", normalized)


def _structure_le_paon(record: dict[str, Any]) -> bool:
    match = LE_PAON_RE.fullmatch(str(record.get("title") or "").strip())
    if not match:
        return False
    citation = str(record.get("original_citation") or "")
    thematic = re.search(
        r"Le Paon d[’']Héra\s+\d+\s*,\s*(.+?)\s*,\s*(?:19|20)\d{2}\b",
        citation,
        re.IGNORECASE,
    )
    record["journal_title"] = record.get("journal_title") or LE_PAON_CANONICAL_TITLE
    record["container_title"] = record["journal_title"]
    record["journal_id"] = LE_PAON_HAL_JOURNAL_ID
    record["journal_status"] = "VALID"
    record["issue"] = match.group(1)
    # HAL/AOfr models the thematic volume label separately from the numeric
    # issue. The XML serializer reads ``issue_title`` as biblScope/serie.
    record["issue_title"] = thematic.group(1).strip() if thematic else None
    return True


def _production_acceptance(record: dict[str, Any]) -> bool:
    status = str(record.get("production_status") or "").strip().lower()
    hal_id = str(record.get("production_hal_id") or "").strip()
    return status == "accepted" or bool(hal_id)


def import_review_workbook(
    source: str | Path,
    output_dir: str | Path,
    approval_ids: set[str] | None = None,
) -> ReviewImportResult:
    records = read_publications_sheet(source)
    exact_approval_ids = set(approval_ids) if approval_ids is not None else None
    approved: list[dict[str, Any]] = []
    report_rows: list[dict[str, Any]] = []
    already_on_hal = blocked = warning_count = deferred = 0
    seen_ids: set[str] = set()

    for record in records:
        publication_id = str(record.get("publication_id") or "").strip()
        workbook_decision = str(record.get("decision") or "").strip()
        effective_decision = workbook_decision
        errors: list[str] = []
        warnings: list[str] = []
        transformations: list[str] = []
        row_status = "valid"

        if not publication_id:
            errors.append("Missing publication_id")
        elif publication_id in seen_ids:
            errors.append("Duplicate publication_id")
        else:
            seen_ids.add(publication_id)

        accepted_in_production = _production_acceptance(record)
        explicitly_selected = (
            exact_approval_ids is not None and publication_id in exact_approval_ids
        )

        if accepted_in_production:
            effective_decision = "already_on_hal"
            already_on_hal += 1
            if explicitly_selected:
                errors.append(
                    "Approval allowlist includes a record already accepted in production"
                )
            elif workbook_decision == "approve":
                warnings.append(
                    "Workbook still says approve, but production acceptance excludes this record"
                )
                transformations.append("Excluded accepted production record")
        elif exact_approval_ids is not None:
            if explicitly_selected:
                effective_decision = "approve"
                transformations.append("Approved by exact publication-ID allowlist")
            else:
                effective_decision = "defer"
                row_status = "deferred"
                deferred += 1
        elif workbook_decision == "already_on_hal":
            already_on_hal += 1
        elif workbook_decision != "approve":
            errors.append(
                f"Unsupported or incomplete decision: {workbook_decision or '<blank>'}"
            )

        if effective_decision == "approve" and not accepted_in_production:
            normalized = dict(record)
            normalized["decision"] = "approve"
            original_title = normalized.get("title")
            normalized["title"] = _normalize_centuries(original_title)
            if normalized["title"] != original_title:
                transformations.append("Normalized French century typography")
            for field in ("publication_type", "title", "year", "authors"):
                if normalized.get(field) in (None, ""):
                    errors.append(f"Missing required field: {field}")
            try:
                normalized["year"] = int(normalized["year"])
            except (TypeError, ValueError):
                errors.append("Year is not an integer")
            if _structure_le_paon(normalized):
                transformations.append("Structured Le Paon d’Héra issue metadata")
            if normalized.get("hal_match_status") == "review":
                warnings.append("Possible HAL overlap approved as distinct")
            if not errors:
                approved.append(normalized)

        if errors:
            blocked += 1
            row_status = "blocked"
        if warnings:
            warning_count += 1
        report_rows.append(
            {
                "publication_id": publication_id,
                "decision": workbook_decision,
                "effective_decision": effective_decision,
                "status": row_status,
                "errors": errors,
                "warnings": warnings,
                "transformations": transformations,
            }
        )

    if exact_approval_ids is not None:
        unknown_ids = exact_approval_ids.difference(seen_ids)
        if unknown_ids:
            raise ValueError(
                "Approval allowlist contains unknown publication IDs: "
                + ", ".join(sorted(unknown_ids))
            )

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    approved_path = output / "hal-ready.json"
    report_path = output / "review-import-report.json"
    approved_path.write_text(json.dumps(approved, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(
        json.dumps(
            {
                "source": str(source),
                "total_rows": len(records),
                "approved": len(approved),
                "already_on_hal": already_on_hal,
                "deferred": deferred,
                "blocked": blocked,
                "records_with_warnings": warning_count,
                "approval_allowlist": (
                    sorted(exact_approval_ids) if exact_approval_ids is not None else None
                ),
                "rows": report_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return ReviewImportResult(
        approved_path,
        report_path,
        len(approved),
        already_on_hal,
        blocked,
        warning_count,
        deferred,
    )
