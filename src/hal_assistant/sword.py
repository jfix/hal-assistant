from __future__ import annotations

import base64
import hashlib
import json
import os
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
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
    sha256: str | None = None
    force_duplicate_by_title: bool = False


def _credentials() -> tuple[str, str]:
    login = os.getenv("HAL_SWORD_LOGIN")
    password = os.getenv("HAL_SWORD_PASSWORD")
    if not login or not password:
        raise RuntimeError(
            "HAL credentials are missing. Set HAL_SWORD_LOGIN and HAL_SWORD_PASSWORD."
        )
    return login, password


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _headers(
    login: str,
    password: str,
    *,
    test: bool,
    on_behalf_of: str | None,
    force_duplicate_by_title: bool = False,
) -> dict[str, str]:
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "Packaging": PACKAGING,
        "Content-Type": "text/xml",
        "User-Agent": "hal-assistant/0.9",
        "ForceDoublonByTitle": "1" if force_duplicate_by_title else "0",
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
    force_duplicate_by_title: bool = False,
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
    headers = _headers(
        login,
        password,
        test=test,
        on_behalf_of=on_behalf_of,
        force_duplicate_by_title=force_duplicate_by_title,
    )
    request = Request(url, data=path.read_bytes(), headers=headers, method="POST")
    digest = _sha256(path)
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
                sha256=digest,
                force_duplicate_by_title=force_duplicate_by_title,
            )
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return SWORDResult(
            xml_file=path.name,
            status_code=exc.code,
            accepted=False,
            response_body=body,
            error=f"HAL returned HTTP {exc.code}",
            sha256=digest,
            force_duplicate_by_title=force_duplicate_by_title,
        )
    except URLError as exc:
        return SWORDResult(
            xml_file=path.name,
            status_code=None,
            accepted=False,
            error=f"Network error: {exc.reason}",
            sha256=digest,
            force_duplicate_by_title=force_duplicate_by_title,
        )


def _ledger_name(environment: str, test: bool) -> str:
    suffix = "test" if test else "submission"
    return f"submission-ledger-{environment}-{suffix}.json"


def _load_existing_ledger(
    ledger: Path,
    *,
    environment: str,
    test: bool,
    resume: bool,
) -> dict[str, object]:
    if not ledger.exists():
        return {}
    if not resume:
        raise ValueError(f"Refusing to overwrite existing ledger: {ledger}")
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    if payload.get("environment") != environment or payload.get("test") is not test:
        raise ValueError(f"Existing ledger does not match this submission stage: {ledger}")
    return payload


def _write_ledger_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _forced_candidate(directory: Path, filename: str) -> Path:
    if (
        not filename.endswith(".xml")
        or Path(filename).name != filename
        or any(character in filename for character in "*?[]")
    ):
        raise ValueError("--force-title-duplicate requires one exact XML basename")
    candidate = directory / filename
    if not candidate.is_file():
        raise ValueError(f"Forced duplicate XML file not found: {candidate}")
    return candidate


