"""Translate optional JSON settings into library export configuration."""
import json
import math
from pathlib import Path

from lib import PathVariables
from lib.common.text.markings import MarkingStyle
from lib.common.text.layout import TextLayout


def _text_layout(settings: dict, windows_fonts: bool) -> TextLayout:
    if not isinstance(settings, dict):
        raise ValueError("text_layout must be a JSON object")
    unknown = settings.keys() - {"dpi", "font_scale"}
    if unknown:
        raise ValueError(f"unknown text layout settings: {sorted(unknown)}")
    measure = None
    if windows_fonts:
        # The optional host provider stays out of the ordinary import path.
        from lib.common.text.windows import WindowsFontMetrics
        measure = WindowsFontMetrics(dpi=settings.get("dpi", 96)).measure
    return TextLayout(measure, font_scale=settings.get("font_scale", 1))


def _line_widths(widths: dict, fallback):
    if not isinstance(widths, dict):
        raise ValueError("line_widths must be a JSON object")
    widths = {int(layer): float(width) for layer, width in widths.items()}
    fallback = float(fallback) if fallback is not None else None
    numbers = list(widths.values()) + ([] if fallback is None else [fallback])
    if any(not math.isfinite(width) for width in numbers):
        raise ValueError("line widths must be finite numbers")

    def line_width(layer):
        if layer in widths:
            return widths[layer]
        if fallback is None:
            raise ValueError(f"no fallback line width configured for layer {layer}")
        return fallback

    return line_width


def load_context(path: Path | None = None, *, format: str, family: str, windows_fonts=False):
    """Choose the detected family's context; absent configuration stays optional."""
    from importlib import import_module
    from lib import format_capabilities
    from lib.common.document_families import family_name

    family = family_name(family)
    format_capabilities(format, family=family)
    if path is None and not windows_fonts:
        return None
    settings = json.loads(Path(path).read_text(encoding="utf-8")) if path is not None else {}
    if not isinstance(settings, dict):
        raise ValueError("export context must be a JSON object")

    if settings.get("marking_style") is not None:
        if family != 'schematic':
            raise ValueError('marking_style is a schematic export setting')
        if not isinstance(settings['marking_style'], dict):
            raise ValueError('marking_style must be a JSON object')
        settings['marking_style'] = MarkingStyle(**settings['marking_style'])
    if settings.get('path_variables') is not None:
        if not isinstance(settings['path_variables'], dict):
            raise ValueError('path_variables must be a JSON object')
        settings['path_variables'] = PathVariables(**settings['path_variables'])
    if 'text_layout' in settings or windows_fonts:
        settings['text_layout'] = _text_layout(settings.get('text_layout', {}), windows_fonts)
    widths = settings.pop('line_widths', {})
    fallback = settings.pop('default_line_width', None)
    if not isinstance(widths, dict):
        raise ValueError('line_widths must be a JSON object')
    if widths or fallback is not None:
        if family != 'schematic':
            raise ValueError('line_widths is a schematic ASC export setting')
        settings['line_width'] = _line_widths(widths, fallback)

    package = import_module('lib.'+family)
    if family == 'schematic':
        constructor = {'asc': package.AscExportContext, 'dch': package.DchExportContext,
                       'dchxml': package.DchXmlExportContext}[format]
    else:
        constructor = package.ExportContext
    return constructor(**settings)
