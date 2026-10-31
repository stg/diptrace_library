"""Document-wide PCB authoring choices and supplied panelization data."""
from ...common.schema import Child, Field, Record
from . import markings


def _fields(kind, names, *, unit=''):
    return {name: Field(name, kind, unit=unit) for name in names.split()}


BOARD_FIELDS = {
    **markings.GLOBAL_FIELDS,
    **_fields('text', 'RelSchem RelSchem_Variable ProjectDir CompFontName UserField1 UserField2 ProjectLibs_Name'),
    **_fields('boolean', 'Locked Toplock Bottomlock PanelExclude RailShow PatternFontVector '
                         'AssyObjSilk AssyObjBorders AssyObjMarking AssyObjBoard AssyObjPads '
                         'CompRotate LockNetStructure SchemNetClasses ProjectLibs_Sorted'),
    'CompFontMono': Field('CompFontMono', 'boolean', default=False),
    **_fields('integer', 'PanelX PanelY ProjectLibs_Type ProjectLibs_Content DesignCache_Count'),
    **_fields('number', 'PanelDX PanelDY RailLeft RailRight RailTop RailBottom OriginX OriginY',
              unit='shared length'),
    **_fields('number', 'CompFontSize PatternFontWidth PatternFontScale'),
}

PANEL = Record('PcbPanel', {
    **_fields('integer', 'Type BorderTabs'),
    **_fields('boolean', 'TabsDone KeepMaterial PanelizeSingle'),
    **_fields('number', 'TabWidth TabRadius TabStep HoleDiam HoleStep HoleInset HoleKeepout '
                        'CombinedRadius LeftGap RightGap TopGap BottomGap', unit='shared length'),
}, children={name: Child(name, 'PcbPanelTabPositions') for name in ('HorzTabsX', 'VertTabsY')})
TAB_POSITION = Record('PcbPanelTabPosition', {
    'Position': Field('Position', 'number', required=True, unit='shared length'),
}, parameters=('Position',))
TAB_POSITIONS = Record('PcbPanelTabPositions', {}, children={
    'Item': Child('Item', TAB_POSITION.name, maximum=None)})


def definition(node):
    parent = node.parent
    if parent is None:
        return None
    if node.kind == 'Panel' and parent.kind == 'Board':
        return PANEL
    if parent.kind == 'Panel' and node.kind in ('HorzTabsX', 'VertTabsY'):
        return TAB_POSITIONS
    if (node.kind == 'Item' and parent.kind in ('HorzTabsX', 'VertTabsY') and
            parent.parent is not None and parent.parent.kind == 'Panel'):
        return TAB_POSITION
    return None


def bind_records(board):
    fields = board.child('Userfields_Global')
    if fields is not None:
        fields.bind_schema(markings.GLOBAL_USER_FIELDS)
        for field in fields.children('UserField'):
            field.set_values()
            # ASC/DIP store a redundant name key. The current field name owns it.
            if (key := field.child('Value')) is not None:
                key.detach()
            field.bind_schema(markings.GLOBAL_USER_FIELD)
    panel = board.child('Panel')
    if panel is not None:
        for node in panel.walk(include_self=True):
            if (schema := definition(node)) is not None:
                node.bind_schema(schema)
