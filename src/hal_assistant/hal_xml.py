from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TEI_NS = "http://www.tei-c.org/ns/1.0"
HAL_NS = "http://hal.archives-ouvertes.fr/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
XML_NS = "http://www.w3.org/XML/1998/namespace"
SCHEMA_URL = "http://api.archives-ouvertes.fr/documents/aofr-sword.xsd"
PACKAGING = "http://purl.org/net/sword-types/AOfr"

ET.register_namespace("", TEI_NS)
ET.register_namespace("hal", HAL_NS)
ET.register_namespace("xsi", XSI_NS)

FRENCH_CONFERENCE_CITIES = {
    "Granada": "Grenade",
    "Santa Maria, Azores": "Santa Maria, Açores",
    "Vienna": "Vienne",
}
FRENCH_COUNTRIES = {"Austria": "Autriche", "Spain": "Espagne"}


def _tag(name: str) -> str:
    return f"{{{TEI_NS}}}{name}"


def _text(parent: ET.Element, name: str, value: object | None, **attrs: str) -> ET.Element | None:
    if value in (None, "", []):
        return None
    node = ET.SubElement(parent, _tag(name), attrs)
    node.text = str(value)
    return node


def _split_author(name: str) -> tuple[str | None, str]:
    normalized = " ".join(name.split())
    if not normalized:
        return None, "Unknown"
    parts = normalized.split(" ")
    if len(parts) == 1:
        return None, parts[0]
    return " ".join(parts[:-1]), parts[-1]


def _authors(record: dict[str, Any]) -> list[str]:
    value = record.get("authors") or []
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def _first(record: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = record.get(name)
        if value not in (None, "", []):
            return value
    return None


def _identifier_values(value: Any) -> list[str]:
    if value in (None, "", []):
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]


def _structure_id(record: dict[str, Any], explicit: str | None) -> str | None:
    value = explicit or _first(record, "hal_structure_id", "structure_id")
    if value in (None, ""):
        value = os.getenv("HAL_STRUCTURE_ID")
    if value in (None, ""):
        return None
    normalized = str(value).removeprefix("struct-").removeprefix("#struct-")
    if not normalized.isdigit():
        raise ValueError("HAL structure ID must be numeric")
    return normalized


def build_tei(
    record: dict[str, Any],
    *,
    domain: str,
    domain_label: str | None = None,
    idhal: str | None = None,
    idhal_author: str | None = None,
    structure_id: str | None = None,
) -> ET.ElementTree:
    """Build a notice-only HAL AOfr TEI document from normalized review metadata."""
    title = _first(record, "title")
    document_type = _first(record, "docType", "document_type")
    year = _first(record, "producedDateY", "year")
    language = _first(record, "language") or "fr"
    authors = _authors(record)
    resolved_structure_id = _structure_id(record, structure_id)

    missing = [
        name
        for name, value in {
            "title": title,
            "document_type": document_type,
            "year": year,
            "authors": authors,
            "domain": domain,
        }.items()
        if value in (None, "", [])
    ]
    if missing:
        raise ValueError(f"Missing mandatory HAL metadata: {', '.join(missing)}")

    root = ET.Element(
        _tag("TEI"),
        {f"{{{XSI_NS}}}schemaLocation": f"{TEI_NS} {SCHEMA_URL}"},
    )
    text = ET.SubElement(root, _tag("text"))
    body = ET.SubElement(text, _tag("body"))
    list_bibl = ET.SubElement(body, _tag("listBibl"))
    bibl_full = ET.SubElement(list_bibl, _tag("biblFull"))
    ET.SubElement(bibl_full, _tag("titleStmt"))

    notes_stmt = ET.SubElement(bibl_full, _tag("notesStmt"))
    ET.SubElement(notes_stmt, _tag("note"), {"type": "audience", "n": "2"})
    ET.SubElement(notes_stmt, _tag("note"), {"type": "popular", "n": "0"})

    source_desc = ET.SubElement(bibl_full, _tag("sourceDesc"))
    bibl_struct = ET.SubElement(source_desc, _tag("biblStruct"))
    analytic = ET.SubElement(bibl_struct, _tag("analytic"))
    _text(analytic, "title", title, **{f"{{{XML_NS}}}lang": str(language)})

    for index, author_name in enumerate(authors):
        author = ET.SubElement(analytic, _tag("author"), {"role": "aut"})
        pers_name = ET.SubElement(author, _tag("persName"))
        forename, surname = _split_author(author_name)
        if forename:
            _text(pers_name, "forename", forename, type="first")
        _text(pers_name, "surname", surname)

        selected_author = idhal_author is None and index == 0
        if idhal_author is not None:
            selected_author = author_name.casefold() == idhal_author.casefold()
        if idhal and selected_author:
            _text(author, "idno", idhal, type="idhal")
        if resolved_structure_id and selected_author:
            ET.SubElement(author, _tag("affiliation"), {"ref": f"#struct-{resolved_structure_id}"})

    monogr = ET.SubElement(bibl_struct, _tag("monogr"))
    container = _first(record, "journalOrBookTitle", "container_title", "journal")
    if container:
        level = "m" if str(document_type) in {"OUV", "COUV"} else "j"
        _text(monogr, "title", container, level=level)
    elif str(document_type) == "OUV":
        _text(monogr, "title", title, level="m")

    if str(document_type) == "COMM":
        meeting = ET.SubElement(monogr, _tag("meeting"))
        _text(meeting, "title", _first(record, "conference_title", "conferenceTitle"))
        _text(
            meeting,
            "date",
            _first(record, "conference_start_date", "conferenceStartDate"),
            type="start",
        )
        _text(
            meeting,
            "date",
            _first(record, "conference_end_date", "conferenceEndDate"),
            type="end",
        )
        conference_city = _first(record, "conference_city", "city")
        if conference_city:
            conference_city = FRENCH_CONFERENCE_CITIES.get(
                str(conference_city), str(conference_city)
            )
        _text(meeting, "settlement", conference_city)
        country_code = _first(
            record,
            "conference_country_code",
            "conferenceCountryCode",
        )
        country_attributes = {"key": str(country_code).upper()} if country_code else {}
        conference_country = _first(record, "conference_country", "country")
        if conference_country:
            conference_country = FRENCH_COUNTRIES.get(
                str(conference_country), str(conference_country)
            )
        _text(
            meeting,
            "country",
            conference_country,
            **country_attributes,
        )

    for doi in _identifier_values(_first(record, "doi")):
        _text(bibl_struct, "idno", doi, type="doi")
    for isbn in _identifier_values(_first(record, "isbn")):
        _text(monogr, "idno", isbn, type="isbn")
    for issn in _identifier_values(_first(record, "issn")):
        _text(monogr, "idno", issn, type="issn")

    imprint = ET.SubElement(monogr, _tag("imprint"))
    _text(imprint, "publisher", _first(record, "publisher"))
    _text(imprint, "biblScope", _first(record, "volume"), unit="volume")
    _text(
        imprint,
        "biblScope",
        _first(record, "issueTitle", "issue_title"),
        unit="serie",
    )
    _text(imprint, "biblScope", _first(record, "issue"), unit="issue")
    _text(imprint, "biblScope", _first(record, "pages"), unit="pp")
    _text(imprint, "date", year, type="datePub")

    source_url = _first(record, "sourceUrl", "source_url")
    if source_url:
        _text(bibl_struct, "ref", source_url, type="seeAlso")

    profile_desc = ET.SubElement(bibl_full, _tag("profileDesc"))
    lang_usage = ET.SubElement(profile_desc, _tag("langUsage"))
    ET.SubElement(lang_usage, _tag("language"), {"ident": str(language)})
    text_class = ET.SubElement(profile_desc, _tag("textClass"))
    domain_node = ET.SubElement(text_class, _tag("classCode"), {"scheme": "halDomain", "n": domain})
    if domain_label:
        domain_node.text = domain_label
    typology = ET.SubElement(
        text_class,
        _tag("classCode"),
        {"scheme": "halTypology", "n": str(document_type)},
    )
    typology.text = str(document_type)

    return ET.ElementTree(root)


