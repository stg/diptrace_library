"""Bind the electrical core during PCB import, before the full model is ready.

The assembly and its source-key maps are temporary importer state. Remaining
geometry, settings and relationships still require modernization and binding;
this module is not a public read adapter.
"""
from dataclasses import dataclass, field

from ....common.structural_edits import assembly
from ....common.conversion import import_notice
from ...model.document import Document
from ...model.definitions import COMPONENT, PAD, PATTERN, NET, COLLECTIONS, DOCUMENT, BOARD
from ...model.membership import MEMBER
from ...model.settings_records import bind_records as bind_settings
from ...model.board_records import bind_records as bind_board_records
from ..import_context import resolve_import_context
from ..errors import PcbError
from ..import_context import resolved_units
from .footprint_data import consume_paste_counts
from .pad_defaults import normalize_standard_pads
from .via_styles import normalize_static_vias
from .missing_geometry import normalize_sizes
from ..standalone_objects import normalize_components
from ..placement_frames import normalize_frames, resolve_fiducials
from .source_index import SourceIndex
from .net_member_repair import prepare_member_repairs, apply_member_repairs


@dataclass(frozen=True)
class CoreAssembly:
    document: Document
    components: SourceIndex
    nets: dict
    pads: SourceIndex
    cached_footprints: tuple = ()
    pad_positions: dict = field(default_factory=dict)
    teardrops: dict = field(default_factory=dict)
    component_pads: dict = field(default_factory=dict)


def _keyed(records, name, label):
    result = {}
    for record in records:
        key = record[name]
        if key in result:
            raise PcbError(f'ambiguous saved {label} key {key}')
        result[key] = record
    return result


