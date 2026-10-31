"""PCB preferences, sheet and supplied panel layout in current XML units."""
from ....common.conversion import warn
from ....common.model import Element
from ....common.xml import set_attribute
from ....common.xml_cell_output import append_title_blocks
from ....common.xml_font_output import project_size
from ....common.xml_output import enum_text, field, numeric, stroke_width
from ...model import board_records, markings, settings_records
from ..output_validation import check_tree
from .components import SHOW, ALIGN
from .graphic_output import project_layer_panel


def _fields(source, target, names, *, units=None, attribute=False):
    """Only authored values and available computed views select optional fields."""
    if source is None:
        return
    emit = set_attribute if attribute else field
    for public, own in names.items():
        value = source.get(own)
        if value is not None:
            emit(target, public, numeric(units.length(value)) if units else value)


def _group(parent, name, source, names, *, units=None):
    result = Element(name)
    _fields(source, result, names, units=units)
    if result.children():
        parent.append(result)
    return result


def _markings(board, *, report):
    result = Element('Markings')
    _fields(board, result, {'CompRotate': 'CompRotate', 'FontVector': 'PatternFontVector',
        'FontMono': 'CompFontMono', 'FontName': 'CompFontName',
        'FontWidth': 'PatternFontWidth', 'FontScale': 'PatternFontScale'})
    if board.get('CompFontSize') is not None:
        project_size(board, result, size='CompFontSize',
                     mono='CompFontMono' if 'CompFontMono' in board else None, attribute=False)
    for name in markings.NAMES:
        target = Element(name+'Global')
        for side in markings.SIDES:
            for suffix, labels in (('Show', SHOW), ('Align', ALIGN)):
                value = board.get(name+'_Global_'+side+suffix)
                if value is not None:
                    set_attribute(target, side+suffix, enum_text(value, labels))
        if target.children():
            result.append(target)
    if (fields := board.child('Userfields_Global')) is not None:
        check_tree(fields, markings.GLOBAL_USER_FIELDS, destination='DIPXML')
        target = result.add('AddFieldsGlobal')
        for source in fields.children('UserField'):
            row = target.add('AddField')
            field(row, 'Name', source['Name'])
            for side in markings.SIDES:
                for suffix, labels in (('Show', SHOW), ('Align', ALIGN)):
                    set_attribute(row, side+suffix, enum_text(source[side+suffix], labels))
    return result


def project_settings(board, *, units, report=None):
    result, source = Element('Settings'), board.child('Settings')
    if source is not None:
        check_tree(source, settings_records.SETTINGS, destination='DIPXML')
    if (markings := _markings(board, report=report)).children():
        result.append(markings)
    _group(result, 'Grid', source, {'Visible': 'GridEnabled', 'Snap': 'GridSnap', 'YIdentical': 'YGridIdentical'})
    grid = result.child('Grid')
    dimensions = Element('Grid') if grid is None else grid
    _fields(source, dimensions, {'Size': 'GridSize', 'YSize': 'YGridSize'}, units=units)
    if grid is None and dimensions.children():
        result.append(dimensions)
    origin = _group(result, 'Origin', source, {'Visible': 'OriginEnabled', 'AxisColor': 'AxisColor'})
    x, y = board.get('OriginX'), board.get('OriginY')
    if x is not None or y is not None:
        for name, value in zip(('X', 'Y'), units.point(0 if x is None else x, 0 if y is None else y)):
            field(origin, name, numeric(value))
        if origin.parent is None:
            result.append(origin)
    _group(result, 'Assembly', source, {'Pads': 'AssyPads', 'Silk': 'AssySilk',
        'CompBorders': 'AssyPatBorders', 'BoardOutline': 'AssyBoardOutline'})
    _group(result, 'LineWidth', source, {'Silk': 'SilkLineWidth', 'Table': 'TableLineWidth',
        'Titles': 'TitlesLineWidth', 'BoardOutline': 'BoardOutlineWidth', 'Assembly': 'AssemblyWidth',
        'CompOutline': 'CompOutlineWidth', 'Courtyard': 'CourtyardWidth'}, units=units)
    if source is not None and (routing := source.child('Routing')) is not None:
        target = result.add('Routing')
        if (router := routing.get('Router')) is not None:
            field(target, 'Router', enum_text(router, ('Shape', 'Grid')))
        _fields(routing, target, {name: name for name in
            ('TraceWidth', 'TraceClearance', 'BoardClearance', 'ViaSize', 'ViaHole', 'FanoutLength')}, units=units)
        if routing.get('PadClearance', 0) != 0 or routing.get('ViaApply', 0) != 0:
            warn(report, 'routing-default-options', 'dipxml',
                 'XML omits separate default pad clearance and via-application choices', (routing,))
    _fields(source, result, {name: name for name in
        ('StackLength', 'SignalDelayLength', 'ShowCompFiducials', 'FlipTextAuto', 'EditInactiveLayer')})
    _fields(source, result, {name: name for name in ('SolderMaskSwell', 'PasteMaskShrink')}, units=units)
    for name, labels in (('LayerDisplayMode', ('Current Only', 'All Layers', 'Contrast')),
                         ('JumperLayer', ('Silk', 'Assembly', 'Signal', 'Do Not Show'))):
        if source is not None and (value := source.get(name)) is not None:
            field(result, name, enum_text(value, labels))
    if (panel := project_layer_panel(board)).children():
        result.append(panel)
    if board.get('RelSchem') is not None or board.get('RelSchem_Variable') is not None:
        target = result.add('RelatedSchem')
        field(target, 'Path', board.get('RelSchem', ''))
        field(target, 'Var', board.get('RelSchem_Variable', ''))
    _fields(board, result, {'TopComponentLock': 'Toplock', 'BottomComponentLock': 'Bottomlock',
        'LockNetStructure': 'LockNetStructure', 'SchemNetClasses': 'SchemNetClasses', 'ProjectDir': 'ProjectDir'})
    return result


