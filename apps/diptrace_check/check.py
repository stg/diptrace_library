"""Check design conversions against supplied exports and repeated saves."""
import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

from lib import ConversionReport, document_family, format_capabilities, input_identity, parse, read, serialize
from apps.common.cli import Console, PROCESSING_ERRORS, add_report_argument, version_argument
from apps.common.paths import require_distinct_paths
from .comparison import compare, snapshot
from .reference import Reference


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


def check_file(source, *, formats=None, version=None, cycles=3, references=None,
               tolerance=Decimal('.0005'), drift_tolerance=Decimal('1e-9'),
               reference_tolerance=Decimal(0), report=None):
    """Return measurements and notices; never rewrite the supplied design.

    A lane is model -> selected serialization -> model. Further saves test that
    its first output has stabilized; their changes use the stricter drift limit.
    Family availability and version support come exclusively from the library.
    """
    if cycles < 2:
        raise ValueError('at least two cycles are required')
    if tolerance < 0 or drift_tolerance < 0 or reference_tolerance < 0:
        raise ValueError('comparison tolerances must be nonnegative')
    source = Path(source)
    report = report if report is not None else ConversionReport()
    original = read(source, report=report)
    original.references.validate()
    family = document_family(original)
    supplied = [Reference.load(path, family=family, version=version)
                for path in dict.fromkeys(references or ())]
    requested = [*(formats or (input_identity(source.read_bytes()).format,)),
                 *(item.format for item in supplied)]
    if None in requested:
        raise ValueError('could not identify an output format; supply --format')
    formats = {}
    for format in requested:
        try:
            capabilities = format_capabilities(format, family=family)
        except (ValueError, NotImplementedError) as error:
            raise CheckOptionsError(str(error)) from error
        formats[capabilities.format] = capabilities
    if version is not None and len(formats) != 1:
        raise CheckOptionsError('--version requires exactly one format, including references')
    baseline = snapshot(original)
    lanes = []
    for format, capabilities in formats.items():
        try:
            selected_version = capabilities.output_version(version)
        except ValueError as error:
            raise CheckOptionsError(str(error)) from error
        groups = {}
        for item in supplied:
            if item.format == format:
                groups.setdefault((item.version, item.units), []).append(item)
        if not groups:
            groups[selected_version, None] = []
        for (target_version, units), paired in groups.items():
            context = paired[0].context(family) if paired else None
            current, previous, first = original, baseline, None
            steps, comparisons = [], []
            for cycle in range(1, cycles+1):
                data = serialize(current, format=format, version=target_version, context=context,
                                 report=report, label=f'{format} cycle {cycle}')
                if snapshot(current) != previous:
                    raise ValueError(f'{format}: saving modified the source model')
                rebuilt = parse(data, format=format, report=report, label=f'{format} cycle {cycle}')
                rebuilt.references.validate()
                actual = snapshot(rebuilt)
                initial = compare(baseline, actual, tolerance=tolerance) if cycle == 1 else None
                if first is None:
                    first = actual
                    comparisons = [item.check(data, actual=actual, family=family, tolerance=tolerance,
                        source_tolerance=reference_tolerance, report=report) for item in paired]
                # Compare later cycles to the FIRST output, so individually
                # small movements cannot hide an accumulating change.
                stability = compare(first, actual, tolerance=drift_tolerance)
                steps.append(dict(cycle=cycle, bytes=len(data), initial=initial, stability=stability))
                current, previous = rebuilt, actual
            unstable = any(step['stability']['needs_review'] for step in steps[1:])
            review = steps[0]['initial']['needs_review']
            rounding = any(steps[0]['initial']['counts'].values())
            lanes.append(dict(format=format, version=target_version, cycles=steps,
                              references=comparisons,
                              status='drift' if unstable else 'review' if review else 'rounding' if rounding else 'clean'))
    return dict(input=str(source), family=family, tolerance=tolerance,
                drift_tolerance=drift_tolerance, reference_tolerance=reference_tolerance, results=lanes,
                needs_review=any(lane['status'] in ('review', 'drift') or
                    any(item['status'] == 'review' for item in lane['references']) for lane in lanes)), report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='diptrace_check', description=__doc__)
    parser.add_argument('input', type=Path, help='design to read; content identifies its family and format')
    parser.add_argument('--format', action='append', dest='formats', help='format to exercise; repeat for multiple formats (default: input and reference formats)')
    parser.add_argument('--reference', action='append', type=Path, default=[],
                        help='matching ASC/XML export from DipTrace; repeat for multiple references')
    parser.add_argument('--version', type=version_argument,
                        help='output schema or application version for one format; default: reference version or library output version')
    parser.add_argument('--cycles', type=int, default=3, help='save/reopen cycles, at least 2 (default: 3)')
    parser.add_argument('--tolerance', type=nonnegative, default=Decimal('.0005'), help='initial numerical review threshold in model units (default: 0.0005)')
    parser.add_argument('--drift-tolerance', type=nonnegative, default=Decimal('1e-9'), help='numerical stability threshold after the first output (default: 1e-9)')
    parser.add_argument('--reference-tolerance', type=nonnegative, default=Decimal(0),
                        help='direct numerical comparison threshold in serialized units (default: exact)')
    parser.add_argument('--json', type=Path, dest='output', help='write the detailed results and conversion notices as JSON')
    add_report_argument(parser)
    args = parser.parse_args(argv)
    if args.cycles < 2:
        parser.error('--cycles must be at least 2')
    if args.version is not None and args.formats is not None and len({f.lower().lstrip('.') for f in args.formats}) != 1:
        parser.error('--version requires exactly one format')
    if args.output is not None:
        try:
            require_distinct_paths(args.input, args.output)
            for reference in args.reference:
                require_distinct_paths(reference, args.output)
        except PROCESSING_ERRORS as error:
            parser.error(str(error))
    console = Console(args.report_level)
    report = ConversionReport()
    try:
        result, report = check_file(args.input, formats=args.formats, version=args.version,
            cycles=args.cycles, references=args.reference, tolerance=args.tolerance,
            drift_tolerance=args.drift_tolerance, reference_tolerance=args.reference_tolerance, report=report)
        console.report(report)
        if args.output is not None:
            result['notices'] = [dict(operation=n.operation, severity=n.severity, rule=n.rule,
                                      message=n.message, paths=n.paths) for n in report.notices]
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2, default=str)+'\n', encoding='utf-8')
            console.info(f'Wrote {args.output}')
        for lane in result['results']:
            console.info(f"{lane['format'].upper()} schema {lane['version']}: {lane['status']} ({args.cycles} cycles)")
            for reference in lane['references']:
                console.info(f"  reference {reference['path']}: {reference['status']}")
                if reference['model_error']:
                    console.diagnostic('error', reference['model_error'])
                for name in ('model', 'serialized'):
                    if reference[name] is not None:
                        show_comparison(reference[name], console, label=name)
            for step in lane['cycles']:
                comparison = step['initial'] if step['cycle'] == 1 else step['stability']
                show_comparison(comparison, console, label=f"cycle {step['cycle']}")
        return int(result['needs_review'])
    except CheckOptionsError as error:
        parser.error(str(error))
    except PROCESSING_ERRORS as error:
        return console.failure('check failed', error, report=report)


def show_comparison(comparison, console, *, label):
    if not comparison['counts']:
        return
    maxima = comparison['maximum_numeric_delta_by_unit']
    detail = '; numeric maxima: '+', '.join(f'{value} {unit}' for unit, value in maxima.items()) if maxima else ''
    counts = ', '.join(f'{count} {name}' for name, count in comparison['counts'].items())
    console.info(f'  {label}: {counts}{detail}')
    for example in comparison['examples'][:3]:
        console.diagnostic('warning' if comparison['needs_review'] else 'info',
            f"{example['kind']}: {example['path']}"+
            (f" (delta {example['delta']} {example['unit'] or 'model units'})" if example['delta'] is not None else ''))


if __name__ == '__main__':
    raise SystemExit(main())
