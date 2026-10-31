"""PCB display, marking and routing preferences from public XML groups."""
from ....common.xml_records import enum_value, length, point
from ....common.xml_font_import import read_size
from ....common.xml_library_values import read_path
from ...model import markings
from ...model.settings_records import LAYER_PANEL
from .components import SHOW, ALIGN


def _fields(record, target, names, *, kind='number', units=None):
    for public, own in names.items():
        if record.has(public):
            value = getattr(record, kind)(public)
            target.add(own, length(value, units) if units is not None else value)


def _markings(record, board):
    _fields(record, board, {'CompRotate': 'CompRotate', 'FontVector': 'PatternFontVector',
                           'FontMono': 'CompFontMono'}, kind='boolean')
    _fields(record, board, {'FontName': 'CompFontName'}, kind='text')
    if record.has('FontSize') or record.has('FontSizeFloat'):
        board.add('CompFontSize', read_size(record))
    # PCB global marking width is a font setting, independent of the display
    # length selection. Zone/text stroke dimensions have their own mapping.
    _fields(record, board, {'FontWidth': 'PatternFontWidth', 'FontScale': 'PatternFontScale'})
    for name in markings.NAMES:
        source = record.take(name+'Global')
        if source is None:
            continue
        for side in markings.SIDES:
            for field, labels in (('Show', SHOW), ('Align', ALIGN)):
                board.add(name+'_Global_'+side+field, enum_value(source.value(side+field, labels[0]), labels))
        source.finish()
    fields = board.add('Userfields_Global')
    for source in record.rows('AddFieldsGlobal', 'AddField'):
        field = fields.add('UserField')
        field.add('Name', source.text('Name', ''))
        for side in markings.SIDES:
            for name, labels in (('Show', SHOW), ('Align', ALIGN)):
                field.add(side+name, enum_value(source.value(side+name, labels[0]), labels))
        source.finish()
    record.finish()


def read_settings(record, board, *, units):
    if record is None:
        return
    settings = board.add('Settings')
    group = record.take('Markings')
    if group is not None:
        _markings(group, board)
    group = record.take('Grid')
    if group is not None:
        _fields(group, settings, {'Visible': 'GridEnabled', 'Snap': 'GridSnap',
                                 'YIdentical': 'YGridIdentical'}, kind='boolean')
        _fields(group, settings, {'Size': 'GridSize', 'YSize': 'YGridSize'}, units=units)
        group.finish()
    group = record.take('Origin')
    if group is not None:
        _fields(group, settings, {'Visible': 'OriginEnabled'}, kind='boolean')
        _fields(group, settings, {'AxisColor': 'AxisColor'}, kind='integer')
        for axis, value in zip(('OriginX', 'OriginY'), point(group, units, default=0)):
            board.add(axis, value)
        group.finish()
    group = record.take('Assembly')
    if group is not None:
        _fields(group, settings, {'Pads': 'AssyPads', 'Silk': 'AssySilk',
                                 'CompBorders': 'AssyPatBorders', 'BoardOutline': 'AssyBoardOutline'}, kind='boolean')
        group.finish()
    group = record.take('LineWidth')
    if group is not None:
        _fields(group, settings, {'Silk': 'SilkLineWidth', 'Table': 'TableLineWidth',
            'Titles': 'TitlesLineWidth', 'BoardOutline': 'BoardOutlineWidth', 'Assembly': 'AssemblyWidth',
            'CompOutline': 'CompOutlineWidth', 'Courtyard': 'CourtyardWidth'}, units=units)
        group.finish()
    group = record.take('Routing')
    if group is not None:
        routing = settings.add('Routing')
        if group.has('Router'):
            routing.add('Router', enum_value(group.value('Router'), ('Shape', 'Grid')))
        _fields(group, routing, {name: name for name in
            ('TraceWidth', 'TraceClearance', 'BoardClearance', 'ViaSize', 'ViaHole', 'FanoutLength')}, units=units)
        group.finish()
    _fields(record, settings, {name: name for name in
        ('StackLength', 'SignalDelayLength', 'ShowCompFiducials', 'FlipTextAuto', 'EditInactiveLayer')}, kind='boolean')
    _fields(record, settings, {name: name for name in ('SolderMaskSwell', 'PasteMaskShrink')}, units=units)
    if record.has('LayerDisplayMode'):
        settings.add('LayerDisplayMode', enum_value(record.value('LayerDisplayMode'), ('Current Only', 'All Layers', 'Contrast')))
    if record.has('JumperLayer'):
        settings.add('JumperLayer', enum_value(record.value('JumperLayer'), ('Silk', 'Assembly', 'Signal', 'Do Not Show')))
    group = record.take('LayerPanel')
    if group is not None:
        panel = settings.add('LayerPanel')
        _fields(group, panel, {name: name for name in LAYER_PANEL.fields}, kind='boolean')
        choices = panel.add('NonSignals')
        for index, entry in enumerate(group.children('NonSignal')):
            value = entry.content().value
            if value not in ('Y', 'N'):
                raise ValueError('LayerPanel/NonSignal requires Y or N')
            choices.add('Item', index, value == 'Y')
            entry.finish(allow_text=True)
        group.finish()
    group = record.take('RelatedSchem')
    if group is not None:
        actual, variable = read_path(group)
        board.add('RelSchem', actual)
        board.add('RelSchem_Variable', variable)
    _fields(record, board, {'TopComponentLock': 'Toplock', 'BottomComponentLock': 'Bottomlock',
                           'LockNetStructure': 'LockNetStructure', 'SchemNetClasses': 'SchemNetClasses'}, kind='boolean')
    _fields(record, board, {'ProjectDir': 'ProjectDir'}, kind='text')
    record.finish()


def read_connectivity(record, board):
    if record is not None:
        _fields(record, board.add('ConnectivityCheck'), {name: name for name in
                ('Traces', 'Shapes', 'CopperPours')}, kind='boolean')
        record.finish()
