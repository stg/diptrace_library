"""Small optional I/O settings shared by standalone library families."""
import codecs
from dataclasses import dataclass
import math
from decimal import Decimal

from .text.layout import TextLayout
from .units import display_units


@dataclass(frozen=True)
class ImportContext:
    """Code page for narrow strings in binary libraries.

    ASC byte encoding can be supplied to read/parse; XML declares its own.
    Imports need no installation preferences or companion files.
    """
    ansi_encoding: str = 'cp1252'

    def __post_init__(self):
        if not isinstance(self.ansi_encoding,str):
            raise TypeError('ansi_encoding must be text')
        object.__setattr__(self,'ansi_encoding',codecs.lookup(self.ansi_encoding).name)


@dataclass(frozen=True)
class ExportContext:
    """Optional output units and calculation settings.

    line_width is a shared-length value or a function of the layer number,
    used only for drawings which request the receiver's default pen. A supplied
    TextLayout overrides receiver metrics, including calculated group centres in
    every format. target_application selects ASC
    receiver conventions; it does not change the document or the ASC dialect.
    """
    units: str = 'mm'
    line_width: object = .3
    text_layout: TextLayout | None = None
    target_application: str | None = None

    def __post_init__(self):
        object.__setattr__(self,'units',display_units(self.units))
        if not callable(self.line_width):
            if type(self.line_width) is bool or not isinstance(self.line_width,(int,float,Decimal)):
                raise TypeError('line_width must be a number or layer callback')
            if not math.isfinite(self.line_width) or self.line_width < 0:
                raise ValueError('line_width must be finite and nonnegative')
        if self.text_layout is not None and not isinstance(self.text_layout,TextLayout):
            raise TypeError('text_layout must be a TextLayout')
        if self.target_application is not None and not isinstance(self.target_application,str):
            raise TypeError('target_application must be text or None')

    def pen(self,layer):
        return self.line_width(layer) if callable(self.line_width) else self.line_width


def import_context(context):
    if context is None:
        return ImportContext()
    if not isinstance(context,ImportContext):
        raise TypeError('library input context must be an ImportContext')
    return context


def export_context(context):
    if context is None:
        return ExportContext()
    if not isinstance(context,ExportContext):
        raise TypeError('library output context must be an ExportContext')
    return context
