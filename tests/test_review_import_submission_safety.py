from __future__ import annotations

import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from hal_assistant.review_import import import_review_workbook

HEADERS = [
    "publication_id",
    "decision",
    "publication_type",
    "title",
    "year",
    "authors",
    "production_status",
    "production_hal_id",
    "hal_match_status",
    "original_citation",
]


def _write_workbook(path: Path, rows: list[list[object]]) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Publications"
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(row)
    workbook.save(path)
    return path


def _row(
    publication_id: str,
    *,
    decision: str = "",
    production_status: str = "",
    production_hal_id: str = "",
) -> list[object]:
    return [
        publication_id,
        decision,
        "journal_article",
        f"Title {publication_id}",
        2025,
        "Florence Fix",
        production_status,
        production_hal_id,
        "not_found",
        f"Title {publication_id}, 2025.",
    ]


def test_exact_allowlist_selects_only_pending_records(tmp_path: Path) -> None:
    workbook = _write_workbook(
        tmp_path / "review.xlsx",
        [
            _row(
                "pub-accepted",
                decision="approve",
                production_status="accepted",
                production_hal_id="hal-01234567",
            ),
            _row("pub-selected"),
            _row("pub-deferred"),
        ],
    )

    result = import_review_workbook(
        workbook,
        tmp_path / "output",
        approval_ids={"pub-selected"},
    )

    assert result.approved_count == 1
    assert result.already_on_hal_count == 1
    assert result.deferred_count == 1
    assert result.blocked_count == 0
    assert result.warning_count == 1

    approved = json.loads(result.approved_path.read_text(encoding="utf-8"))
    assert [record["publication_id"] for record in approved] == ["pub-selected"]

    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    rows = {row["publication_id"]: row for row in report["rows"]}
    assert rows["pub-accepted"]["effective_decision"] == "already_on_hal"
    assert rows["pub-selected"]["effective_decision"] == "approve"
    assert rows["pub-deferred"]["status"] == "deferred"


def test_allowlist_refuses_a_record_already_accepted_in_production(tmp_path: Path) -> None:
    workbook = _write_workbook(
        tmp_path / "review.xlsx",
        [
            _row(
                "pub-accepted",
                production_status="accepted",
                production_hal_id="hal-01234567",
            )
        ],
    )

    result = import_review_workbook(
        workbook,
        tmp_path / "output",
        approval_ids={"pub-accepted"},
    )

    assert result.approved_count == 0
    assert result.already_on_hal_count == 1
    assert result.blocked_count == 1
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert "already accepted" in report["rows"][0]["errors"][0]


def test_allowlist_rejects_unknown_publication_ids(tmp_path: Path) -> None:
    workbook = _write_workbook(
        tmp_path / "review.xlsx",
        [_row("pub-known")],
    )

    with pytest.raises(ValueError, match="unknown publication IDs: pub-missing"):
        import_review_workbook(
            workbook,
            tmp_path / "output",
            approval_ids={"pub-missing"},
        )


def test_default_import_excludes_stale_approve_for_accepted_record(tmp_path: Path) -> None:
    workbook = _write_workbook(
        tmp_path / "review.xlsx",
        [
            _row(
                "pub-accepted",
                decision="approve",
                production_status="accepted",
                production_hal_id="hal-01234567",
            )
        ],
    )

    result = import_review_workbook(workbook, tmp_path / "output")

    assert result.approved_count == 0
    assert result.already_on_hal_count == 1
    assert result.blocked_count == 0
