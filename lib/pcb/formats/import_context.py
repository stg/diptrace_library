"""Optional environment defaults for importing PCB data."""
from dataclasses import dataclass

from ...common.units import DISPLAY_UNITS, display_units
from ...common.text.layout import TextLayout, default_layout


@dataclass(frozen=True)
class ImportContext:
    """Display-unit fallback, text measurements and optional canvas environment.

    A stored selection takes precedence. This choice affects display and text
    projection; imported geometry always uses the model's shared length units.
    A black canvas is the standard fallback for drawing-color visibility
    normalization. Set background_color=None to retain authored colors.
    Absent a stored choice, common component fiducials contribute to footprint
    bounds by default; show_component_fiducials overrides that fallback.
    """
    units: str = 'mm'
    text_layout: TextLayout | None = None
    background_color: int | None = 0
    show_component_fiducials: bool = True

    def __post_init__(self):
        object.__setattr__(self, 'units', display_units(self.units))
        if self.text_layout is not None and not isinstance(self.text_layout, TextLayout):
            raise TypeError('PCB text_layout must be a TextLayout')
        if type(self.show_component_fiducials) is not bool:
            raise TypeError('PCB show_component_fiducials must be a Boolean')
        if self.background_color is not None:
            if type(self.background_color) is not int:
                raise TypeError('PCB background_color must be an integer or None')
            if not 0 <= self.background_color <= 0xFFFFFF:
                raise ValueError('PCB background_color must be a 24-bit design color')

    @property
    def layout(self):
        return self.text_layout or default_layout()


def resolve_import_context(context):
    if context is None:
        return ImportContext()
    if not isinstance(context, ImportContext):
        raise TypeError('PCB input context must be an ImportContext')
    return context


def resolved_units(root, choices, context):
    """Use a stored unit, then saved switch choices, then the environment default."""
    if root.child('Units') is not None:
        return display_units(root.scalar('Units'))
    return next((unit for unit, selected in reversed(tuple(zip(DISPLAY_UNITS, choices)))
                 if selected), context.units)
