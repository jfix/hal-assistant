import json
from pathlib import Path

from hal_assistant.diagnose_cli import parse_hal_error, write_bundle
from hal_assistant.sword import SWORDResult


def test_parse_hal_error_extracts_json_verbose_description() -> None:
    body = """<?xml version='1.0'?>
    <sword:error xmlns:sword='http://purl.org/net/sword/error/'
      xmlns='http://www.w3.org/2005/Atom' href='urn:test'>
      <title>ERROR</title>
      <summary>Bad metadata</summary>
      <sword:treatment>processing failed</sword:treatment>
      <sword:verboseDescription>{\"author\":[\"missing\"]}</sword:verboseDescription>
    </sword:error>"""
    parsed = parse_hal_error(body)
    assert parsed is not None
    assert parsed["summary"] == "Bad metadata"
    assert parsed["verbose"] == {"author": ["missing"]}


def test_bundle_redacts_credentials(tmp_path: Path) -> None:
    xml_path = tmp_path / "notice.xml"
    xml_path.write_text("<TEI/>", encoding="utf-8")
    result = SWORDResult(
        xml_file="notice.xml",
        status_code=400,
        accepted=False,
        response_body="bad request",
        error="HAL returned HTTP 400",
    )
    report_path = write_bundle(xml_path, result, tmp_path / "bundle", {})
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["request"]["headers"]["Authorization"] == "Basic <redacted>"
    assert "password" not in report_path.read_text(encoding="utf-8").lower()
    assert (tmp_path / "bundle" / "request.xml").exists()
    assert (tmp_path / "bundle" / "response.xml").exists()