def _iter_ledger_results(payload: dict[str, object]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for item in payload.get("results", []):
        if isinstance(item, dict):
            results.append(item)
    for attempt in payload.get("attempts", []):
        if not isinstance(attempt, dict):
            continue
        for item in attempt.get("results", []):
            if isinstance(item, dict):
                results.append(item)
    return results


def _require_forced_production_test(directory: Path, path: Path) -> None:
    ledger = directory / _ledger_name("production", True)
    if not ledger.exists():
        raise ValueError(
            "A matching successful production X-test is required before a forced duplicate write"
        )
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    if payload.get("environment") != "production" or payload.get("test") is not True:
        raise ValueError("Forced duplicate validation ledger is not a production X-test")
    digest = _sha256(path)
    matching = [
        item
        for item in _iter_ledger_results(payload)
        if item.get("xml_file") == path.name
        and item.get("accepted") is True
        and item.get("force_duplicate_by_title") is True
        and item.get("sha256") == digest
    ]
    if not matching:
        raise ValueError(
            "No successful forced production X-test with a matching XML checksum was found"
        )


def submit_batch(
    xml_dir: str | Path,
    *,
    environment: str,
    test: bool,
    execute: bool,
    on_behalf_of: str | None,
    limit: int | None = None,
    fail_fast: bool = False,
    resume: bool = False,
    force_title_duplicate: str | None = None,
) -> tuple[list[SWORDResult], Path]:
    """Submit notices independently and maintain a cumulative, resumable ledger."""
    if environment not in {"preprod", "production"}:
        raise ValueError("environment must be 'preprod' or 'production'")
    if environment == "production" and not test and not execute:
        raise ValueError("Refusing production writes without --execute")
    if force_title_duplicate and environment != "production":
        raise ValueError("Title-duplicate forcing must be tested against the production endpoint")
    if force_title_duplicate and limit is not None:
        raise ValueError("--limit cannot be combined with --force-title-duplicate")
    if environment == "production" and not test:
        confirmation = os.getenv("HAL_SWORD_CONFIRM_PRODUCTION")
        if confirmation != "SUBMIT_TO_HAL":
            raise RuntimeError(
                "Set HAL_SWORD_CONFIRM_PRODUCTION=SUBMIT_TO_HAL for production writes."
            )

    directory = Path(xml_dir)
    all_files = sorted(directory.glob("*.xml"))
    files = all_files
    forced_path: Path | None = None
    if force_title_duplicate:
        forced_path = _forced_candidate(directory, force_title_duplicate)
        files = [forced_path]
    elif limit:
        files = files[:limit]

    if forced_path is not None and environment == "production" and not test:
        duplicate_confirmation = os.getenv("HAL_SWORD_CONFIRM_TITLE_DUPLICATE")
        if duplicate_confirmation != forced_path.name:
            raise RuntimeError(
                "Set HAL_SWORD_CONFIRM_TITLE_DUPLICATE to the exact XML filename "
                "for a forced title-duplicate write."
            )
        _require_forced_production_test(directory, forced_path)

    ledger = directory / _ledger_name(environment, test)
    previous = _load_existing_ledger(
        ledger,
        environment=environment,
        test=test,
        resume=resume,
    )

    previous_results = {
        str(item.get("xml_file")): item
        for item in previous.get("results", [])
        if isinstance(item, dict) and item.get("xml_file")
    }
    accepted_names = {
        name for name, item in previous_results.items() if item.get("accepted") is True
    }
    pending_files = [path for path in files if path.name not in accepted_names]

    attempt_results: list[SWORDResult] = []
    for path in pending_files:
        force_for_file = forced_path is not None and path.name == forced_path.name
        if environment == "production" and not test:
            result = _submit_production_notice(
                path,
                on_behalf_of=on_behalf_of,
                force_duplicate_by_title=force_for_file,
            )
        else:
            result = submit_notice(
                path,
                environment=environment,
                test=test,
                on_behalf_of=on_behalf_of,
                force_duplicate_by_title=force_for_file,
            )
        attempt_results.append(result)
        previous_results[path.name] = asdict(result)
        if fail_fast and not result.accepted:
            break

    ordered_results: list[SWORDResult] = []
    known_names = {path.name for path in all_files}
    ordered_names = [path.name for path in all_files if path.name in previous_results]
    ordered_names.extend(sorted(set(previous_results) - known_names))
    for name in ordered_names:
        item = previous_results.get(name)
        if item is not None:
            ordered_results.append(SWORDResult(**item))

    now = datetime.now(UTC).isoformat()
    attempts = list(previous.get("attempts", []))
    attempts.append(
        {
            "started_from_resume": bool(previous),
            "completed_at": now,
            "submitted": len(attempt_results),
            "accepted": sum(item.accepted for item in attempt_results),
            "rejected": sum(not item.accepted for item in attempt_results),
            "force_title_duplicate": force_title_duplicate,
            "results": [asdict(item) for item in attempt_results],
        }
    )
    payload: dict[str, object] = {
        "created_at": previous.get("created_at", now),
        "updated_at": now,
        "environment": environment,
        "test": test,
        "load_filter": "noaffiliation",
        "fail_fast": fail_fast,
        "resume": resume,
        "candidate_files": len(all_files),
        "selected_files": len(files),
        "forced_title_duplicate_file": force_title_duplicate,
        "submitted": len(ordered_results),
        "accepted": sum(item.accepted for item in ordered_results),
        "rejected": sum(not item.accepted for item in ordered_results),
        "pending": len(all_files) - len(ordered_results),
        "results": [asdict(item) for item in ordered_results],
        "attempts": attempts,
    }
    _write_ledger_atomic(ledger, payload)
    return ordered_results, ledger


def _submit_production_notice(
    xml_path: str | Path,
    *,
    on_behalf_of: str | None,
    force_duplicate_by_title: bool = False,
    timeout: float = 60.0,
) -> SWORDResult:
    """Production-only implementation, reachable after all batch guards pass."""
    login, password = _credentials()
    path = Path(xml_path)
    headers = _headers(
        login,
        password,
        test=False,
        on_behalf_of=on_behalf_of,
        force_duplicate_by_title=force_duplicate_by_title,
    )
    request = Request(PRODUCTION_URL, data=path.read_bytes(), headers=headers, method="POST")
    digest = _sha256(path)
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
                sha256=digest,
                force_duplicate_by_title=force_duplicate_by_title,
            )
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return SWORDResult(
            xml_file=path.name,
            status_code=exc.code,
            accepted=False,
            response_body=body,
            error=f"HAL returned HTTP {exc.code}",
            sha256=digest,
            force_duplicate_by_title=force_duplicate_by_title,
        )
    except URLError as exc:
        return SWORDResult(
            xml_file=path.name,
            status_code=None,
            accepted=False,
            error=f"Network error: {exc.reason}",
            sha256=digest,
            force_duplicate_by_title=force_duplicate_by_title,
        )