def assemble_core(decoded, *, context=None):
    """Consume saved identities and agreeing net assignments into model links.

    Keep the input-key maps only for the remaining import stages. The unfinished
    assembly is explicitly incomplete and cannot be advertised as PCB support.
    """
    context = resolve_import_context(context)
    upgrades = getattr(decoded, 'upgrades', None)
    display = getattr(upgrades, 'display', None)
    units = resolved_units(decoded.root, display.unit_choices if display is not None else (), context)
    board = decoded.board
    saved_components = board.select('Components/Component')
    saved_nets = board.select('Nets/Net')
    inactive = [node for node in (*saved_components, *saved_nets) if not node['Enabled']]
    components = [node for node in saved_components if node['Enabled']]
    nets = [node for node in saved_nets if node['Enabled']]
    by_component = SourceIndex(((node['Number'], node) for node in components), 'component')
    by_net = _keyed(nets, 'Number', 'net')
    teardrops = {}
    for net_key, net in by_net.items():
        for polygon in net.select('Teardrops/Teardrop'):
            if len(polygon.values) != 1 or type(polygon.values[0]) is not int or polygon.values[0] < 0:
                raise PcbError(f'{polygon.path}: expected a saved teardrop key')
            key = net_key, polygon.values[0]
            if key in teardrops:
                raise PcbError(f'ambiguous saved teardrop key {key}')
            teardrops[key] = polygon
    pad_entries, pad_positions, component_pads = [], {}, {}
    assignments = {}
    members = []
    boundaries = []
    for component_key, component in by_component.entries:
        rows = component.select('Pattern/Pads/Pad')
        # The binary pad array includes its two non-pad boundary entries.
        # Actual pad keys need not equal positions in a compacted input array.
        # Deleted interior entries carry negative keys and do not describe
        # current pads. Their stale geometry and labels are not model content.
        current = [pad for pad in rows[1:-1] if pad['Number_New'] >= 0]
        pad_positions[component] = {position: pad for position, pad in enumerate(rows[1:-1], 1)
                                    if pad['Number_New'] == position}
        actual = _keyed(current, 'Number_New', 'pad')
        component_pads[component] = actual
        for pad_key, pad in actual.items():
            pad_entries.append(((component_key, pad_key), pad))
            net_key = pad['NetNumber']
            if net_key >= 0 and net_key not in by_net:
                raise PcbError(f'unresolved saved pad net key {net_key}')
            assignments[pad] = by_net.get(net_key) if net_key >= 0 else None
        boundaries.extend(rows[:1]+rows[-1:] if len(rows) >= 2 else rows)
        boundaries.extend(pad for pad in rows[1:-1] if pad['Number_New'] < 0)
    pads = SourceIndex(pad_entries, 'net pad')
    repairs = prepare_member_repairs(nets, by_component, pads)
    for repair in repairs.values():
        for _, pad in repair.members:
            assignments[pad] = repair.net
    listed = set()
    for net in nets:
        rows = (repairs[net].members if net in repairs else
                ((row, pads.get(row.values)) for row in net.select('Pads/Item')))
        for row, target in rows:
            if target is None:
                raise PcbError(f'unresolved saved net pad key {row.values}')
            if target in listed:
                raise PcbError('a pad occurs more than once in saved net member lists')
            if assignments[target] is not net:
                raise PcbError('saved pad assignment contradicts its explicit net member')
            listed.add(target)
            members.append((row, target))

    apply_member_repairs(repairs)
    # Inactive records are deleted array slots, not current object identities.
    # Exclude them from modernization too, after active electrical preflight.
    for node in inactive:
        node.detach()
    if (prepare := getattr(decoded, 'prepare', None)) is not None:
        prepare(context)
    normalize_components(board)
    normalize_static_vias(board)
    normalize_sizes(board)
    common_fiducials = resolve_fiducials(board, context.show_component_fiducials)
    normalize_frames(board, raw=True, common_fiducials=common_fiducials)
    normalize_standard_pads(board)
    document = Document(decoded.root)
    document.complete = False
    document.diagnostics.append('PCB import assembly is incomplete')
    if inactive:
        import_notice('info', 'inactive-electrical-records',
                      'Discarded inactive component and net records.',
                      (board.one('Components'), board.one('Nets')),
                      recoverability='active design data retained; deleted slots are not authored objects')
    if by_component.repeated_keys:
        import_notice('info', 'component-number-normalization',
                      'Consumed repeated source component numbers without merging design objects.',
                      (board.one('Components'),),
                      recoverability='each component remains independent; current numbers regenerate on output')
    with assembly(document):
        document.root.bind_schema(DOCUMENT)
        document.root['Units'] = units
        board.bind_schema(BOARD)
        bind_settings(board)
        bind_board_records(board)
        from .titles import bind_titles
        bind_titles(document, board.child('SheetSettings'))
        board.one('Components').bind_schema(COLLECTIONS['Components'])
        board.one('Nets').bind_schema(COLLECTIONS['Nets'])
        for boundary in boundaries:
            boundary.detach()
        for component in components:
            component.one('Number').detach()
            component.bind_schema(COMPONENT)
            pattern = component.one('Pattern').bind_schema(PATTERN)
            consume_paste_counts(pattern)
            pattern.one('Pads').bind_schema(COLLECTIONS['ComponentPads'])
        for net in nets:
            net.one('Number').detach()
            net.bind_schema(NET)
            net.one('Pads').bind_schema(COLLECTIONS['NetPads'])
        for pad in pads.records:
            pad.one('Number_New').detach()
            pad.one('NetNumber').detach()
            if (group := pad.child('InternalConnection')) is not None:
                group.detach()
            if pad.child('SignalDelay') is None:
                pad.add('SignalDelay', 0)
            pad.bind_schema(PAD)
        for row, _ in members:
            row.set_values()
            row.bind_schema(MEMBER)
        with document.references.binding_batch():
            for row, pad in members:
                document.references.bind(row, pad, role='net-member', preserve=True)
            for pad, net in assignments.items():
                if net is not None and pad not in listed:
                    document.references.bind(pad, net, role='pad-net', preserve=True)
    from .internal_connections import assemble_definitions
    from .hierarchy import assemble_hierarchy
    from .connection_groups import assemble_groups
    from .library import assemble_library
    from .cache_links import assemble_cache_links
    from .ratlines import assemble_ratlines
    from .assembly_variants import assemble_variants
    result = CoreAssembly(document, by_component, by_net, pads, pad_positions=pad_positions,
                          teardrops=teardrops, component_pads=component_pads)
    result = assemble_library(result, decoded)
    result = assemble_cache_links(result)
    result = assemble_hierarchy(result)
    result = assemble_definitions(result)
    return assemble_variants(assemble_ratlines(assemble_groups(result)))
