"""Build a naturally ordered component BOM from DCH, ASC or DCHXML."""
import argparse
from collections import defaultdict
from collections.abc import Iterable
import csv
from pathlib import Path
import re

from lib import ConversionReport, read, split_refdes
from apps.common.components import Component, Signature, physical_components
from apps.common.cli import Console, PROCESSING_ERRORS, add_report_argument
from apps.common.paths import require_distinct_paths

CSV_FIELDS = ("RefDes", "Name", "Value", "Pattern")
NUMBER_RUN = re.compile(r"([0-9]+)")


def natural_key(reference: str) -> tuple:
    """Put R2 before R10, including numbers inside compound references."""
    return tuple(
        (1, int(token)) if token.isdigit() else (0, token.casefold())
        for token in NUMBER_RUN.split(reference)
        if token
    )


def group_bom(components: Iterable[Component]) -> list[dict[str, str]]:
    """Group identical parts, retaining the first occurrence of each RefDes."""
    seen_references = set()
    groups: dict[Signature, list[str]] = defaultdict(list)
    for component in components:
        # A multipart component can occur more than once in a schematic. Count
        # the physical reference once, preserving the first occurrence's facts.
        try:
            identity = split_refdes(component.reference)
        except ValueError:
            identity = component.reference
        if identity in seen_references:
            continue
        seen_references.add(identity)
        groups[component.signature].append(component.reference)

    rows = []
    for (name, value, pattern), references in groups.items():
        references.sort(key=natural_key)
        rows.append({
            "RefDes": ", ".join(references),
            "Name": name,
            "Value": value,
            "Pattern": pattern,
        })
    rows.sort(key=lambda row: natural_key(row["RefDes"]))
    return rows


def build_bom(path: Path, *, report=None) -> tuple[list[dict[str, str]], bool]:
    """Return CSV rows and import completeness through the shared model."""
    design = read(path, report=report)
    return group_bom(physical_components(design)), design.complete


def write_bom(path: Path, rows: list[dict[str, str]]) -> None:
    """Keep CSV formatting independent of schematic reading and grouping."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(
            output, fieldnames=CSV_FIELDS, delimiter=";",
            quoting=csv.QUOTE_ALL, lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="diptrace_bom", description=__doc__)
    parser.add_argument("input_design", type=Path, help="DCH, ASC or DCHXML schematic")
    parser.add_argument("output_csv", type=Path, help="semicolon-delimited BOM CSV")
    add_report_argument(parser)
    args = parser.parse_args(argv)
    console = Console(args.report_level)
    try:
        require_distinct_paths(args.input_design, args.output_csv)
    except ValueError as error:
        parser.error(str(error))
    report = ConversionReport()
    try:
        # Import and group before opening an existing CSV, so a bad schematic
        # leaves the previous BOM intact.
        rows, _ = build_bom(args.input_design, report=report)
        write_bom(args.output_csv, rows)
    except PROCESSING_ERRORS as error:
        return console.failure("BOM export failed", error, report=report)

    console.report(report)
    console.info(f"Wrote {args.output_csv}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
