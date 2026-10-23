"""Version defaults expressed in our document vocabulary."""
from decimal import Decimal
from .dch_records import placed_components, cached_definitions, footprints, symbols
from .schematic_geometry import symbol_bounds, pattern_bounds
from .model import Element


def complete_properties(schematic):
    """Make absent older properties ordinary current data after modernization.

    These are declared defaults, not estimates or destination-specific changes.
    Optional supplier match flags stay absent until an export context resolves
    the environment-dependent preference.
    """
    def missing(parent,name,*values):
        if parent.child(name) is None:
            parent.add(name,*values)

    missing(schematic,'ProjectDir','')
    for part in symbols(schematic):
        supplier=part.one('Suppliers')
        for name in ('PartNumber','Manufacturer','Pattern','Supplier','SourceLocator','Currency'):
            missing(supplier,name,'')
        if part.parent.kind=='Components':
            missing(supplier,'Prices')
            missing(part,'LibPath_Variable',part.scalar('LibPath'))
    for pattern in footprints(schematic):
        model=pattern.one('Model3D')
        missing(model,'Model3DFile_Variable','' if pattern.parent.kind=='Definition' else model.scalar('Model3DFile'))
    for shape in schematic.select('Shapes/Shape'):
        missing(shape,'Picture_File_Variable',shape.scalar('Picture_File'))
    for name,kind in [('ProjectLibs_Folders','Folder'),('ProjectLibs_Libs','Lib')]:
        for path in schematic.select(name+'/'+kind):
            missing(path,'VariablePath',path.values[0])
    for slot in schematic.select('CacheLib/Slots/Slot'):
        missing(slot,'VariablePath',slot.values[1])
        if not slot.children('Definition'):
            missing(slot,'Model3DFile_Variable','')
    for definition in cached_definitions(schematic):
        missing(definition.one('Part'),'ModelNote','')


def _default(parent, name, *values, version):
    if parent.child(name) is not None:
        raise ValueError(f"version default would overwrite {name}")
    node = parent.add(name, *values)
    node.annotations["default_for_version"] = version
    return node


def _mask_defaults(parent, version):
    for name, value in (("PadMask_Percent", 50), ("PadMask_EdgeGap", Decimal('0.9')),
                        ("PadMask_SegmentGap", Decimal('0.6')), ("PadMask_SegmentSide", 3)):
        _default(parent, name, value, version=version)
    for name in ("PadMask_TopSegments", "PadMask_BotSegments"):
        _default(parent, name, 0, version=version)


def _empty_groups(parent, name, version):
    # Earlier layouts have no current group array; obsolete member lists have
    # already been consumed without becoming document data.
    _default(parent, name, version=version)


def _pattern_defaults(pattern, version):
    
    for name, value in (
        ("OriginCross", True), ("OriginCircle", True), ("OriginCommon", 1), ("OriginCourtyard", 0),
        ("Name_Description", ""), ("Name_Unique", ""), ("RecoveryCode", ""),
        ("RecoveryCode_Generator", True), ("RecoveryCode_Model", True), ("Pattern_Manufacturer", ""),
        ("PadCorner", 0), ("PadShape_X", 0), ("PadShape_Y", 0), ("PadTerminalCount", 0),
        ("TopMask_State", 0), ("BotMask_State", 0), ("TopPaste_State", 0), ("BotPaste_State", 0),
        ("CustomSwell_New", -1000), ("CustomShrink_New", -1000),
    ):
        _default(pattern, name, value, version=version)
    _mask_defaults(pattern, version)
    for pad in pattern.child("Pads").children("Pad"):
        for name, value in (("Group", -1), ("PadCorner", 0), ("PadShape_X", 0),
                            ("PadShape_Y", 0), ("PadTerminalCount", 0)):
            _default(pad, name, value, version=version)
        _mask_defaults(pad, version)
    for hole in pattern.child("Holes").children("Hole"):
        hole.set_values(*hole.arguments, -1)
        hole.annotations["group_default_for_version"] = version
    for dimension in pattern.child("Dimensions").children("Dimension"):
        _default(dimension, "Group", -1, version=version)
        for side in (1,2):
            point=dimension.one('Point'+str(side))
            if dimension.scalar('Connected'+str(side))==0 and point.values[0]>9:
                point.set_values(point.values[0]+10)
    _empty_groups(pattern, "Pattern_Groups", version)
    for name, value in (('IPC_XOff', 0), ('IPC_YOff', 0), ('AutoHeight', 0),
                        ('AutoColor', 0x4B4B4B), ('Type', 0)):
        _default(pattern.child('Model3D'), name, value, version=version)


def _symbol_defaults(part, version):
    
    for container, kind in (("Pins", "Pin"), ("Shapes", "Shape")):
        for node in part.child(container).children(kind):
            _default(node, "Group", -1, version=version)


