from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Thread
from typing import Annotated

import typer

from .deposit import build_deposit_plans, export_deposit_plans
from .enrichment import enrich_publications
from .exporters import export_excel, export_json
from .hal import match_publications
from .hal_xml import build_xml_batch
from .models import Publication
from .parser import parse_docx
from .sword import submit_batch

app = typer.Typer(no_args_is_help=True, help="Prepare publication metadata for HAL workflows.")


@contextmanager
def heartbeat(label: str, interval: float = 10.0) -> Iterator[None]:
    """Print periodic activity messages while a long-running phase is active."""
    stop = Event()
    started = time.monotonic()

    def report() -> None:
        while not stop.wait(interval):
            elapsed = int(time.monotonic() - started)
            typer.echo(f"  … {label} still running ({elapsed}s elapsed)")

    typer.echo(f"▶ {label}")
    thread = Thread(target=report, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=0.2)
        elapsed = time.monotonic() - started
        typer.echo(f"✓ {label} complete ({elapsed:.1f}s)")


@app.command()
def run(
    document: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    idhal: Annotated[
        str,
        typer.Option(help="HAL Id used as the authoritative existing-publication set."),
    ],
    author: Annotated[
        str | None,
        typer.Option(help="Default author added to every parsed record."),
    ] = None,
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o")] = Path("output"),
    enrich: Annotated[
        bool,
        typer.Option("--enrich/--no-enrich", help="Enrich unmatched records before planning."),
    ] = True,
) -> None:
    """Run DOCX parsing, HAL matching, enrichment, and deposit dry-run end to end."""
    parsed_dir = output_dir / "parsed"
    review_dir = output_dir / "hal-review"
    dry_run_dir = output_dir / "dry-run"

    with heartbeat("Parsing DOCX and exporting parsed records"):
        publications = parse_docx(document, default_author=author)
        parsed_json = export_json(publications, parsed_dir / "publications.json")
        export_excel(publications, parsed_dir / "publications.xlsx")
    typer.echo(f"  Parsed {len(publications)} publications")

    with heartbeat(f"Matching publications against HAL Id {idhal}"):
        match_publications(publications, idhal=idhal)

    if enrich:
        with heartbeat("Enriching unmatched publications through Crossref/OpenAlex"):
            enrich_publications(publications)
    else:
        typer.echo("- Metadata enrichment skipped")

    with heartbeat("Writing HAL review files"):
        review_json = export_json(publications, review_dir / "publications-with-hal.json")
        export_excel(publications, review_dir / "publications-with-hal.xlsx")

    with heartbeat("Building dry-run deposit plan"):
        plans = build_deposit_plans(publications)
        plan_json, plan_excel = export_deposit_plans(plans, dry_run_dir)
    statuses = Counter(plan.status.value for plan in plans)

    typer.echo("\nDry run complete")
    for status, count in sorted(statuses.items()):
        typer.echo(f"  {status}: {count}")
    typer.echo(f"Parsed JSON: {parsed_json}")
    typer.echo(f"HAL review JSON: {review_json}")
    typer.echo(f"Deposit plan JSON: {plan_json}")
    typer.echo(f"Deposit plan Excel: {plan_excel}")
    typer.echo(f"Packages: {dry_run_dir / 'packages'}")


@app.command()
def parse(
    document: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o")] = Path("output"),
    author: Annotated[
        str | None,
        typer.Option(help="Default author added to every record."),
    ] = None,
) -> None:
    """Parse a DOCX publication list and export JSON and Excel review files."""
    publications = parse_docx(document, default_author=author)
    json_path = export_json(publications, output_dir / "publications.json")
    excel_path = export_excel(publications, output_dir / "publications.xlsx")
    typer.echo(f"Parsed {len(publications)} publications")
    for publication_type, count in sorted(
        Counter(item.publication_type.value for item in publications).items()
    ):
        typer.echo(f"  {publication_type}: {count}")
    typer.echo(f"JSON:  {json_path}")
    typer.echo(f"Excel: {excel_path}")


