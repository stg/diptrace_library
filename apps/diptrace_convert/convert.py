"""Convert DipTrace design files between formats or supported output versions."""
import argparse
from pathlib import Path

from lib import ConversionReport, document_family, format_capabilities, read, serialize
from apps.common.cli import Console, PROCESSING_ERRORS, add_report_argument
from apps.common.paths import require_distinct_paths
from .context import load_context


def conversion_formats(source: Path, target: Path, version=None, *, family):
    """Ask the adapters about extensions and versions; keep no app version list."""
    source_format = format_capabilities(source.suffix, family=family)
    target_format = format_capabilities(target.suffix, family=family)
    if source_format.family != target_format.family:
        raise ValueError("input and output must belong to the same document family")
    return source_format.format, target_format.format, target_format.output_version(version)


def _save_conversion(design, target, *, format, version, context, report):
    """Finish output in memory before creating directories or replacing a file."""
    data = serialize(design, format=format, version=version,
                     context=context, report=report, label=str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return design


def convert(source: Path, target: Path, *, version=None, context=None, report=None):
    """Read once, detect its family, then serialize before touching the output."""
    source, target = Path(source), Path(target)
    require_distinct_paths(source, target)
    design = read(source, report=report)
    _, target_format, version = conversion_formats(source, target, version,
                                                   family=document_family(design))
    return _save_conversion(design, target, format=target_format, version=version,
                            context=context, report=report)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="diptrace_convert", description=__doc__)
    parser.add_argument("input", type=Path, help="design to read; extension selects its format")
    parser.add_argument("output", type=Path, help="design to write; extension selects its format")
    parser.add_argument("--version", type=int, help="destination schema; defaults to the library's output version")
    parser.add_argument("--context", type=Path, help="optional export overrides in JSON")
    parser.add_argument(
        "--windows-fonts", action="store_true",
        help="measure system-font text with the Windows font provider",
    )
    add_report_argument(parser)
    args = parser.parse_args(argv)
    console = Console(args.report_level)

    try:
        require_distinct_paths(args.input, args.output)
        # ASC's family comes from its Source declaration. Unique extensions
        # can be checked early, without loading the input or favoring a family.
        for path in (args.input, args.output):
            if path.suffix.lower() != '.asc':
                format_capabilities(path.suffix)
    except PROCESSING_ERRORS as error:
        parser.error(str(error))

    report = ConversionReport()
    try:
        design = read(args.input, report=report)
    except PROCESSING_ERRORS as error:
        return console.failure("conversion failed", error, report=report)

    try:
        _, target_format, version = conversion_formats(args.input, args.output, args.version,
                                                        family=document_family(design))
        context = load_context(args.context, format=target_format, windows_fonts=args.windows_fonts)
    except PROCESSING_ERRORS as error:
        parser.error(str(error))

    try:
        _save_conversion(design, args.output, format=target_format, version=version,
                         context=context, report=report)
    except PROCESSING_ERRORS as error:
        return console.failure("conversion failed", error, report=report)

    console.report(report)
    console.info(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
