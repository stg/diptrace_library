"""Check one design by saving, reopening and repeating the selected formats."""
import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

from lib import ConversionReport, document_family, format_capabilities, input_identity, parse, read, serialize
from apps.common.cli import Console, PROCESSING_ERRORS, add_report_argument
from apps.common.paths import require_distinct_paths
from .comparison import compare, snapshot


class CheckOptionsError(ValueError):
    """The selected output format/version is an invalid command option."""


def nonnegative(value):
    try:
        number = Decimal(value)
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError('expected a finite nonnegative number') from error
    if not number.is_finite() or number < 0:
        raise argparse.ArgumentTypeError('expected a finite nonnegative number')
    return number


def check_file(source, *, formats=None, version=None, cycles=3,
               tolerance=Decimal('.0005'), drift_tolerance=Decimal('1e-9'), report=None):
    """Return measurements and notices; never rewrite the supplied design.

    A lane is model -> selected serialization -> model. Further saves test that
    its first output has stabilized; their changes use the stricter drift limit.
    Family availability and version support come exclusively from the library.
    """
    if cycles < 2:
        raise ValueError('at least two cycles are required')
    if tolerance < 0 or drift_tolerance < 0:
        raise ValueError('comparison tolerances must be nonnegative')
    source = Path(source)
    report = report if report is not None else ConversionReport()
    original = read(source, report=report)
    original.references.validate()
    family = document_family(original)
    formats = tuple(dict.fromkeys(formats or (input_identity(source.read_bytes()).format,)))
    if None in formats:
        raise ValueError('could not identify an output format; supply --format')
    if version is not None and len(formats) != 1:
        raise ValueError('--version requires exactly one format')
    baseline = snapshot(original)
    lanes = []
    for format in formats:
        try:
            capabilities = format_capabilities(format, family=family)
            format, selected_version = capabilities.format, capabilities.output_version(version)
        except (ValueError, NotImplementedError) as error:
            raise CheckOptionsError(str(error)) from error
        current, previous, first = original, baseline, None
        steps = []
        for cycle in range(1, cycles+1):
            data = serialize(current, format=format, version=selected_version, report=report,
                             label=f'{format} cycle {cycle}')
            if snapshot(current) != previous:
                raise ValueError(f'{format}: saving modified the source model')
            rebuilt = parse(data, format=format, report=report, label=f'{format} cycle {cycle}')
            rebuilt.references.validate()
            actual = snapshot(rebuilt)
            initial = compare(baseline, actual, tolerance=tolerance) if cycle == 1 else None
            if first is None:
                first = actual
            # Compare every later cycle to the FIRST output, so individually
            # small movements cannot hide an accumulating change.
            stability = compare(first, actual, tolerance=drift_tolerance)
            steps.append(dict(cycle=cycle, bytes=len(data), initial=initial, stability=stability))
            current, previous = rebuilt, actual
        unstable = any(step['stability']['needs_review'] for step in steps[1:])
        review = steps[0]['initial']['needs_review']
        rounding = any(steps[0]['initial']['counts'].values())
        lanes.append(dict(format=format, version=selected_version, cycles=steps,
                          status='drift' if unstable else 'review' if review else 'rounding' if rounding else 'clean'))
    return dict(input=str(source), family=family, tolerance=tolerance,
                drift_tolerance=drift_tolerance, results=lanes,
                needs_review=any(lane['status'] in ('review', 'drift') for lane in lanes)), report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='diptrace_check', description=__doc__)
    parser.add_argument('input', type=Path, help='design to read; content identifies its family and format')
    parser.add_argument('--format', action='append', dest='formats', help='format to exercise; repeat for multiple formats (default: input format)')
    parser.add_argument('--version', type=int, help='output schema for one selected format; default: library output version')
    parser.add_argument('--cycles', type=int, default=3, help='save/reopen cycles, at least 2 (default: 3)')
    parser.add_argument('--tolerance', type=nonnegative, default=Decimal('.0005'), help='initial numerical review threshold in model units (default: 0.0005)')
    parser.add_argument('--drift-tolerance', type=nonnegative, default=Decimal('1e-9'), help='numerical stability threshold after the first output (default: 1e-9)')
    parser.add_argument('--json', type=Path, dest='output', help='write the detailed results and conversion notices as JSON')
    add_report_argument(parser)
    args = parser.parse_args(argv)
    if args.cycles < 2:
        parser.error('--cycles must be at least 2')
    if args.version is not None and args.formats is not None and len(set(args.formats)) != 1:
        parser.error('--version requires exactly one format')
    if args.output is not None:
        try:
            require_distinct_paths(args.input, args.output)
        except PROCESSING_ERRORS as error:
            parser.error(str(error))
    console = Console(args.report_level)
    report = ConversionReport()
    try:
        result, report = check_file(args.input, formats=args.formats, version=args.version,
            cycles=args.cycles, tolerance=args.tolerance, drift_tolerance=args.drift_tolerance, report=report)
        console.report(report)
        if args.output is not None:
            result['notices'] = [dict(operation=n.operation, severity=n.severity, rule=n.rule,
                                      message=n.message, paths=n.paths) for n in report.notices]
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2, default=str)+'\n', encoding='utf-8')
            console.info(f'Wrote {args.output}')
        for lane in result['results']:
            console.info(f"{lane['format'].upper()} schema {lane['version']}: {lane['status']} ({args.cycles} cycles)")
            for step in lane['cycles']:
                comparison = step['initial'] if step['cycle'] == 1 else step['stability']
                if comparison['counts']:
                    maxima = comparison['maximum_numeric_delta_by_unit']
                    detail = '; numeric maxima: '+', '.join(f'{value} {unit}' for unit, value in maxima.items()) if maxima else ''
                    counts = ', '.join(f'{count} {name}' for name, count in comparison['counts'].items())
                    console.info(f"  cycle {step['cycle']}: {counts}{detail}")
                    for example in comparison['examples'][:3]:
                        console.diagnostic('warning' if comparison['needs_review'] else 'info',
                            f"{example['kind']}: {example['path']}"+
                            (f" (delta {example['delta']} {example['unit'] or 'model units'})" if example['delta'] is not None else ''))
        return int(result['needs_review'])
    except CheckOptionsError as error:
        parser.error(str(error))
    except PROCESSING_ERRORS as error:
        return console.failure('check failed', error, report=report)


if __name__ == '__main__':
    raise SystemExit(main())