def validate_tei(tree: ET.ElementTree) -> list[str]:
    """Perform deterministic local structural checks before remote HAL validation."""
    root = tree.getroot()
    errors: list[str] = []
    ns = {"tei": TEI_NS}
    required_paths = {
        "title": ".//tei:analytic/tei:title",
        "author": ".//tei:analytic/tei:author",
        "publication date": ".//tei:imprint/tei:date[@type='datePub']",
        "language": ".//tei:langUsage/tei:language",
        "HAL domain": ".//tei:classCode[@scheme='halDomain']",
        "HAL typology": ".//tei:classCode[@scheme='halTypology']",
    }
    for label, path in required_paths.items():
        if root.find(path, ns) is None:
            errors.append(f"Missing {label}")

    typology = root.find(".//tei:classCode[@scheme='halTypology']", ns)
    if typology is not None and typology.attrib.get("n") == "COMM":
        meeting_paths = {
            "conference title": ".//tei:meeting/tei:title",
            "conference start date": ".//tei:meeting/tei:date[@type='start']",
            "conference end date": ".//tei:meeting/tei:date[@type='end']",
            "conference city": ".//tei:meeting/tei:settlement",
            "conference country": ".//tei:meeting/tei:country",
        }
        for label, path in meeting_paths.items():
            if root.find(path, ns) is None:
                errors.append(f"Missing {label}")
    return errors


def write_tei(tree: ET.ElementTree, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Register again at the serialization boundary. This prevents ElementTree
    # from emitting ns0-prefixed TEI when other code has changed its registry.
    ET.register_namespace("", TEI_NS)
    ET.register_namespace("hal", HAL_NS)
    ET.register_namespace("xsi", XSI_NS)
    ET.indent(tree, space="  ")
    tree.write(output, encoding="utf-8", xml_declaration=True)
    return output


@dataclass(frozen=True)
class XMLBuildResult:
    publication_id: str
    path: Path
    errors: list[str]


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
    payload = json.loads(Path(source).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("HAL-ready source must be a JSON array")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    results: list[XMLBuildResult] = []
    selected = payload[:limit] if limit else payload

    for index, record in enumerate(selected, start=1):
        publication_id = str(record.get("publication_id") or f"record-{index:04d}")
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
            path = output / f"{publication_id}.xml"
            if not errors:
                write_tei(tree, path)
        except (TypeError, ValueError) as exc:
            errors = [str(exc)]
            path = output / f"{publication_id}.xml"
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
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results


def select_representative_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select at most one record per HAL document type for a safe test batch."""
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        document_type = str(_first(record, "docType", "document_type") or "")
        if document_type and document_type not in seen:
            selected.append(record)
            seen.add(document_type)
        if len(selected) >= 5:
            break
    return selected
