"""PCB ASC cache syntax into shared unplaced symbols and physical footprints."""
from ....common.asc_library import unprefix, unpack_catalogs, unpack_project_paths, rows
from ....common.asc_model_body import unpack_model_body
from ....common.asc_footprints import unpack_model, unpack_terminals, unpack_pattern_shapes
from ....common.model import Element
from ....common import footprint_records, symbol_records
from .values import boolean, numeric_row, rename
from ..errors import PcbError


_FLAGS = {name for schema in (footprint_records.PATTERN, footprint_records.PAD,
          footprint_records.PATTERN_SHAPE, footprint_records.MODEL3D,
          footprint_records.DIMENSION,
          symbol_records.SYMBOL, symbol_records.PIN, symbol_records.DRAWING)
          for name, field in schema.fields.items() if field.kind == 'boolean'}


def _classifications(owner, prefix):
    rename(owner, {'CategoryName': prefix+'_CategoryName', 'CategoryIndex': prefix+'_CategoryIndex',
                   'CategoryTypes': prefix+'_CategoryTypes'})


def _text_lines(collection):
    if collection.values:
        raise PcbError(f'{collection.path}: expected cached text lines')
    collection.kind = 'TextLine'
    for line in rows(collection, 'TextLine'):
        if len(line.arguments) != 1 or line.arguments[0].kind != 'string' or line.children():
            raise PcbError(f'{line.path}: expected one cached text string')
        line.kind = 'pt'


def _groups(owner, name):
    if (groups := owner.child(name)) is not None:
        if groups.values:
            raise PcbError(f'{groups.path}: expected local groups')
        for group in groups.children():
            if group.kind == ('Pattern_Group' if name == 'Pattern_Groups' else 'Group'):
                group.kind = 'pt'
            group.set_values(*numeric_row(group, 4, flags=(0,), integers=(1,)))


def _duplicate_pad_value(pad, old, current):
    first, second = pad.child(old), pad.child(current)
    if first is None:
        return
    if second is None:
        first.kind = current
    elif first.values == second.values and not first.children() and not second.children():
        first.detach()
    else:
        raise PcbError(f'{pad.path}: conflicting cached pad {old}/{current} values')


def _pattern(pattern):
    _classifications(pattern, 'Pattern')
    rename(pattern, {'Manufacturer': 'Pattern_Manufacturer'})
    unpack_terminals(pattern, container='PadTerminals', counted=False)
    for pad in pattern.one('Pads').children():
        if pad.kind != 'Pad' or len(pad.arguments) != 5:
            raise PcbError(f'{pad.path}: expected five cached pad header values')
        for old, current in (('CustomSwell', 'CustomSwell_New'), ('CustomShrink', 'CustomShrink_New')):
            _duplicate_pad_value(pad, old, current)
        rename(pad, {'Number': 'Number_New', 'PadWidth': 'PadWidth_New', 'PadHeight': 'PadHeight_New',
                     'PadShape': 'PadShape_New', 'Point': 'PadPoints_New',
                     'TopMask_State': 'DisableTopMask', 'BotMask_State': 'DisableBottomMask',
                     'TopPaste_State': 'DisableTopPaste', 'BotPaste_State': 'DisableBottomPaste'})
        unpack_terminals(pad, container='PadTerminals', counted=False)
    shapes = pattern.one('Shapes')
    for record in shapes.children():
        if record.kind == 'Point':
            record.kind = 'Points_New'
        elif record.kind == 'TextLines':
            _text_lines(record)
    unpack_pattern_shapes(shapes, pad_id=False, header_fields=(('Layer', 2), ('TextAngle', 15)))
    for hole in pattern.select('Holes/Hole'):
        if len(hole.arguments) != 7 or hole.children():
            raise PcbError(f'{hole.path}: expected seven cached hole values')
        hole.set_values(*(boolean(value, hole.path) if index < 2 else value
                          for index, value in enumerate(hole.arguments)))
    for pair in pattern.select('InternalConnections/*'):
        pair.set_values(*numeric_row(pair, 2, kind='IntCon', integers=(0, 1)))
    model = pattern.one('Model3D')
    rename(model, {'IPC_X': 'IPC_XOff', 'IPC_Y': 'IPC_YOff', 'ModelType': 'Type'})
    unpack_model(model, fields=('Mirror', 'NoSearch', 'Units'))
    _groups(pattern, 'Pattern_Groups')