def project_connectivity(board):
    result = Element('ConnectivityCheck')
    if (source := board.child('ConnectivityCheck')) is not None:
        check_tree(source, settings_records.CONNECTIVITY, destination='DIPXML')
        _fields(source, result, {name: name for name in settings_records.CONNECTIVITY.fields}, attribute=True)
    return result


def project_sheet(board, *, units):
    result, source = Element('SheetSettings'), board.child('SheetSettings')
    root = board._owner().root
    _fields(root, result, {'Scale': 'Scale'})
    x, y = root.get('Xpos'), root.get('Ypos')
    if x is not None or y is not None:
        for name, value in zip(('Xpos', 'Ypos'), units.point(0 if x is None else x, 0 if y is None else y)):
            field(result, name, numeric(value))
    if source is None:
        return result
    check_tree(source, settings_records.SHEET, destination='DIPXML')
    for name, definition in settings_records.SHEET.fields.items():
        _fields(source, result, {name: name}, units=units if definition.unit == 'shared length' else None)
    if (zones := source.child('BorderZones')) is not None:
        target = result.add('BorderZones')
        for name, definition in settings_records.BORDER_ZONES.fields.items():
            if (value := zones.get(name)) is None:
                continue
            if name == 'FontSize':
                project_size(zones, target, mono=None, attribute=False)
            elif name == 'FontLineWidth':
                field(target, name, stroke_width(value, units))
            else:
                field(target, name, numeric(units.length(value)) if definition.unit == 'shared length' else value)
    append_title_blocks(source, result, units=units)
    return result


def project_panel(board, *, units, display_metrics=True, side_gaps=True, report=None):
    result, source = Element('Panel'), board.child('Panel')
    _fields(board, result, {'Columns': 'PanelX', 'Rows': 'PanelY', 'RailShow': 'RailShow'}, attribute=True)
    _fields(board, result, {'ColumnSpacing': 'PanelDX', 'RowSpacing': 'PanelDY'}, units=units, attribute=True)
    _fields(board, result, {name: name for name in ('RailLeft', 'RailRight', 'RailTop', 'RailBottom')},
            units=units if display_metrics else None, attribute=True)
    if source is None:
        return result
    check_tree(source, board_records.PANEL, destination='DIPXML')
    if (value := source.get('Type')) is not None:
        set_attribute(result, 'Type', enum_text(value, ('V-Scoring', 'Tab Routing')))
    for name, definition in board_records.PANEL.fields.items():
        if not side_gaps and name in ('LeftGap', 'RightGap', 'TopGap', 'BottomGap'):
            spacing = 'PanelDX' if name in ('LeftGap', 'RightGap') else 'PanelDY'
            if (value := source.get(name)) is not None and value != board.get(spacing, 0):
                warn(report, 'panel-side-gaps', 'dipxml', 'Destination omits independent panel-side spacing',
                     (source.one(name),), recoverability='copy spacing remains; independent side gaps are not represented')
            continue
        if name != 'Type':
            _fields(source, result, {name: name},
                    units=units if display_metrics and definition.unit == 'shared length' else None, attribute=True)
    for name in ('HorzTabsX', 'VertTabsY'):
        if (positions := source.child(name)) is not None:
            target = result.add(name)
            for row in positions.children('Item'):
                value = units.length(row['Position'])
                field(target, 'Item', numeric(-value if name == 'VertTabsY' else value))
    return result
