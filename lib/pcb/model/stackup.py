"""Construct standard stackup data when an input has no material stack.

Dimensions below use millimetres; the model uses shared length units. The
construction describes alternating copper and insulation, without a second
copy of the copper-layer order or conductor/plane classification.

The material choices are observable by selecting standard multilayer stackups
and exporting the material stack. Millimetres avoid a second unit convention;
for example, 1.37 mil of copper is 1.37 * .0254 = .034798 mm.
"""
from dataclasses import dataclass
from decimal import Decimal

from ...common.model import Element
from . import board_rules


@dataclass(frozen=True)
class Material:
    name: str
    thickness: Decimal
    constant: Decimal
    variable: bool = False
    trace_width: Decimal = Decimal(0)


RESIST = Material('Solder Resist', Decimal('.01'), Decimal('3.5'), True)
COPPER = Material('Copper 1 Oz', Decimal('.034798'), Decimal(0), trace_width=Decimal('.2'))
PREPREG = {
    '106': Material('Prepreg 106', Decimal('.05'), Decimal('4.6')),
    '1080': Material('Prepreg 1080', Decimal('.078'), Decimal('4.6')),
    '2113': Material('Prepreg 2113', Decimal('.102'), Decimal('4.6')),
}
# Standard choices are indexed by the template's copper-layer count. Their
# repeated copper/insulation arrangement is generated below rather than stored.
CORE_THICKNESS = {2: '1.5', 4: '1', 6: '.3', 8: '.25', 10: '.15', 12: '.1', 14: '.1', 16: '.1'}
PREPREG_CHOICE = {4: '2113', 6: '2113', 8: '1080', 10: '1080', 12: '106', 14: '106', 16: '106'}


@dataclass(frozen=True)
class StackupProposal:
    name: str
    items: Element
    copper_layers: tuple


def default_stackup(layers):
    """Return detached material records and their proposed copper identities.

    The import stage attaches the records and binds their links. Select the
    next standard template, or the largest one when the stack exceeds them.
    Its alternating insulation arrangement extends to the requested count.
    """
    layers = tuple(layers)
    count = len(layers)
    items = Element('LayerStackItems').bind_schema(board_rules.COLLECTIONS['LayerStackItems'])
    if count == 0:
        return StackupProposal('', items, ())
    template = next((size for size in CORE_THICKNESS if size >= count), max(CORE_THICKNESS))
    core = Material('FR-4', Decimal(CORE_THICKNESS[template]), Decimal('4.6'), True)
    links = []

    def add(material, layer=None):
        item = items.add('LayerStackItem').bind_schema(board_rules.STACK_ITEM)
        record = item.add('Material').bind_schema(board_rules.MATERIAL)
        for name, value in (
            ('Name', material.name), ('VariableThickness', material.variable),
            ('Thickness', material.thickness*3), ('Constant', material.constant),
            ('TraceWidth', material.trace_width*3),
        ):
            record.add(name, value)
        if layer is not None:
            links.append((item, layer))

    add(RESIST)
    for index, layer in enumerate(layers):
        add(COPPER, layer)
        if index == count-1:
            continue
        if template == 2 or index % 2:
            add(core)
        else:
            insulation = PREPREG[PREPREG_CHOICE[template]]
            add(insulation)
            add(insulation)
    add(RESIST)
    return StackupProposal(f'{template} Layers Default Stackup', items, tuple(links))
