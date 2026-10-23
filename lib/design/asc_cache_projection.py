"""Public ASC cache records over the same editable symbols and footprints.

The cache dialect has its own order, historical spellings and duplicate fields.
Geometry and scalar policies are shared with placed records; binary/format
runtime layouts are not part of this adapter.
"""
from .model import Element, Value
from .asc_model_body import project_model_body
from .asc_projection import (ProjectionError, _head, _plain, _visible, _ordered,
    _value, _project_drawing, project_pad, project_model3d, project_user_fields,
    project_pattern_drawing, _project_terminals, PATTERN_FIELDS, DIMENSION_FIELDS)


CACHED_PIN_FIELDS = '''Enabled Locked ModelSig Type Orientation Number Length Name
StringNumber ShowName PinNumXShift PinNumYShift PinNameXShift PinNameYShift
ElectricType NameFontSize NameFontWidth NameFontScale Group PinNameRotate
PinNumRotate'''.split()
CACHED_DRAWING_FIELDS = '''Enabled Locked VectorFont FontWidth FontScale
Orientation Type FontSize FontColor FontType FontName Name PenWidth Points
TextAngle TextHorz TextVert TextAlign LineSpacing Group TextLine Points_New
ShowPart MarkingGenerated'''.split()
CACHED_SYMBOL_FIELDS = '''Enabled PartType PartName ShowNumbers Type Number1
Number2 Width Height Value LockProperties Origin_X Origin_Y Pins Shapes UserFields
ModelType ModelString ModelBody SubfolderIndex Verification Manufacturer
Component_CategoryName Component_CategoryIndex Component_CategoryTypes Groups
Suppliers'''.split()
CACHED_PATTERN_FIELDS = '''Type Datasheet VariableParameter1 VariableParameter2
VariableParameter3 VariableParameter4 Number1 Number2 Spacing1 Spacing2
VariableParameter5 Spacing3 LockProperties PatternOrientation Width Height
OriginCross OriginCircle OriginCommon OriginCourtyard Name_Description Name_Unique
RecoveryCode RecoveryCode_Generator RecoveryCode_Model Pattern_Manufacturer
PadCorner PadShape_X PadShape_Y PadWidth PadHeight PadShape PadHole PadHoleH
PadHoleType PadTerminalCount PadMask_Percent PadMask_EdgeGap PadMask_SegmentGap
PadMask_SegmentSide PadMask_TopSegments PadMask_BotSegments SurfacePad OriginX
OriginY PadPoints InternalConnections Pattern_Groups Pads Shapes Holes Dimensions
UserFields Model3D Mounting Pattern_CategoryName Pattern_CategoryIndex
Pattern_CategoryTypes PossibleNames'''.split()


def _prefix(node, *, rename=None, keep=()):
    rename = rename or {}
    result = node.clone()
    for item in result.walk(include_self=True):
        if item.kind not in keep:
            item.kind = 'cl_'+rename.get(item.kind, item.kind)
    return result


def _collection(node, kind, project):
    result = _head(node)
    for index, child in enumerate(_visible(node)):
        if child.kind != kind:
            raise ProjectionError(f'{node.path}: expected {kind}, found {child.kind}')
        result.append(project(child, index))
    return result


def project_cached_pin(pin, *, index=None):
    result = _prefix(_ordered(pin, CACHED_PIN_FIELDS), rename={'PinNameXShift': 'PinNamexShift'})
    if index is not None:
        result.set_argument(0, index)
    return result


def project_cached_drawing(shape, *, index=None, text_bounds=None):
    result = _project_drawing(shape, CACHED_DRAWING_FIELDS, index=index, text_bounds=text_bounds, omit_empty=True)
    return _prefix(result, rename={'PenWidth': 'Width'}, keep=('ShowPart', 'MarkingGenerated'))


def project_cached_symbol(part, *, text_bounds=None):
    def pins(node):
        return _collection(node, 'Pin', lambda item, index: project_cached_pin(item, index=index))
    def shapes(node):
        return _collection(node, 'Shape', lambda item, index: project_cached_drawing(item, index=index, text_bounds=text_bounds))
    result = _ordered(part, CACHED_SYMBOL_FIELDS, {'Pins': pins, 'Shapes': shapes,
                                                'ModelBody': project_model_body}, omitted=('ModelNote',))
    for field in result.children():
        if field.kind in ('Pins', 'Shapes'):
            field.kind = 'cl_'+field.kind  # Children already use the cache dialect.
        elif field.kind == 'Suppliers':
            public = ('PartNumber', 'Manufacturer', 'Pattern', 'Supplier', 'Currency')
            old = part.one('Suppliers')
            field.set_values()
            for item in list(field.children()):
                field.remove(item)
            for name in public:
                child = old.child(name)
                if child is not None:
                    field.append(_plain(child))
                else:
                    raise ProjectionError(f'{old.path}: expected one {name}')
        else:
            renamed = {'Origin_X': 'OriginX', 'Origin_Y': 'OriginY',
                'Component_CategoryName': 'CategoryName', 'Component_CategoryIndex': 'CategoryIndex',
                'Component_CategoryTypes': 'CategoryTypes', 'Type': 'CategoryType',
                'Component_Type': 'CategoryType'}
            # Type is a category-row name only, not the symbol's own Type field.
            mapping = renamed if field.kind == 'Component_CategoryTypes' else {k:v for k,v in renamed.items() if k != 'Type'}
            copy = _prefix(field, rename=mapping)
            index = result.children().index(field)
            result.remove(field)
            result.insert(copy, index)
    result.kind = 'cl_Part'
    return result


