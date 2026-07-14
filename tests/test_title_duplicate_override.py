import hashlib
import json
from pathlib import Path
from urllib.request import Request

import pytest

from hal_assistant import sword
from hal_assistant.sword import SWORDResult, submit_batch


class _Response:
    status = 202

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return (
            b'<?xml version="1.0"?>'
            b'<entry xmlns="http://www.w3.org/2005/Atom">'
            b"<id>hal-test</id>"
            b'<link rel="alternate" href="https://hal.science/hal-test"/>'
            b"</entry>"
        )


def _write_xml(directory: Path, name: str, title: str) -> Path:
    path = directory / name
    path.write_text(f"<TEI><title>{title}</title></TEI>", encoding="utf-8")
    return path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _forced_test_ledger(directory: Path, path: Path) -> None:
    result = {
        "xml_file": path.name,
        "status_code": 202,
        "accepted": True,
        "sha256": _digest(path),
        "force_duplicate_by_title": True,
    }
    (directory / "submission-ledger-production-test.json").write_text(
        json.dumps(
            {
                "environment": "production",
                "test": True,
                "results": [result],
                "attempts": [{"results": [result]}],
            }
        ),
        encoding="utf-8",
    )


def test_forced_duplicate_x_test_targets_one_exact_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = _write_xml(tmp_path, "pub-0017.xml", "Le Paon d'Héra 1")
    _write_xml(tmp_path, "pub-0018.xml", "Le Paon d'Héra 2")
    monkeypatch.setenv("HAL_SWORD_LOGIN", "login")
    monkeypatch.setenv("HAL_SWORD_PASSWORD", "password")
    requests: list[Request] = []

    def fake_urlopen(request: Request, timeout: float) -> _Response:
        requests.append(request)
        assert timeout == 60.0
        return _Response()

    monkeypatch.setattr(sword, "urlopen", fake_urlopen)

    results, ledger_path = submit_batch(
        tmp_path,
        environment="production",
        test=True,
        execute=False,
        on_behalf_of=None,
        resume=False,
        force_title_duplicate=selected.name,
    )

    assert [item.xml_file for item in results] == [selected.name]
    assert len(requests) == 1
    assert requests[0].get_header("Forcedoublonbytitle") == "1"
    assert requests[0].get_header("X-test") == "1"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert ledger["selected_files"] == 1
    assert ledger["pending"] == 1
    assert ledger["results"][0]["sha256"] == _digest(selected)
    assert ledger["results"][0]["force_duplicate_by_title"] is True


def test_forced_duplicate_write_requires_matching_production_x_test(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = _write_xml(tmp_path, "pub-0017.xml", "Le Paon d'Héra 1")
    monkeypatch.setenv("HAL_SWORD_CONFIRM_PRODUCTION", "SUBMIT_TO_HAL")
    monkeypatch.setenv("HAL_SWORD_CONFIRM_TITLE_DUPLICATE", selected.name)

    with pytest.raises(ValueError, match="matching successful production X-test"):
        submit_batch(
            tmp_path,
            environment="production",
            test=False,
            execute=True,
            on_behalf_of=None,
            resume=False,
            force_title_duplicate=selected.name,
        )


def test_forced_duplicate_write_preserves_prior_accepted_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accepted = _write_xml(tmp_path, "pub-0016.xml", "Already accepted")
    selected = _write_xml(tmp_path, "pub-0017.xml", "Le Paon d'Héra 1")
    _forced_test_ledger(tmp_path, selected)
    previous_results = [
        {
            "xml_file": accepted.name,
            "status_code": 201,
            "accepted": True,
            "hal_id": "hal-existing",
            "sha256": _digest(accepted),
            "force_duplicate_by_title": False,
        },
        {
            "xml_file": selected.name,
            "status_code": 400,
            "accepted": False,
            "error": "HAL returned HTTP 400",
            "sha256": _digest(selected),
            "force_duplicate_by_title": False,
        },
    ]
    (tmp_path / "submission-ledger-production-submission.json").write_text(
        json.dumps(
            {
                "environment": "production",
                "test": False,
                "results": previous_results,
                "attempts": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HAL_SWORD_CONFIRM_PRODUCTION", "SUBMIT_TO_HAL")
    monkeypatch.setenv("HAL_SWORD_CONFIRM_TITLE_DUPLICATE", selected.name)
    calls: list[tuple[str, bool]] = []

    def fake_submit(
        xml_path: str | Path,
        *,
        on_behalf_of: str | None,
        force_duplicate_by_title: bool = False,
        timeout: float = 60.0,
    ) -> SWORDResult:
        path = Path(xml_path)
        calls.append((path.name, force_duplicate_by_title))
        return SWORDResult(
            xml_file=path.name,
            status_code=201,
            accepted=True,
            hal_id="hal-new",
            sha256=_digest(path),
            force_duplicate_by_title=force_duplicate_by_title,
        )

    monkeypatch.setattr(sword, "_submit_production_notice", fake_submit)

    results, ledger_path = submit_batch(
        tmp_path,
        environment="production",
        test=False,
        execute=True,
        on_behalf_of=None,
        resume=True,
        force_title_duplicate=selected.name,
    )

    assert calls == [(selected.name, True)]
    assert [(item.xml_file, item.accepted) for item in results] == [
        (accepted.name, True),
        (selected.name, True),
    ]
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert ledger["accepted"] == 2
    assert ledger["rejected"] == 0


@pytest.mark.parametrize("filename", ["../pub-0017.xml", "pub-0017", "*.xml"])
def test_forced_duplicate_requires_exact_xml_basename(
    tmp_path: Path,
    filename: str,
) -> None:
    with pytest.raises(ValueError, match="exact XML basename"):
        submit_batch(
            tmp_path,
            environment="production",
            test=True,
            execute=False,
            on_behalf_of=None,
            force_title_duplicate=filename,
        )


def test_forced_duplicate_is_not_available_on_preproduction(tmp_path: Path) -> None:
    _write_xml(tmp_path, "pub-0017.xml", "Le Paon d'Héra 1")
    with pytest.raises(ValueError, match="production endpoint"):
        submit_batch(
            tmp_path,
            environment="preprod",
            test=True,
            execute=False,
            on_behalf_of=None,
            force_title_duplicate="pub-0017.xml",
        )
