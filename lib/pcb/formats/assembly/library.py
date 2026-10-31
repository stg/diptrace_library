"""Assemble unplaced footprint data and local pad identities in a PCB cache."""
from dataclasses import dataclass, replace

from ....common.model import Element
from ....common.references import Guard, Index
from ....common.structural_edits import assembly
from ...model import library_records
from ...model.internal_connections import PAIR, ROLES
from ...model.library_relations import PIN_PAD_ROLE
from ..errors import PcbError
from .footprint_data import consume_paste_counts, consume_drawing_pads, bind_drawing_pads


@dataclass(frozen=True)
class FootprintAssembly:
    """Temporary saved-position maps for remaining footprint attachment binding."""
    pattern: Element
    pads: dict[int, Element]
    shapes: dict[int, Element]
    holes: dict[int, Element]


def _pad_map(pattern):
    rows = pattern.select('Pads/Pad')
    pads = {}
    removed = rows[:1]+rows[-1:] if len(rows) > 1 else rows
    for position, pad in enumerate(rows[1:-1], 1):
        marker = pad.one('Number_New').values[0]
        if marker != position:
            removed.append(pad)
        else:
            pads[position] = pad
    return pads, removed


def _geometry_map(pattern, path, active):
    """Consume boundary/deleted records while retaining saved attachment positions."""
    rows = pattern.select(path)
    current = {position: row for position, row in enumerate(rows[1:-1], 1) if active(row)}
    kept = set(current.values())
    return current, [row for row in rows if row not in kept]


def assemble_library(core, decoded):
    document = core.document
    prepared, pairs, pin_links, discarded = [], [], [], []
    by_definition = {}
    for pattern in library_records.patterns(decoded.board):
        pads, boundaries = _pad_map(pattern)
        shapes, unused_shapes = _geometry_map(pattern, 'Shapes/Shape', lambda row: row.get('Type', 0) > 0)
        holes, unused_holes = _geometry_map(pattern, 'Holes/Hole', lambda row: bool(row.values[0]))
        prepared.append(FootprintAssembly(pattern, pads, shapes, holes))
        if pattern.parent.kind == 'Definition':
            by_definition[pattern.parent] = prepared[-1]
        discarded.extend(boundaries)
        discarded.extend(unused_shapes)
        discarded.extend(unused_holes)
        discarded.extend(row for row in pattern.select('Dimensions/Dimension') if not row.get('Enabled', True))
        for pair in pattern.select('InternalConnections/IntCon'):
            targets = tuple(pads.get(key) for key in pair.values)
            if len(targets) != 2 or any(target is None for target in targets):
                raise PcbError('unresolved cached internal connection pad')
            pairs.append((pair, targets))
    for slot in decoded.board.select('CacheLib/Slots/Slot'):
        definitions = slot.children('Definition')
        primary = by_definition.get(definitions[0]) if definitions else None
        if primary is None or not primary.pads:
            continue
        # All sections of a multipart component assign pins to its physical
        # footprint. The serialized first section supplies that pad domain.
        for definition in definitions:
            part = definition.child('Part')
            if part is None or part.get('PartType') != 0:
                continue
            for pin in part.select('Pins/Pin'):
                field = pin.child('Number')
                if field is None or not pin.get('Enabled', True) or field.values[0] < 0:
                    continue
                key = field.values[0]
                pin_links.append((pin, field, primary.pads.get(key), primary.pattern.one('Pads')))

    with assembly(document):
        drawing_links = [link for footprint in prepared for link in consume_drawing_pads(footprint)]
        for node in discarded:
            node.detach()
        for item in prepared:
            consume_paste_counts(item.pattern)
            item.pattern.annotations.pop('declared_pad_count', None)
            for pad in item.pads.values():
                pad.one('Number_New').detach()
            for dimension in item.pattern.select('Dimensions/Dimension'):
                dimension.set_values()
        for pair, _ in pairs:
            pair.set_values()
            pair.bind_schema(PAIR)
        from .dimensions import prepare_local_dimensions
        for footprint in prepared:
            prepare_local_dimensions(footprint)
        from .local_groups import prepare_local_groups
        group_links, missing_groups = prepare_local_groups(decoded.board)
        library_records.bind_records(decoded.board)
        for _, field, pad, _ in pin_links:
            if pad is not None:
                field.set_values(pad._ordinal()+1)
        with document.references.binding_batch():
            bind_drawing_pads(document, drawing_links)
            for source, role, target in group_links:
                document.references.bind(source, target, role=role, preserve=True)
            for source, role, field, groups in missing_groups:
                document.references.note(source, role+': local group cannot be resolved',
                                         Index(field), collections=(groups,))
            for pair, targets in pairs:
                for role, target in zip(ROLES, targets):
                    document.references.bind(pair, target, role=role, preserve=True)
            for pin, field, pad, collection in pin_links:
                part = pin.parent.parent
                indices = (Index(field, offset=1),)
                guards = (Guard(part.one('PartType'), (0,)),)
                if pad is None:
                    document.references.note(part, f'{PIN_PAD_ROLE}: target pad cannot be resolved',
                        *indices, collections=(collection,), guards=guards)
                else:
                    document.references.bind(part, pad, *indices, role=PIN_PAD_ROLE, preserve=True, guards=guards)
            from .dimensions import bind_local_dimensions
            for footprint in prepared:
                bind_local_dimensions(document, footprint)
    return replace(core, cached_footprints=tuple(prepared))
