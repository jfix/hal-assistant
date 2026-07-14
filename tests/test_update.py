import hashlib
import json
from pathlib import Path

import pytest

from hal_assistant.update import UpdateCandidate, _update_one, load_update_manifest, update_batch


def _batch(tmp_path: Path) -> Path:
    xml = tmp_path / "hal-01234567.xml"
    xml.write_text("<TEI/>", encoding="utf-8")
    digest = hashlib.sha256(xml.read_bytes()).hexdigest()
    (tmp_path / "update-manifest.json").write_text(
        json.dumps(
            {
                "format": "hal-assistant-update-batch-v1",
                "records": [
                    {
                        "hal_id": "hal-01234567",
                        "version": 2,
                        "xml_file": xml.name,
                        "sha256": digest,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_manifest_requires_exact_id_version_and_checksum(tmp_path: Path) -> None:
    root = _batch(tmp_path)
    candidate = load_update_manifest(root)[0]
    assert candidate.hal_id == "hal-01234567"
    assert candidate.version == 2

    manifest = json.loads((root / "update-manifest.json").read_text())
    manifest["records"][0]["sha256"] = "0" * 64
    (root / "update-manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Checksum mismatch"):
        load_update_manifest(root)


def test_real_update_requires_execute(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="--execute"):
        update_batch(_batch(tmp_path), test=False)


def test_real_update_requires_confirmation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HAL_SWORD_CONFIRM_UPDATE", raising=False)
    with pytest.raises(RuntimeError, match="HAL_SWORD_CONFIRM_UPDATE"):
        update_batch(_batch(tmp_path), test=False, execute=True)


def test_real_update_requires_matching_successful_xtest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _batch(tmp_path)
    monkeypatch.setenv("HAL_SWORD_CONFIRM_UPDATE", "UPDATE_EXISTING_HAL_RECORDS")
    with pytest.raises(ValueError, match="X-test ledger"):
        update_batch(root, test=False, execute=True)


def test_manifest_rejects_duplicate_target(tmp_path: Path) -> None:
    root = _batch(tmp_path)
    manifest = json.loads((root / "update-manifest.json").read_text())
    manifest["records"].append(dict(manifest["records"][0]))
    (root / "update-manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Duplicate HAL identifier"):
        load_update_manifest(root)


def test_xtest_accepts_hal_placeholder_identifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _batch(tmp_path)
    candidate = UpdateCandidate(
        "hal-01234567",
        2,
        "hal-01234567.xml",
        hashlib.sha256((root / "hal-01234567.xml").read_bytes()).hexdigest(),
    )

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'''<entry xmlns="http://www.w3.org/2005/Atom">
                <id>FooTestId-12345678</id>
            </entry>'''

    monkeypatch.setattr("hal_assistant.update._credentials", lambda: ("login", "password"))
    monkeypatch.setattr("hal_assistant.update.urlopen", lambda *_args, **_kwargs: Response())
    result = _update_one(root, candidate, test=True, on_behalf_of=None)
    assert result.accepted is True
    assert result.returned_hal_id == "FooTestId-12345678"
