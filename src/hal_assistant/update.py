from __future__ import annotations

import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .sword import PRODUCTION_URL, _credentials, _headers, _parse_atom, _write_ledger_atomic

HAL_ID_RE = re.compile(r"^(?:hal|halshs)-\d{8}$")


@dataclass(frozen=True)
class UpdateCandidate:
    hal_id: str
    version: int
    xml_file: str
    sha256: str


@dataclass(frozen=True)
class UpdateResult:
    hal_id: str
    version: int
    xml_file: str
    sha256: str
    target_url: str
    status_code: int | None
    accepted: bool
    returned_hal_id: str | None = None
    hal_url: str | None = None
    error: str | None = None


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_update_manifest(directory: str | Path) -> list[UpdateCandidate]:
    root = Path(directory)
    manifest_path = root / "update-manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"Update manifest not found: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("format") != "hal-assistant-update-batch-v1":
        raise ValueError("Unsupported update manifest format")
    candidates: list[UpdateCandidate] = []
    seen: set[str] = set()
    for raw in payload.get("records", []):
        hal_id = str(raw.get("hal_id", ""))
        if not HAL_ID_RE.fullmatch(hal_id):
            raise ValueError(f"Invalid HAL identifier: {hal_id!r}")
        if hal_id in seen:
            raise ValueError(f"Duplicate HAL identifier in manifest: {hal_id}")
        seen.add(hal_id)
        version = raw.get("version")
        if not isinstance(version, int) or version < 1:
            raise ValueError(f"Invalid version for {hal_id}: {version!r}")
        xml_file = str(raw.get("xml_file", ""))
        if not xml_file or Path(xml_file).name != xml_file:
            raise ValueError(f"Invalid XML filename for {hal_id}: {xml_file!r}")
        path = root / xml_file
        if not path.is_file():
            raise ValueError(f"XML file not found for {hal_id}: {path}")
        try:
            ET.parse(path)
        except ET.ParseError as exc:
            raise ValueError(f"Malformed XML for {hal_id}: {exc}") from exc
        expected = str(raw.get("sha256", ""))
        actual = _digest(path)
        if expected != actual:
            raise ValueError(f"Checksum mismatch for {hal_id}")
        candidates.append(UpdateCandidate(hal_id, version, xml_file, actual))
    if not candidates:
        raise ValueError("Update manifest contains no records")
    return candidates


def _target(candidate: UpdateCandidate) -> str:
    return f"{PRODUCTION_URL.rstrip('/')}/{candidate.hal_id}v{candidate.version}"


