"""Embedded definition output using shared codecs and PCB physical domains."""
from dataclasses import dataclass

from ....common.conversion import info, warn
from ....common.footprint_codec import write_parameters, write_pad_geometry, write_model, write_pattern_extensions
from ....common.footprint_objects import new_pad, new_pattern_drawing
from ....common.library_codec import LibraryCodecs, write_definition, write_cache_library
from ....common.model import Element
from ....common.pad_masks import MASK_FIELDS, mask_state
from ....common.symbol_codec import write_symbol_drawings, write_symbol_extensions
from ....common.supplier_codec import write_supplier
from ....common.supplier_conversion import report_supplier_omissions
from ...model import library_records as model
from ...model.cache_links import validate_prefix
from ..cache_domains import physical_domain
from ..errors import PcbError
from ..output_indices import pad_number
from ..output_validation import check_tree, field_value
from .write_components import write_pattern_graphics


@dataclass(frozen=True)
class DefinitionOutput:
    definition: Element
    pads: tuple
    drawings: tuple
    holes: tuple

    @property
    def pattern(self):
        return self.definition.one('Pattern')


def _boundary(source, schema):
    result = source.clone()
    for child in tuple(result.children()):
        if child.kind not in schema.fields and child.kind not in schema.children:
            child.detach()
        elif child.kind == 'Group' or (field := schema.fields.get(child.kind)) is not None and field.getter is not None:
            child.detach()
    return result.bind_schema(schema)


def definition_outputs(board):
    """Validate current ownership and build fresh, inactive boundary records."""
    validate_prefix(board)
    cache = board.child('CacheLib')
    if cache is not None:
        check_tree(cache, model.CACHE, destination='DIP')
    outputs = []
    for slot in board.select('CacheLib/Slots/Slot'):
        definitions = slot.children('Definition')
        if not definitions:
            continue
        for definition in definitions:
            if definition.child('Part') is None or definition.child('Pattern') is None:
                raise PcbError(f'{definition.path}: DIP requires a symbol and physical footprint per definition')
        selected = physical_domain(slot, definitions)
        if selected is not definitions[0].one('Pattern'):
            raise PcbError(f'{slot.path}: section output requires the pin-assignment footprint in the first definition')
        for definition in definitions:
            pattern = definition.one('Pattern')
            for pair in pattern.select('InternalConnections/IntCon'):
                if pair['Pad1'] is None or pair['Pad2'] is None:
                    raise PcbError(f'{pair.path}: internal connection needs two current pads')
            boundary_pad = _boundary(new_pad(), model.PAD)
            boundary_drawing = _boundary(new_pattern_drawing(), model.PATTERN_DRAWING)
            boundary_hole = Element('Hole', False, False, 0, 0, 0, 0).bind_schema(model.HOLE)
            outputs.append(DefinitionOutput(definition,
                (boundary_pad, *pattern.select('Pads/Pad'), boundary_pad),
                (boundary_drawing, *pattern.select('Shapes/Shape'), boundary_drawing),
                (boundary_hole, *pattern.select('Holes/Hole'), boundary_hole)))
    return tuple(outputs)


def _omissions(writer, board, outputs):
    cache = board.child('CacheLib')
    for name in ('Patterns', 'PadStyles', 'PatternCategories'):
        branch = cache.child(name) if cache is not None else None
        if branch is not None and branch.children():
            warn(writer.report, 'independent-library-definitions', 'dip',
                 'DIP cannot carry independent library '+name, (branch,),
                 recoverability='cached and placed physical definitions remain; unused independent definitions are omitted')
    for output in outputs:
        pattern = output.pattern
        present = [name for name in ('Value', 'Datasheet', 'RefDes', 'Sided') if pattern.child(name) is not None]
        if present:
            notice = warn if any(pattern.get(name) for name in present) else info
            notice(writer.report, 'cached-pattern-metadata', 'dip',
                   'DIP omits independent footprint metadata: '+', '.join(present), (pattern,))
        for pad in pattern.select('Pads/Pad'):
            if pad.child('Id') is not None:
                warn(writer.report, 'cached-pad-persistent-key', 'dip', 'DIP generates positional cached pad keys', (pad,))
        for shape in pattern.select('Shapes/Shape'):
            if field_value(shape, 'PadId') != -1:
                warn(writer.report, 'cached-drawing-pad', 'dip', 'DIP omits a cached drawing pad selector', (shape,))
        part = output.definition.one('Part')
        for pin in part.select('Pins/Pin'):
            if pin.child('UnresolvedKeys') is not None:
                raise PcbError(f'{pin.path}: unresolved cached pin extensions need a DIP mapping')
            if pin.child('SignalDelay') is not None:
                notice = warn if pin['SignalDelay'] else info
                notice(writer.report, 'cached-pin-delay', 'dip', 'DIP omits cached pin signal delay', (pin,))
        for shape in part.select('Shapes/Shape'):
            if field_value(shape, 'ShowPart') or field_value(shape, 'MarkingGenerated'):
                warn(writer.report, 'cached-symbol-drawing-options', 'dip',
                     'DIP omits cached symbol visibility and generation settings', (shape,))


