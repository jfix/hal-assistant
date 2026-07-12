from __future__ import annotations

import base64
import json
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .hal_xml import PACKAGING

PREPROD_URL = "https://api-preprod.archives-ouvertes.fr/sword/hal/"
PRODUCTION_URL = "https://api.archives-ouvertes.fr/sword/hal/"
ATOM_NS = "http://www.w3.org/2005/Atom"
HAL_NS = "http://hal.archives-ouvertes.fr/"


@dataclass(frozen=True)
class SWORDResult:
    xml_file: str
    status_code: int | None
    accepted: bool
    hal_id: str | None = None
    hal_url: str | None = None
    response_body: str | None = None
    error: str | None = None


def _credentials() -> tuple[str, str]:
    login = os.getenv("HAL_SWORD_LOGIN")
    password = os.getenv("HAL_SWORD_PASSWORD")
    if not login or not password:
        raise RuntimeError(
            "HAL credentials are missing. Set HAL_SWORD_LOGIN and HAL_SWORD_PASSWORD."
        )
    return login, password


def _parse_atom(body: str) -> tuple[str | None, str | None]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return None, None
    ns = {"atom": ATOM_NS, "hal": HAL_NS}
    id_node = root.find("atom:id", ns)
    hal_id = id_node.text.strip() if id_node is not None and id_node.text else None
    hal_url = None
    for link in root.findall("atom:link", ns):
        if link.attrib.get("rel") == "alternate":
            hal_url = link.attrib.get("href")
            break
    return hal_id, hal_url


def _headers(login: str, password: str, *, test: bool, on_behalf_of: str | None) -> dict[str, str]:
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "Packaging": PACKAGING,
        "Content-Type": "text/xml",
        "User-Agent": "hal-assistant/0.8",
        "ForceDoublonByTitle": "0",
        "LoadFilter": "noaffiliation",
    }
    if test:
        headers["X-test"] = "1"
    if on_behalf_of:
        headers["On-Behalf-Of"] = on_behalf_of
    return headers


def submit_notice(
    xml_path: str | Path,
    *,
    environment: str = "preprod",
    test: bool = True,
    on_behalf_of: str | None = None,
    timeout: float = 60.0,
) -> SWORDResult:
    """Submit one notice-only TEI XML document to HAL SWORD."""
    if environment not in {"preprod", "production"}:
        raise ValueError("environment must be 'preprod' or 'production'")
    if environment == "production" and test is False:
        raise ValueError("Production writes must be invoked by the gated batch command")

    login, password = _credentials()
    path = Path(xml_path)
    url = PREPROD_URL if environment == "preprod" else PRODUCTION_URL
    headers = _headers(login, password, test=test, on_behalf_of=on_behalf_of)
    request = Request(url, data=path.read_bytes(), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            status = response.status
            hal_id, hal_url = _parse_atom(body)
            return SWORDResult(
                xml_file=path.name,
                status_code=status,
                accepted=status in {200, 201, 202},
                hal_id=hal_id,
                hal_url=hal_url,
                response_body=body,
            )
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return SWORDResult(
            xml_file=path.name,
            status_code=exc.code,
            accepted=False,
            response_body=body,
            error=f"HAL returned HTTP {exc.code}",
        )
    except URLError as exc:
        return SWORDResult(
            xml_file=path.name,
            status_code=None,
            accepted=False,
            error=f"Network error: {exc.reason}",
        )


def _ledger_name(environment: str, test: bool) -> str:
    suffix = "test" if test else "submission"
    return f"submission-ledger-{environment}-{suffix}.json"


def submit_batch(
    xml_dir: str | Path,
    *,
    environment: str,
    test: bool,
    execute: bool,
    on_behalf_of: str | None,
    limit: int | None = None,
) -> tuple[list[SWORDResult], Path]:
    """Submit XML files with explicit production-write gating and save an immutable ledger."""
    if environment == "production" and not test and not execute:
        raise ValueError("Refusing production writes without --execute")
    if environment == "production" and not test:
        confirmation = os.getenv("HAL_SWORD_CONFIRM_PRODUCTION")
        if confirmation != "SUBMIT_TO_HAL":
            raise RuntimeError(
                "Set HAL_SWORD_CONFIRM_PRODUCTION=SUBMIT_TO_HAL for production writes."
            )

    directory = Path(xml_dir)
    ledger = directory / _ledger_name(environment, test)
    if ledger.exists():
        raise ValueError(f"Refusing to overwrite existing ledger: {ledger}")

    files = sorted(directory.glob("*.xml"))
    if limit:
        files = files[:limit]
    results: list[SWORDResult] = []
    for path in files:
        if environment == "production" and not test:
            result = _submit_production_notice(path, on_behalf_of=on_behalf_of)
        else:
            result = submit_notice(
                path,
                environment=environment,
                test=test,
                on_behalf_of=on_behalf_of,
            )
        results.append(result)
        if not result.accepted:
            break

    ledger.write_text(
        json.dumps(
            {
                "created_at": datetime.now(UTC).isoformat(),
                "environment": environment,
                "test": test,
                "load_filter": "noaffiliation",
                "submitted": len(results),
                "accepted": sum(item.accepted for item in results),
                "results": [item.__dict__ for item in results],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return results, ledger


def _submit_production_notice(
    xml_path: str | Path,
    *,
    on_behalf_of: str | None,
    timeout: float = 60.0,
) -> SWORDResult:
    """Production-only implementation, reachable after all batch guards pass."""
    login, password = _credentials()
    path = Path(xml_path)
    headers = _headers(login, password, test=False, on_behalf_of=on_behalf_of)
    request = Request(PRODUCTION_URL, data=path.read_bytes(), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            hal_id, hal_url = _parse_atom(body)
            return SWORDResult(
                xml_file=path.name,
                status_code=response.status,
                accepted=response.status in {200, 201, 202},
                hal_id=hal_id,
                hal_url=hal_url,
                response_body=body,
            )
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return SWORDResult(
            xml_file=path.name,
            status_code=exc.code,
            accepted=False,
            response_body=body,
            error=f"HAL returned HTTP {exc.code}",
        )
    except URLError as exc:
        return SWORDResult(
            xml_file=path.name,
            status_code=None,
            accepted=False,
            error=f"Network error: {exc.reason}",
        )