def _update_one(
    directory: Path,
    candidate: UpdateCandidate,
    *,
    test: bool,
    on_behalf_of: str | None,
    timeout: float = 60.0,
) -> UpdateResult:
    login, password = _credentials()
    headers = _headers(login, password, test=test, on_behalf_of=on_behalf_of)
    # HAL documents these filters as preserving existing affiliations and domains.
    headers["LoadFilter"] = "noaffiliation,nodomain"
    target = _target(candidate)
    request = Request(
        target,
        data=(directory / candidate.xml_file).read_bytes(),
        headers=headers,
        method="PUT",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            returned_hal_id, hal_url = _parse_atom(body)
            test_placeholder = bool(
                test and returned_hal_id and returned_hal_id.startswith("FooTestId-")
            )
            accepted = response.status in {200, 201, 202}
            if returned_hal_id and returned_hal_id != candidate.hal_id and not test_placeholder:
                accepted = False
            return UpdateResult(
                **asdict(candidate),
                target_url=target,
                status_code=response.status,
                accepted=accepted,
                returned_hal_id=returned_hal_id,
                hal_url=hal_url,
                error=(
                    f"HAL returned unexpected identifier {returned_hal_id}"
                    if returned_hal_id
                    and returned_hal_id != candidate.hal_id
                    and not test_placeholder
                    else None
                ),
            )
    except HTTPError as exc:
        # Do not persist the response body: HAL responses can contain deposit passwords.
        exc.read()
        return UpdateResult(
            **asdict(candidate),
            target_url=target,
            status_code=exc.code,
            accepted=False,
            error=f"HAL returned HTTP {exc.code}",
        )
    except URLError as exc:
        return UpdateResult(
            **asdict(candidate),
            target_url=target,
            status_code=None,
            accepted=False,
            error=f"Network error: {exc.reason}",
        )


def _validated_test_checksums(directory: Path) -> dict[str, str]:
    path = directory / "update-ledger-production-test.json"
    if not path.exists():
        raise ValueError("A successful production X-test ledger is required before updates")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("test") is not True or payload.get("rejected") != 0:
        raise ValueError("The production X-test ledger is not fully accepted")
    return {
        str(item["hal_id"]): str(item["sha256"])
        for item in payload.get("results", [])
        if item.get("accepted") is True
    }


def update_batch(
    directory: str | Path,
    *,
    test: bool = True,
    execute: bool = False,
    on_behalf_of: str | None = None,
    limit: int | None = None,
    fail_fast: bool = False,
    resume: bool = False,
) -> tuple[list[UpdateResult], Path]:
    root = Path(directory)
    candidates = load_update_manifest(root)
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be positive")
        candidates = candidates[:limit]
    if not test:
        if not execute:
            raise ValueError("Refusing production metadata updates without --execute")
        if os.getenv("HAL_SWORD_CONFIRM_UPDATE") != "UPDATE_EXISTING_HAL_RECORDS":
            raise RuntimeError(
                "Set HAL_SWORD_CONFIRM_UPDATE=UPDATE_EXISTING_HAL_RECORDS for production updates."
            )
        validated = _validated_test_checksums(root)
        for candidate in candidates:
            if validated.get(candidate.hal_id) != candidate.sha256:
                raise ValueError(f"No matching successful X-test for {candidate.hal_id}")

    suffix = "test" if test else "submission"
    ledger = root / f"update-ledger-production-{suffix}.json"
    previous: dict[str, object] = {}
    if ledger.exists():
        if not resume:
            raise ValueError(f"Refusing to overwrite existing ledger: {ledger}")
        previous = json.loads(ledger.read_text(encoding="utf-8"))
        if previous.get("test") is not test:
            raise ValueError("Existing ledger does not match this update stage")

    prior_results = {
        str(item["hal_id"]): item
        for item in previous.get("results", [])
        if isinstance(item, dict) and item.get("hal_id")
    }
    attempt: list[UpdateResult] = []
    for candidate in candidates:
        prior = prior_results.get(candidate.hal_id)
        if prior and prior.get("accepted") is True and prior.get("sha256") == candidate.sha256:
            continue
        result = _update_one(root, candidate, test=test, on_behalf_of=on_behalf_of)
        prior_results[candidate.hal_id] = asdict(result)
        attempt.append(result)
        if fail_fast and not result.accepted:
            break

    results = [
        UpdateResult(**prior_results[item.hal_id])
        for item in candidates
        if item.hal_id in prior_results
    ]
    now = datetime.now(UTC).isoformat()
    attempts = list(previous.get("attempts", []))
    attempts.append({"completed_at": now, "results": [asdict(item) for item in attempt]})
    payload: dict[str, object] = {
        "format": "hal-assistant-update-ledger-v1",
        "created_at": previous.get("created_at", now),
        "updated_at": now,
        "environment": "production",
        "method": "PUT",
        "test": test,
        "load_filter": "noaffiliation,nodomain",
        "candidate_records": len(candidates),
        "accepted": sum(item.accepted for item in results),
        "rejected": sum(not item.accepted for item in results),
        "pending": len(candidates) - len(results),
        "results": [asdict(item) for item in results],
        "attempts": attempts,
    }
    _write_ledger_atomic(ledger, payload)
    return results, ledger