def _pads(writer, output):
    writer.integer(len(output.pads))
    for index, pad in enumerate(output.pads):
        writer.boolean(writer.quarter_turns(pad['PadAngle']) % 2 == 1)
        writer.integer(-1 if index in (0, len(output.pads)-1) else pad_number(pad))
        writer.fields(pad, 'number', 'X Y')
        writer.fields(pad, 'text', 'StringNumber Name')
        write_pad_geometry(writer, pad)
        writer.fields(pad, 'boolean', 'Locked Sided')
        for name in MASK_FIELDS:
            writer.boolean(mask_state(pad, name) == 2)
        writer.fields(pad, 'number', 'CustomSwell_New CustomShrink_New')


def write_cache(writer, board, outputs=None):
    """Write the cache envelope; retain the returned plan for later extensions."""
    outputs = definition_outputs(board) if outputs is None else outputs
    _omissions(writer, board, outputs)
    writer.scalar(board, 'ProjectLibs_Name', 'text', default='')
    writer.scalars(board, 'integer', 'ProjectLibs_Type ProjectLibs_Content',
                   defaults={'ProjectLibs_Type': 0, 'ProjectLibs_Content': 0})
    writer.rows(board.child('ProjectLibs_Folders'), 'Folder', 'text')
    writer.rows(board.child('ProjectLibs_Libs'), 'Lib', 'text')
    writer.scalar(board, 'ProjectLibs_Sorted', 'boolean', default=False)
    writer.field(board, 'DesignCache_Count', 'integer')
    writer.rows(board.child('DesignCache_Links'), 'Link', 'integer')
    for link in board.select('DesignCache_Links/Link'):
        if board._owner().references.unresolved_slot(link):
            warn(writer.report, 'unresolved-design-cache-slot', 'dip', 'Active design-cache selection is unavailable',
                 (link,), recoverability='the explicit unresolved slot index remains')
    by_pattern = {output.pattern: output for output in outputs}
    codecs = LibraryCodecs(write_parameters,
        lambda w, p: _pads(w, by_pattern[p]),
        lambda w, p: write_pattern_graphics(w, p, drawings=by_pattern[p].drawings, holes=by_pattern[p].holes),
        write_model, lambda w, p: write_symbol_drawings(w, p, orientation=w.quarter_turns),
        definition_text='Datasheet')
    write_cache_library(writer, board.child('CacheLib'),
                        lambda w, d: write_definition(w, d, codecs))
    return outputs


def write_cache_masks(writer, outputs):
    for output in outputs:
        for pad in output.pads:
            for name in MASK_FIELDS:
                writer.integer(mask_state(pad, name))


def write_cache_extensions(writer, outputs):
    for output in outputs:
        write_pattern_extensions(writer, output.pattern,
                                 pads=output.pads, drawings=output.drawings, holes=output.holes)
        write_symbol_extensions(writer, output.definition.one('Part'))


def write_cache_pin_rotations(writer, outputs):
    for output in outputs:
        for pin in output.definition.select('Part/Pins/Pin'):
            writer.fields(pin, 'integer', 'PinNameRotate PinNumRotate')


def cache_font_records(outputs):
    for output in outputs:
        for pin in output.definition.select('Part/Pins/Pin'):
            yield pin, 'NameFontSize', 'NameFontMono'
        for shape in output.definition.select('Part/Shapes/Shape'):
            yield shape, 'FontSize', 'FontMono'
        for shape in output.drawings:
            yield shape, 'FontSize', 'FontMono'
        for dimension in output.pattern.select('Dimensions/Dimension'):
            yield dimension, 'FontSize', 'FontMono'


def write_cache_model_options(writer, outputs):
    for output in outputs:
        writer.field(output.pattern.one('Model3D'), 'KeepPins', 'boolean')


def write_cache_suppliers(writer, outputs):
    report_supplier_omissions((output.definition.one('Part') for output in outputs),
        destination='dip', report=writer.report, omit_source_locator=False, omit_preference=True)
    for output in outputs:
        part = output.definition.one('Part')
        write_supplier(writer, part, prices=False)


def write_cache_paths(writer, board):
    """Literal variable paths only; writing never discovers external files."""
    for slot in board.select('CacheLib/Slots/Slot'):
        writer.scalar(slot, 'VariablePath', 'text', default='')
        definitions = slot.children('Definition')
        owner = definitions[0].one('Pattern/Model3D') if definitions else slot
        writer.scalar(owner, 'Model3DFile_Variable', 'text', default='')
        for definition in definitions[1:]:
            model = definition.one('Pattern/Model3D')
            if model.get('Model3DFile_Variable', ''):
                warn(writer.report, 'cached-secondary-model-path', 'dip',
                     'DIP carries one variable model path per cached component slot', (model,),
                     recoverability='literal model filenames and the primary variable path remain')


def write_cache_shields(writer, outputs):
    for output in outputs:
        for shape in output.drawings:
            writer.field(shape, 'ShieldGroup', 'integer')
