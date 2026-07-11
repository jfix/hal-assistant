from __future__ import annotations

import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Annotated, Any

import typer

from .hal_xml import PACKAGING, TEI_NS, validate_tei
from .sword import PREPROD_URL, SWORDResult, submit_notice

app = typer.Typer(no_args_is_help=True, help="Diagnose one HAL AOfr notice safely.")
ATOM_NS = "http://www.w3.org/2005/Atom"
SWORD_NS = "http://purl.org/net/sword/error/"


def _tag(name: str) -> str:
    return f"{{{TEI_NS}}}{name}"


def _text(node: ET.Element | None) -> str | None:
    if node is None or node.text is None:
        return None
    value = node.text.strip()
    return value or None


def inspect_xml(path: Path) -> dict[str, Any]:
    tree = ET.parse(path)
    root = tree.getroot()
    authors: list[dict[str, Any]] = []
    for author in root.findall(f".//{_tag('analytic')}/{_tag('author')}"):
        authors.append(
            {
                "forename": _text(author.find(f"{_tag('persName')}/{_tag('forename')}")),
                "surname": _text(author.find(f"{_tag('persName')}/{_tag('surname')}")),
                "idhal": _text(author.find(f"{_tag('idno')}[@type='idhal']")),
                "affiliations": [
                    node.attrib.get("ref") for node in author.findall(_tag("affiliation"))
                ],
            }
        )
    return {
        "root": root.tag,
        "local_validation_errors": validate_tei(tree),
        "title": _text(root.find(f".//{_tag('analytic')}/{_tag('title')}")),
        "document_type": root.find(
            f".//{_tag('classCode')}[@scheme='halTypology']"
        ).attrib.get("n")
        if root.find(f".//{_tag('classCode')}[@scheme='halTypology']") is not None
        else None,
        "publication_date": _text(
            root.find(f".//{_tag('imprint')}/{_tag('date')}[@type='datePub']")
        ),
        "authors": authors,
        "structure_ids": [
            node.attrib.get("{http://www.w3.org/XML/1998/namespace}id")
            for node in root.findall(f".//{_tag('listOrg')}/{_tag('org')}")
        ],
    }


def parse_hal_error(body: str | None) -> dict[str, Any] | None:
    if not body:
        return None
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return {"raw": body}
    ns = {"atom": ATOM_NS, "sword": SWORD_NS}
    verbose = _text(root.find("sword:verboseDescription", ns))
    parsed_verbose: Any = verbose
    if verbose:
        try:
            parsed_verbose = json.loads(verbose)
        except json.JSONDecodeError:
            pass
    return {
        "error_uri": root.attrib.get("href"),
        "title": _text(root.find("atom:title", ns)),
        "summary": _text(root.find("atom:summary", ns)),
        "treatment": _text(root.find("sword:treatment", ns)),
        "verbose": parsed_verbose,
    }


def write_bundle(
    xml_path: Path,
    result: SWORDResult,
    output_dir: Path,
    inspection: dict[str, Any],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(xml_path, output_dir / "request.xml")
    if result.response_body:
        (output_dir / "response.xml").write_text(result.response_body, encoding="utf-8")
    report = {
        "request": {
            "url": PREPROD_URL,
            "method": "POST",
            "headers": {
                "Authorization": "Basic <redacted>",
                "Packaging": PACKAGING,
                "Content-Type": "text/xml",
                "X-test": "1",
                "LoadFilter": "noaffiliation",
                "ForceDoublonByTitle": "0",
            },
            "xml_file": xml_path.name,
            "inspection": inspection,
        },
        "response": {
            "status_code": result.status_code,
            "accepted": result.accepted,
            "hal_id": result.hal_id,
            "hal_url": result.hal_url,
            "error": result.error,
            "parsed_error": parse_hal_error(result.response_body),
        },
    }
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


@app.command()
def diagnose(
    xml_file: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o")] = Path(
        "output/hal-diagnostic"
    ),
) -> None:
    """Inspect and test-submit one notice, then write a credential-safe bundle."""
    try:
        inspection = inspect_xml(xml_file)
        result = submit_notice(xml_file, environment="preprod", test=True)
        report = write_bundle(xml_file, result, output_dir, inspection)
    except (ET.ParseError, OSError, RuntimeError, ValueError) as exc:
        typer.echo(f"Diagnosis failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(f"HAL status: {result.status_code}")
    typer.echo(f"Accepted/test-validated: {'yes' if result.accepted else 'no'}")
    typer.echo(f"Diagnostic report: {report}")
    typer.echo(f"Request XML: {output_dir / 'request.xml'}")
    if result.response_body:
        typer.echo(f"Response XML: {output_dir / 'response.xml'}")
    if not result.accepted:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