def apply_version_defaults(version, schematic):
    """Fill absent fields after wire decoding, using the source version."""
    if version >= 40:
        return
    for part in placed_components(schematic):
        if version < 32:
            
            # pre-32 branch. They are absent from the wire, not unknown data.
            for parent, defaults in (
                    (part.child('Pattern'), (('Mounting', -1), ('Pattern_CategoryName', ''),
                     ('Pattern_CategoryIndex', -1), ('Pattern_CategoryTypes', 0), ('PossibleNames', 0))),
                    (part, (('Manufacturer', ''), ('Component_CategoryName', ''),
                     ('Component_CategoryIndex', -1), ('Component_CategoryTypes', 0)))):
                for name, value in defaults:
                    _default(parent, name, value, version=version)
        for name, value in (("CustomMarkingFont", False), ("MarkingFontSize", 6), ("MarkingFontAll", False)):
            _default(part, name, value, version=version)
        _pattern_defaults(part.child("Pattern"), version)
        _symbol_defaults(part, version)
        for shape in part.child('Shapes').children('Shape'):
            
            
            _default(shape, 'ShowPart', True, version=version)
    
    for table in schematic.child("Tables").children("Table"):
        _default(table, "DefLineSpacing", Decimal('1.2'), version=version)
        for cell in table.child("Cells").children("Cell"):
            _default(cell, "LineSpacing", Decimal('1.2'), version=version)
    for page in schematic.child("Pages").children("Page"):
        for grid in page.child("TitleBlocks").children("TitleBlock"):
            for cell in grid.child("Contents").children("Content"):
                _default(cell, "LineSpacing", Decimal('1.2'), version=version)
    for definition in cached_definitions(schematic):
        _pattern_defaults(definition.child("Pattern"), version)
        part = definition.child("Part")
        _symbol_defaults(part, version)
        _empty_groups(part, "Groups", version)


def restore_legacy_dimensions(version, schematic):
    """Old files store approximate selection sizes; derive authoring bounds.

    Placed origins are migrated separately; library origins remain unchanged.
    """
    if version >= 40:
        return
    placed = set(placed_components(schematic))
    for part in symbols(schematic):
        bounds = symbol_bounds(part)
        minimum = .36 if part in placed else 0
        for name, size in (('Width', bounds.width if bounds else 0),
                           ('Height', bounds.height if bounds else 0)):
            field = part.child(name)
            field.annotations['derived_from'] = 'symbol geometry'
            field.set_values(Decimal(str(max(minimum, size))))
    for pattern in footprints(schematic):
        bounds = pattern_bounds(pattern)
        for name, size in (('Width', bounds.width if bounds else 0),
                           ('Height', bounds.height if bounds else 0)):
            field = pattern.child(name)
            field.annotations['derived_from'] = 'footprint geometry'
            field.set_values(Decimal(str(max(.0001, size))))


def recenter_legacy_symbols(version, schematic):
    """Migrate placed pre-40 symbols while preserving their sheet positions."""
    if version >= 40:
        return
    for part in placed_components(schematic):
        recenter_symbol(part)
        part.annotations.pop('pending_origin_migration', None)


def recenter_symbol(part):
    bounds = symbol_bounds(part)
    center = bounds.center if bounds else (0., 0.)
    if not any(center):
        return center
    cx, cy = center
    for name, offset in (('X', cx), ('Y', cy)):
        field = part.child(name)
        field.set_values(float(field.values[0])+offset)
    for pin in part.child('Pins').children('Pin'):
        if pin.scalar('Enabled') in (True, 'Y'):
            pin.set_argument(1, float(pin.values[1])-cx)
            pin.set_argument(2, float(pin.values[2])-cy)
    for shape in part.child('Shapes').children('Shape'):
        if shape.scalar('Enabled') not in (True, 'Y'):
            continue
        geometry = shape.child('Points_New') or shape.child('Points')
        for point in geometry.children('pt'):
            point.set_values(float(point.values[0])-cx, float(point.values[1])-cy)
    labels = [part.child(name) for name in ('ShowRefDes', 'ShowName', 'ShowValue',
                                          'ShowManufacturer', 'ShowDatasheet')]
    fields = part.child('UserFields')
    labels.extend(fields.children('UserField') if fields else ())
    for label in labels:
        # Every public label tuple ends with position-choice, horizontal and
        # vertical alignment, X, Y, angle. Choice 8 stores an explicit anchor.
        if label is not None and len(label.values) >= 6 and label.values[-6] == 8:
            label.set_argument(len(label.values)-3, float(label.values[-3])-cx)
            label.set_argument(len(label.values)-2, float(label.values[-2])-cy)
    return center