@app.command("match-hal")
def match_hal(
    source: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o")] = Path(
        "output/hal-review"
    ),
    idhal: Annotated[
        str | None,
        typer.Option(help="Use this HAL Id as the authoritative candidate set."),
    ] = None,
    enrich: Annotated[
        bool,
        typer.Option(help="Enrich records not confidently found in HAL."),
    ] = False,
) -> None:
    """Search HAL without modifying it and export a match-review report."""
    payload = json.loads(source.read_text(encoding="utf-8"))
    publications = [Publication.model_validate(item) for item in payload]
    match_publications(publications, idhal=idhal)
    if enrich:
        enrich_publications(publications)
    json_path = export_json(publications, output_dir / "publications-with-hal.json")
    excel_path = export_excel(publications, output_dir / "publications-with-hal.xlsx")
    statuses = Counter(
        item.hal_match.status.value
        for item in publications
        if item.hal_match is not None
    )
    typer.echo(f"Checked {len(publications)} publications against HAL")
    for status, count in sorted(statuses.items()):
        typer.echo(f"  {status}: {count}")
    typer.echo(f"JSON:  {json_path}")
    typer.echo(f"Excel: {excel_path}")


@app.command("prepare-deposits")
def prepare_deposits(
    source: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o")] = Path(
        "output/dry-run"
    ),
) -> None:
    """Generate a credential-free HAL deposit plan without uploading anything."""
    payload = json.loads(source.read_text(encoding="utf-8"))
    publications = [Publication.model_validate(item) for item in payload]
    plans = build_deposit_plans(publications)
    json_path, excel_path = export_deposit_plans(plans, output_dir)
    statuses = Counter(plan.status.value for plan in plans)
    typer.echo(f"Prepared {len(plans)} dry-run deposit plans")
    for status, count in sorted(statuses.items()):
        typer.echo(f"  {status}: {count}")
    typer.echo(f"JSON:  {json_path}")
    typer.echo(f"Excel: {excel_path}")
    typer.echo(f"Packages: {output_dir / 'packages'}")


@app.command("build-hal-xml")
def build_hal_xml(
    source: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    domain: Annotated[
        str,
        typer.Option(help="Required HAL scientific-domain code, for example shs.litt."),
    ],
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o")] = Path(
        "output/hal-xml"
    ),
    domain_label: Annotated[
        str | None,
        typer.Option(help="Optional human-readable HAL domain label."),
    ] = None,
    idhal: Annotated[
        str | None,
        typer.Option(help="IdHAL attached to the selected author in generated TEI."),
    ] = None,
    idhal_author: Annotated[
        str | None,
        typer.Option(help="Author name that should receive --idhal."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(help="Build only the first N records for a small test batch."),
    ] = None,
) -> None:
    """Convert reviewed HAL-ready JSON into notice-only AOfr TEI XML files."""
    with heartbeat("Building HAL AOfr TEI XML"):
        results = build_xml_batch(
            source,
            output_dir,
            domain=domain,
            domain_label=domain_label,
            idhal=idhal,
            idhal_author=idhal_author,
            limit=limit,
        )
    valid = sum(not item.errors for item in results)
    blocked = len(results) - valid
    typer.echo(f"Generated {valid} XML files; blocked: {blocked}")
    typer.echo(f"Manifest: {output_dir / 'manifest.json'}")
    if blocked:
        raise typer.Exit(code=1)


@app.command("submit-hal")
def submit_hal(
    xml_dir: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=False, readable=True),
    ],
    environment: Annotated[
        str,
        typer.Option(help="HAL endpoint: preprod or production."),
    ] = "preprod",
    test: Annotated[
        bool,
        typer.Option("--test/--no-test", help="Send X-test: 1; enabled by default."),
    ] = True,
    execute: Annotated[
        bool,
        typer.Option(help="Required for non-test production writes."),
    ] = False,
    on_behalf_of: Annotated[
        str | None,
        typer.Option(help="HAL On-Behalf-Of value, e.g. idhal|florence-fix."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(help="Submit at most N XML notices."),
    ] = None,
) -> None:
    """Validate notices remotely through HAL SWORD, or submit with explicit write gates."""
    with heartbeat(f"Submitting HAL SWORD batch to {environment}"):
        try:
            results, ledger = submit_batch(
                xml_dir,
                environment=environment,
                test=test,
                execute=execute,
                on_behalf_of=on_behalf_of,
                limit=limit,
            )
        except (RuntimeError, ValueError) as exc:
            typer.echo(f"Refused: {exc}", err=True)
            raise typer.Exit(code=2) from exc
    accepted = sum(item.accepted for item in results)
    typer.echo(f"HAL accepted/test-validated: {accepted}/{len(results)}")
    typer.echo(f"Ledger: {ledger}")
    if accepted != len(results):
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Print the installed HAL Assistant version."""
    from . import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()