def _part(part):
    _classifications(part, 'Component')
    rename(part, {'OriginX': 'Origin_X', 'OriginY': 'Origin_Y'})
    unpack_model_body(part.one('ModelBody'))
    for pin in part.select('Pins/Pin'):
        rename(pin, {'PinNamexShift': 'PinNameXShift'})
    for shape in part.select('Shapes/Shape'):
        rename(shape, {'Width': 'PenWidth', 'Orientation': 'TextAngle', 'Points': 'Points_New'})
        if (lines := shape.child('TextLines')) is not None:
            if shape.child('TextLine') is not None:
                raise PcbError(f'{shape.path}: ambiguous cached text lines')
            _text_lines(lines)
        else:
            shape.add('TextLine').add('pt', shape.scalar('Name', ''))
        for name in ('ShowPart', 'MarkingGenerated'):
            if shape.child(name) is None:
                shape.add(name, False)
    verification = part.one('Verification')
    if len(verification.arguments) != 7 or verification.children():
        raise PcbError(f'{verification.path}: expected seven verification flags')
    verification.set_values(*(boolean(value, verification.path) for value in verification.arguments))
    _groups(part, 'Groups')


def unpack_cache(board):
    """Prepare cache definitions without loading external libraries or models.

    ASC supplies one physical footprint per slot. It is owned once, alongside
    the first symbol variant; other variants share its pad domain through the
    normal relationship assembler. Missing independent variants are not copied.
    """
    unpack_project_paths(board)
    old = board.child('CacheLib')
    if old is None:
        return
    unprefix(old)
    if old.values or any(node.kind not in ('Categories', 'Subfolders', 'Components', 'Design_Cache_Specific')
                         for node in old.children()):
        raise PcbError(f'{old.path}: unsupported PCB cache sections')
    unpack_catalogs(old)
    components, paths = old.one('Components'), old.one('Design_Cache_Specific')
    definitions = rows(components, 'Component')
    path_rows = rows(paths, 'pt')
    if components.values or paths.values or len(definitions) != len(path_rows):
        raise PcbError(f'{old.path}: cache path count does not match slots')
    cache = Element('CacheLib')
    old.one('Categories').move_to(cache)
    old.one('Subfolders').move_to(cache)
    slots = cache.add('Slots')
    for index, (component, path) in enumerate(zip(definitions, path_rows)):
        if (len(path.arguments) != 2 or path.children() or
                any(value.kind != 'string' for value in path.arguments)):
            raise PcbError(f'{path.path}: expected actual and variable library paths')
        slot = slots.add('Slot', index, path.arguments[0])
        slot.add('VariablePath', path.arguments[1])
        if component.values or any(node.kind not in ('Part', 'Pattern') for node in component.children()):
            raise PcbError(f'{component.path}: unsupported cached component sections')
        if not component.children():
            continue
        parts, pattern = component.children('Part'), component.one('Pattern')
        if not parts:
            raise PcbError(f'{component.path}: cached component has no symbol variants')
        # PCB ASC places the primary component's datasheet inside cl_Pattern.
        # It is symbol metadata, not a second independent footprint property.
        if (datasheet := pattern.child('Datasheet')) is not None:
            if (len(datasheet.arguments) != 1 or datasheet.arguments[0].kind != 'string'
                    or datasheet.children() or parts[0].child('Datasheet') is not None):
                raise PcbError(f'{pattern.path}: ambiguous cached component datasheet')
            datasheet.move_to(parts[0])
        _pattern(pattern)
        for variant, part in enumerate(parts):
            definition = slot.add('Definition', variant)
            part.move_to(definition)
            _part(part)
            if variant == 0:
                pattern.move_to(definition)
    for node in cache.walk():
        if node.kind in _FLAGS and len(node.arguments) == 1 and not node.children():
            node.set_values(boolean(node.arguments[0], node.path))
    position = board.children().index(old)
    old.detach()
    board.insert(cache, position)
