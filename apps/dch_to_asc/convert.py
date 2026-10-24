"""Complete schematic ASC output through the owned design library."""
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import AscExportContext, PathVariables, read
from lib.schematic.layout.markings import (MarkingStyle)
from lib.schematic.layout.text_layout import (TextLayout)


def load_context(path=None, *, windows_fonts=False):
    """Load explicit export choices; no reference schematic or app state is read."""
    settings = json.loads(Path(path).read_text(encoding='utf-8')) if path is not None else {}
    if not isinstance(settings, dict):
        raise ValueError('export context must be a JSON object')
    style_settings = settings.pop('marking_style', None)
    style = MarkingStyle(**style_settings) if style_settings is not None else None
    paths = settings.pop('path_variables', None)
    if paths is not None:
        settings['path_variables'] = PathVariables(**paths)
    layout = settings.pop('text_layout', {})
    if not isinstance(layout, dict):
        raise ValueError('text_layout must be a JSON object')
    unknown = layout.keys()-{'dpi', 'font_scale'}
    if unknown:
        raise ValueError(f'unknown text layout settings: {sorted(unknown)}')
    measure = None
    if windows_fonts:
        from lib.common.text.windows import (WindowsFontMetrics)
        measure = WindowsFontMetrics(dpi=layout.get('dpi', 96)).measure
    settings['text_layout'] = TextLayout(measure, font_scale=layout.get('font_scale', 1))
    widths = settings.pop('line_widths', {})
    if not isinstance(widths, dict):
        raise ValueError('line_widths must be a JSON object')
    fallback = settings.pop('default_line_width', None)
    if widths or fallback is not None:
        widths = {int(layer): float(width) for layer, width in widths.items()}
        if any(not math.isfinite(width) for width in widths.values()) or fallback is not None and not math.isfinite(fallback):
            raise ValueError('line widths must be finite numbers')
        def line_width(layer):
            if layer in widths:
                return widths[layer]
            if fallback is None:
                raise ValueError(f'no fallback line width configured for layer {layer}')
            return fallback
        settings['line_width'] = line_width
    settings['marking_style'] = style
    return AscExportContext(**settings)


def convert(input_dch, output_asc, *, context=None):
    if Path(input_dch).resolve() == Path(output_asc).resolve():
        raise ValueError('input and output paths must differ')
    source = read(input_dch, format='dch')
    public = source.as_asc(context=context)
    # Finish conversion/validation before touching an existing output file.
    data = public.to_asc_bytes(preserve=False)
    output = Path(output_asc)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return public


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_dch', type=Path)
    parser.add_argument('output_asc', type=Path)
    parser.add_argument('--context', type=Path, help='optional export overrides in JSON')
    parser.add_argument('--windows-fonts', action='store_true', help='measure system-font text with the host font provider')
    args = parser.parse_args(argv)
    try:
        context = load_context(args.context, windows_fonts=args.windows_fonts)
        public = convert(args.input_dch, args.output_asc, context=context)
    except (ValueError, TypeError, LookupError, OSError, NotImplementedError) as error:
        parser.exit(2, f'conversion failed: {error}\n')
    print(f'wrote={args.output_asc} parts={len(public.select("/Schematic/Components/Part"))} '
          f'nets={len(public.select("/Schematic/Nets/Net"))}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

