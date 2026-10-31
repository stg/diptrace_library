"""Optional PCB export choices and deterministic library fallback settings."""
from dataclasses import dataclass, replace
from decimal import Decimal
import math

from ...common.units import display_units
from ...common.path_variables import PathVariables
from ...common.text.layout import TextLayout, default_layout


@dataclass(frozen=True)
class ExportContext:
    """Stored data wins over fallbacks; units/project_dir are explicit overrides.

    Geometry uses shared length units. The library's fallback grid and line width
    are .1 mm; the fallback sheet is landscape A4. These choices do not claim to
    reproduce any installation's application preferences.
    """
    units: str | None = None
    project_dir: str | None = None
    font_size: int | float | Decimal = 2
    vector_font: bool = True
    grid_size: int | float | Decimal = Decimal('.3')
    line_width: int | float | Decimal = Decimal('.3')
    sheet_size: tuple = (891, 630)
    default_main_supplier: bool = False
    legacy_picture_files: tuple | None = None
    path_variables: PathVariables | None = None
    text_layout: TextLayout | None = None

    def __post_init__(self):
        if self.units is not None:
            object.__setattr__(self, 'units', display_units(self.units))
        if self.project_dir is not None and not isinstance(self.project_dir, str):
            raise TypeError('project_dir must be text')
        if self.path_variables is not None and not isinstance(self.path_variables, PathVariables):
            raise TypeError('path_variables must be a PathVariables configuration')
        if self.text_layout is not None and not isinstance(self.text_layout, TextLayout):
            raise TypeError('PCB text_layout must be a TextLayout')
        for name in ('vector_font', 'default_main_supplier'):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name+' must be a boolean')
        for name in ('font_size', 'grid_size', 'line_width'):
            value = getattr(self, name)
            if type(value) is bool or not isinstance(value, (int, float, Decimal)):
                raise TypeError(name+' must be a number')
            if not math.isfinite(value) or value < 0 or value == 0 and name != 'line_width':
                raise ValueError(name+' must be positive' if name != 'line_width' else name+' must be nonnegative')
        if not isinstance(self.sheet_size, tuple) or len(self.sheet_size) != 2:
            raise TypeError('sheet_size must contain width and height')
        if any(type(value) is bool or not isinstance(value, (int, float, Decimal))
               or not math.isfinite(value) or value <= 0 for value in self.sheet_size):
            raise ValueError('sheet_size requires two positive numbers')

    def resolved(self, document, *, format=None):
        """Return independent effective choices, optionally checking the target."""
        if format is not None and format.lower().lstrip('.') not in ('dip', 'asc', 'dipxml'):
            raise ValueError(f'unsupported PCB output format: {format!r}')
        board = document.one('/Board')
        return replace(self, units=self.units or document.root.get('Units', 'mm'),
                       project_dir=self.project_dir if self.project_dir is not None else board.get('ProjectDir', ''))

    @property
    def layout(self):
        return self.text_layout or default_layout()


def resolve_export_context(context):
    if context is None:
        return ExportContext()
    if not isinstance(context, ExportContext):
        raise TypeError('PCB output context must be an ExportContext')
    return context