def project_cached_pad(pad, pattern, *, index=None):
    view = project_pad(pad)
    result = _head(view, 'cl_Pad')
    if index is not None:
        result.set_argument(0, index)
    # ASC emits the current number, then its legacy compatibility view.
    result.add('cl_Number', *map(_value, pad.one('Number_New').arguments))
    for field in view.children():
        result.append(_prefix(field, rename={'Points': 'Point'}))
        if field.kind == 'PadTerminalCount':
            # Footprint defaults repeat after each pad's individual fields.
            for name in ('TopMask_State', 'BotMask_State', 'TopPaste_State', 'BotPaste_State'):
                result.add('cl_'+name, _value(pattern.one(name).arguments[0]))
            for name in ('CustomSwell_New', 'CustomShrink_New'):
                result.append(_prefix(_plain(pattern.one(name))))
    return result


def project_cached_pattern(pattern, *, datasheet='', line_width=None, text_bounds=None):
    unknown = [node.kind for node in _visible(pattern)
               if node.kind not in PATTERN_FIELDS and node.kind not in ('PadTerminal', 'Datasheet')]
    if unknown:
        raise ProjectionError(f'{pattern.path}: no cached footprint projection for {unknown}')
    result = _head(pattern, 'cl_Pattern')
    for name in CACHED_PATTERN_FIELDS:
        if name == 'Datasheet':
            result.add('cl_Datasheet', _value(Value.of(pattern.scalar('Datasheet', datasheet))))
            continue
        field = pattern.child(name)
        if field is None:
            raise ProjectionError(f'{pattern.path}: expected one {name}')
        if name == 'Pads':
            # Cached footprints retain both array-boundary pads. The same
            # owned pattern may have been authored/imported for placed use,
            # where those records carry an omission annotation.
            projected = _head(field, 'cl_Pads')
            for index, pad in enumerate(field.children()):
                if pad.kind != 'Pad':
                    raise ProjectionError(f'{field.path}: expected Pad, found {pad.kind}')
                projected.append(project_cached_pad(pad, pattern, index=index))
        elif name == 'Shapes':
            projected = Element('cl_Shapes')
            for shape in _visible(field):
                for record in project_pattern_drawing(shape, pattern, line_width=line_width, text_bounds=text_bounds):
                    if record.kind == 'Shape':
                        record.set_argument(0, _value(shape.one('Type').arguments[0]))
                    projected.append(_prefix(record, rename={'Points': 'Point'}))
        elif name == 'Dimensions':
            projected = Element('cl_Dimensions')
            for dimension in _visible(field):
                record = _ordered(dimension, DIMENSION_FIELDS)
                record.set_values()
                projected.append(_prefix(record))
        elif name == 'Model3D':
            projected = _prefix(project_model3d(field, variable_fallback=False))
        elif name == 'PadTerminalCount':
            projected = _prefix(_project_terminals(pattern))
        elif name == 'UserFields':
            projected = _prefix(_plain(field))
        else:
            names = {'Pattern_CategoryName': 'CategoryName', 'Pattern_CategoryIndex': 'CategoryIndex',
                     'Pattern_CategoryTypes': 'CategoryTypes', 'Type': 'CategoryType',
                     'Pattern_Type': 'CategoryType'}
            mapping = names if name == 'Pattern_CategoryTypes' else {k:v for k,v in names.items() if k != 'Type'}
            projected = _prefix(_plain(field), rename=mapping)
        result.append(projected)
    return result


def project_cache(cache, *, line_width=None, symbol_text_bounds=None, pattern_text_bounds=None):
    """Project slots, variants, catalog metadata and per-slot library paths."""
    unknown=[n.kind for n in _visible(cache) if n.kind not in ('Categories','Subfolders','Slots')]
    if unknown:
        raise ProjectionError(f'{cache.path}: no cache projection for {unknown}')
    result=Element('CacheLib')
    def catalog(parent,kind,child_kind,public):
        nodes=parent.children(kind)
        if len(nodes) != len(_visible(parent)):
            raise ProjectionError(f'{parent.path}: expected only {kind} records')
        for node in nodes:
            record=Element(public,*map(_value,node.arguments))
            if child_kind is not None:
                record.set_values(*record.arguments,len(node.children(child_kind)))
                for child in catalog(node,child_kind,'Subtype' if child_kind=='Type' else None,
                                     'cl_Type' if child_kind=='Type' else 'cl_SubType'):
                    record.append(child)
            elif node.children():
                raise ProjectionError(f'{node.path}: unexpected catalog children')
            yield record
    categories=cache.one('Categories')
    target=result.add('cl_Categories',len(categories.children('Category')))
    for category in catalog(categories,'Category','Type','cl_Category'):
        target.append(category)
    folders=cache.one('Subfolders')
    target=result.add('cl_Subfolders',len(folders.children('Folder')))
    for folder in catalog(folders,'Folder',None,'cl_Subfolder'):
        target.append(folder)
    components=result.add('cl_Components')
    paths=Element('Design_Cache_specific')
    slots=cache.one('Slots')
    for slot in _visible(slots):
        if slot.kind != 'Slot':
            raise ProjectionError(f'{slots.path}: expected Slot, found {slot.kind}')
        definitions=slot.children('Definition')
        if not definitions:
            raise ProjectionError(f'{slot.path}: empty slot needs an explicit export-cache policy')
        component=components.add('cl_Component')
        for definition in definitions:
            component.append(project_cached_symbol(definition.one('Part'),text_bounds=symbol_text_bounds))
        component.append(project_cached_pattern(definitions[0].one('Pattern'),line_width=line_width,
                                                text_bounds=pattern_text_bounds))
        library=slot.values[1]
        variable=slot.scalar('VariablePath','')
        paths.add('cl_pt',_value(Value.of(library)),_value(Value.of(variable if variable.replace(' ','') else library)))
    components.append(paths)
    return result
