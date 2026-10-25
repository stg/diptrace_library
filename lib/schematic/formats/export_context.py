"""Shared export choices, with destination-specific options kept explicit."""
from dataclasses import MISSING, dataclass, field, fields, replace
from typing import Callable

from ..layout.markings import MarkingStyle, resolve_marking_style
from ...common.text.layout import TextLayout, default_layout
from .export_defaults import default_line_width, display_units
from .path_variables import PathVariables


@dataclass(frozen=True)
class ExportContext:
    """Optional overrides; construct defaults or use dataclasses.replace to customize."""
    units: str | None = None
    project_dir: str | None = None
    marking_style: MarkingStyle | None = None
    grid_snap: bool | None = None
    text_layout: TextLayout = field(default_factory=default_layout)
    use_part_font_color: bool | None = None
    additional_user_fields: tuple = ()
    legacy_picture_files: tuple | None = None
    path_variables: PathVariables | None = None
    refresh_user_fields: bool = False

    def __post_init__(self):
        if self.units is not None and self.units not in ('mm', 'mil', 'in', 'inch'):
            raise ValueError('display units must be mm, mil or in')
        if self.project_dir is not None and not isinstance(self.project_dir, str):
            raise TypeError('project_dir must be text')
        for name in ('grid_snap', 'use_part_font_color'):
            value = getattr(self, name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f'{name} must be a boolean')
        if not isinstance(self.refresh_user_fields, bool):
            raise TypeError('refresh_user_fields must be a boolean')
        if self.marking_style is not None and not isinstance(self.marking_style, MarkingStyle):
            raise TypeError('marking_style must be a MarkingStyle')
        if not isinstance(self.text_layout, TextLayout):
            raise TypeError('text_layout must be a TextLayout')
        if self.path_variables is not None and not isinstance(self.path_variables, PathVariables):
            raise TypeError('path_variables must be a PathVariables configuration')

    def resolved(self, document, *, format=None):
        """Return independent effective common choices for this document."""
        if format is not None:
            destination = format.lower().lstrip('.')
            if destination not in ('dch', 'asc', 'dchxml'):
                raise ValueError(f'unsupported schematic output format: {format!r}')
            return resolve_export_context(self, destination).resolved(document)
        schematic = document.one('/Schematic')
        settings = schematic.one('Settings')
        units = self.units or display_units(document)
        return replace(self, units='in' if units == 'inch' else units,
            project_dir=self.project_dir if self.project_dir is not None else schematic.scalar('ProjectDir', ''),
            marking_style=resolve_marking_style(document, self.marking_style),
            grid_snap=self.grid_snap if self.grid_snap is not None else settings.scalar('GridSnap', True),
            use_part_font_color=self.use_part_font_color if self.use_part_font_color is not None
                                else settings.scalar('UsePartFontColor', False))


@dataclass(frozen=True)
class _RecordExportContext(ExportContext):
    compact_inactive: bool | None = None
    default_main_supplier: bool = False

    def __post_init__(self):
        super().__post_init__()
        if self.compact_inactive is not None and not isinstance(self.compact_inactive, bool):
            raise TypeError('compact_inactive must be a boolean')
        if not isinstance(self.default_main_supplier, bool):
            raise TypeError('default_main_supplier must be a boolean')

@dataclass(frozen=True)
class DchExportContext(_RecordExportContext):
    def resolved(self, document):
        result = super().resolved(document)
        return replace(result, compact_inactive=False if self.compact_inactive is None else self.compact_inactive,
                       grid_snap=None)


@dataclass(frozen=True)
class AscExportContext(_RecordExportContext):
    line_width: Callable[[int], float] | None = None
    legacy_text_slots: tuple | None = None
    encoding: str | None = None

    def __post_init__(self):
        super().__post_init__()
        if self.encoding is not None:
            import codecs
            try:
                codecs.lookup(self.encoding)
                ''.encode(self.encoding)
            except LookupError as error:
                raise ValueError(f'unsupported ASC text encoding: {self.encoding}') from error
        if self.line_width is not None and not callable(self.line_width):
            raise TypeError('line_width must be callable')
        if self.legacy_text_slots is not None and len(self.legacy_text_slots) != 6:
            raise ValueError('legacy text slots require two modes, two alignments and two field names')

    def resolved(self, document):
        result = super().resolved(document)
        return replace(result, compact_inactive=True if self.compact_inactive is None else self.compact_inactive,
                       encoding=self.encoding or 'cp1252',
                       line_width=self.line_width if self.line_width is not None else default_line_width)


@dataclass(frozen=True)
class DchXmlExportContext(ExportContext):
    active_sheet: int | None = None

    def __post_init__(self):
        super().__post_init__()
        if self.active_sheet is not None and (isinstance(self.active_sheet, bool)
                or not isinstance(self.active_sheet, int) or self.active_sheet < 0):
            raise ValueError('active_sheet must be a nonnegative integer')

    def resolved(self, document):
        result = super().resolved(document)
        return replace(result, units='inch' if result.units == 'in' else result.units,
                       active_sheet=self.active_sheet if self.active_sheet is not None
                                    else document.one('/Schematic').get('ActiveSheet', 0))


def resolve_export_context(context, destination):
    """Select destination defaults, refusing unsupported explicit options.

    Common contexts work for every format. Existing specialized contexts also
    transfer when all their non-default options are meaningful to the target.
    """
    target = {'asc': AscExportContext, 'dch': DchExportContext, 'dchxml': DchXmlExportContext}[destination]
    if context is None:
        return target()
    if not isinstance(context, ExportContext):
        raise TypeError('schematic output context must be an ExportContext')
    if destination == 'dch' and context.grid_snap is not None:
        raise ValueError('grid_snap is not stored by DCH output; use a destination that carries this setting')
    names = {item.name for item in fields(target)}
    options = {}
    for item in fields(context):
        value = getattr(context, item.name)
        if item.name in names:
            options[item.name] = value
        elif item.default is MISSING or value != item.default:
            raise ValueError(f'{item.name} is not supported for {destination} output')
    return target(**options)
