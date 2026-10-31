"""PCB display and check settings, separate from physical board geometry."""
from ...common.schema import Child, Field, Record
from .routing_defaults import ROUTING


def _fields(kind, names, *, unit=''):
    return {name: Field(name, kind, unit=unit) for name in names.split()}


LAYER_PANEL = Record('PcbLayerPanel', _fields('boolean',
    'TopAssy TopMask TopPaste BotAssy BotMask BotPaste Board '
    'TopTerminals BotTerminals TopCourtyard BotCourtyard TopOutline BotOutline '
    'TopDimensions BotDimensions'))

SETTINGS = Record('PcbSettings', {
    **_fields('boolean', 'GridEnabled GridSnap YGridIdentical OriginEnabled FlipTextAuto AssyPads '
                         'AssySilk AssyPatBorders AssyBoardOutline EditInactiveLayer StackLength '
                         'SignalDelayLength ShowCompFiducials'),
    **_fields('integer', 'AxisColor JumperLayer LayerDisplayMode'),
    **_fields('number', 'GridSize YGridSize SilkLineWidth TableLineWidth TitlesLineWidth '
                        'BoardOutlineWidth AssemblyWidth CompOutlineWidth CourtyardWidth '
                        'SolderMaskSwell PasteMaskShrink', unit='shared length'),
}, children={
    'Routing': Child('Routing', ROUTING.name),
    'LayerPanel': Child('LayerPanel', LAYER_PANEL.name),
})

CONNECTIVITY = Record('PcbConnectivityCheck', _fields('boolean', 'Traces Shapes CopperPours'))

SHEET = Record('PcbSheetSettings', {
    **_fields('number', 'SheetWidth SheetHeight LeftMargin TopMargin RightMargin BottomMargin',
              unit='shared length'),
    **_fields('boolean', 'DisplayTitles DisplaySheet'),
}, children={'BorderZones': Child('BorderZones', 'PcbBorderZones'),
             'TitleBlocks': Child('TitleBlocks', 'PcbTitleBlocks')})

BORDER_ZONES = Record('PcbBorderZones', {
    **_fields('boolean', 'Visible Border'),
    **_fields('integer', 'HorzZones VertZones Standard'),
    **_fields('text', 'FontName'),
    **_fields('number', 'FontSize'),
    **_fields('number', 'HorzBorderSize VertBorderSize FontLineWidth', unit='shared length'),
})


def definition(node):
    parent = node.parent
    if parent is None:
        return None
    if parent.kind == 'Board':
        return {'Settings': SETTINGS, 'ConnectivityCheck': CONNECTIVITY,
                'SheetSettings': SHEET}.get(node.kind)
    if (parent.schema is SETTINGS or parent.kind == 'Settings' and
            parent.parent is not None and parent.parent.kind == 'Board'):
        return LAYER_PANEL if node.kind == 'LayerPanel' else None
    if (parent.kind == 'SheetSettings' and parent.parent is not None and
            parent.parent.kind == 'Board' and node.kind == 'BorderZones'):
        return BORDER_ZONES
    return None


def bind_records(board):
    """Bind settings branches without scanning all placed board geometry.

    Routing aliases are established later, after the default class is bound
    and the duplicated binary defaults have been consumed.
    """
    for branch in (*board.select('Settings'), *board.select('ConnectivityCheck'),
                   *board.select('SheetSettings')):
        for node in branch.walk(include_self=True):
            if (schema := definition(node)) is not None:
                node.bind_schema(schema)
