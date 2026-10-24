"""Convert any supported schematic input using optional settings and reports."""
import argparse
from dataclasses import replace
from pathlib import Path

from lib import ConversionReport, ExportContext, read, write


def convert(source, destination, *, version=52, units=None):
    report = ConversionReport()
    design = read(source, report=report)
    kind = Path(destination).suffix.lower().lstrip('.')
    defaults = ExportContext().resolved(design, format=kind)
    context = replace(defaults, units=units) if units is not None else defaults
    options = {} if kind == 'asc' else {'version': version}
    write(design, destination, context=context, report=report, **options)
    for notice in report.notices:
        print(notice.severity, notice.operation, notice.format, notice.message)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('output')
    parser.add_argument('--version', type=int, default=52)
    parser.add_argument('--units', choices=('mm', 'mil', 'inch'))
    args = parser.parse_args()
    convert(args.input, args.output, version=args.version, units=args.units)
