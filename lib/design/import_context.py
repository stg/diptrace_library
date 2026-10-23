"""Optional environment inputs for modernizing older schematic data."""
from dataclasses import dataclass
from .text_layout import TextLayout, default_layout


@dataclass(frozen=True)
class ImportContext:
    """Defaults for font settings absent from older files and a layout service.

    Stored settings take precedence. font_name supplies the environment family
    for legacy placement; it does not replace a stored drawing's font family.
    Vector layout is self-contained. A missing system-font provider uses the
    optional Windows backend lazily, only when a placement needs measurement.
    Other environments can supply TextLayout(measure_system=...).
    """
    font_size: int = 2
    font_name: str = ''
    text_layout: TextLayout | None = None

    def __post_init__(self):
        if isinstance(self.font_size, bool) or not isinstance(self.font_size, int) or self.font_size <= 0:
            raise ValueError('import font_size must be a positive integer')
        if not isinstance(self.font_name, str):
            raise TypeError('import font_name must be text')
        if self.text_layout is not None and not isinstance(self.text_layout, TextLayout):
            raise TypeError('import text_layout must be a TextLayout')

    @property
    def layout(self):
        return self.text_layout or default_layout()


def resolve_import_context(context):
    if context is None:
        return ImportContext()
    if not isinstance(context, ImportContext):
        raise TypeError('schematic input context must be an ImportContext')
    return context


def modernize_font_settings(schematic, context):
    """Make missing old settings ordinary current document properties."""
    settings = schematic.one('Settings')
    for name, value in (('PartFontSize', context.font_size), ('PartFontColor', 0),
                        ('UsePartFontColor', False)):
        if settings.child(name) is None:
            settings.add(name, value)
