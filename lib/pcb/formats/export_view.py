"""Complete output settings on a detached PCB export view.

Fallbacks are library policy for absent information, not imported design facts
or historical snapshots. Stored settings remain authoritative.
"""
from ...common.conversion import info, warn
from ...common.schema import MISSING
from ...common.model import IncompleteDocumentError
from ...common.title_records import new_title_blocks
from ...common.footprint_objects import new_pattern
from ..model import rule_records, library_records, static_via
from ..model.stackup import default_stackup
from .export_context import resolve_export_context
from .cache_domains import prepare_primary_order
from .marking_defaults import complete_user_markings, default_markings
from .calculated_markings import materialize_markings
from .path_variables import prepare_variable_paths
from .standalone_objects import report_ignored_data
from .assembly.missing_geometry import materialize_sizes
from .placement_frames import normalize_frames
from .assembly.object_kinds import normalize_objects
from .inactive_output import compact_length_results, compact_xml_board, compact_xml_patterns


def _fill(node, values, changed):
    added = False
    for name, value in values.items():
        if node.get(name, MISSING) is MISSING:
            node[name] = value
            added = True
    if added:
        changed.append(node)


def _child(owner, name):
    result = owner.child(name)
    return result if result is not None else owner.add(name)


def _last_rules(board):
    """Derive the required previous-rule envelope from current rule meaning."""
    source, target = board.one('DRC'), board.add('LastDRC')
    window = ('ShowList', 'RealTimeMode', 'DRCDone')
    for name, field in rule_records.DRC.fields.items():
        if name not in window:
            target[name] = source.get(name, field.default)
    for name, kind in (('LayClearances', 'LayClearance'), ('LaySizes', 'LaySize')):
        rows = source.select(name+'/'+kind)
        if not rows:
            continue
        output = target.add(name)
        for row in rows:
            copy = output.add(kind)
            copy['Layer'] = row['Layer']
            for field, definition in row.schema.fields.items():
                if definition.getter is None:
                    copy[field] = row.get(field, definition.default)
            if (details := row.child('ClearanceDetails')) is not None:
                copy.append(details.clone())
    return target


def prepare_export(document, *, context=None, report=None, destination='dip'):
    """Return a configured independent view and its resolved context."""
    if destination not in ('dip', 'asc', 'dipxml'):
        raise ValueError('unknown PCB output format: '+str(destination))
    if not document.complete:
        raise IncompleteDocumentError('complete PCB data is required for conversion')
    selected = resolve_export_context(context)
    context = selected.resolved(document)
    view = document.clone()
    board, changed = view.one('/Board'), []
    compact_length_results(view, destination=destination, report=report)
    if destination == 'dipxml':
        compact_xml_board(view, report=report)
        compact_xml_patterns(view, report=report)
    normalize_objects(board, raw=False, destination=destination, report=report)
    report_ignored_data(board, destination=destination, report=report)
    if (vias := tuple(static_via.conflicting_components(board))):
        warn(report, 'static-via-style', destination,
             'The selected via style overrides conflicting pad geometry when the output is opened',
             vias, recoverability='the authoring model remains unchanged; reopened geometry follows the selected style')
    view.root['Units'] = context.units
    if selected.project_dir is not None:
        board['ProjectDir'] = selected.project_dir
    _fill(board, dict(CompFontSize=context.font_size, CompFontName='', CompFontMono=False,
        PatternFontVector=context.vector_font, PatternFontWidth=-1, PatternFontScale=1,
        ProjectDir=context.project_dir), changed)
    _fill(board, default_markings(), changed)

    settings = _child(board, 'Settings')
    _fill(settings, dict(GridSize=context.grid_size, GridEnabled=True, YGridSize=settings.get('GridSize', context.grid_size),
        YGridIdentical=True, OriginEnabled=True, AxisColor=0x808080, FlipTextAuto=True,
        AssyPads=False, AssySilk=True, AssyPatBorders=False, AssyBoardOutline=True,
        JumperLayer=0, LayerDisplayMode=0, EditInactiveLayer=False,
        SilkLineWidth=context.line_width, TableLineWidth=context.line_width, TitlesLineWidth=context.line_width,
        BoardOutlineWidth=context.line_width, SolderMaskSwell=0, PasteMaskShrink=0,
        StackLength=False, SignalDelayLength=False, ShowCompFiducials=True), changed)
    _child(settings, 'Routing')
    panel = _child(settings, 'LayerPanel')
    _fill(panel, dict.fromkeys(panel.schema.fields, True), changed)
    connectivity = _child(board, 'ConnectivityCheck')
    _fill(connectivity, dict.fromkeys(connectivity.schema.fields, True), changed)

    sheet = _child(board, 'SheetSettings')
    _fill(sheet, dict(SheetWidth=context.sheet_size[0], SheetHeight=context.sheet_size[1],
        LeftMargin=0, TopMargin=0, RightMargin=0, BottomMargin=0, DisplayTitles=False, DisplaySheet=False), changed)
    if destination != 'asc':
        zones = _child(sheet, 'BorderZones')
        _fill(zones, dict(Visible=False, HorzZones=0, VertZones=0, Standard=0, FontName='',
            FontSize=context.font_size, Border=False, HorzBorderSize=0, VertBorderSize=0,
            FontLineWidth=context.line_width), changed)
    if sheet.child('TitleBlocks') is None:
        changed.append(sheet.append(new_title_blocks()))

    _child(board, 'DRC')
    if destination == 'dip' and board.child('LastDRC') is None:
        changed.append(_last_rules(board))
    stack = board.child('LayerStackItems')
    if stack is None or not stack.children():
        proposal = default_stackup(board.select('Layers/Layer'))
        if stack is not None:
            view.remove(stack)
        board['LayerStackName'] = proposal.name
        board.append(proposal.items)
        for item, layer in proposal.copper_layers:
            item['Layer'] = layer
        changed.append(proposal.items)
    panel = _child(board, 'Panel')
    values = dict.fromkeys(('TabWidth', 'TabRadius', 'TabStep', 'HoleDiam', 'HoleStep', 'HoleInset',
                            'HoleKeepout', 'CombinedRadius'), 0)
    values.update(Type=0, TabsDone=False, KeepMaterial=False, BorderTabs=0, PanelizeSingle=False,
                  LeftGap=board.get('PanelDX', 0), RightGap=board.get('PanelDX', 0),
                  TopGap=board.get('PanelDY', 0), BottomGap=board.get('PanelDY', 0))
    _fill(panel, values, changed)
    for component in board.select('Components/Component'):
        supplier = component.child('Suppliers')
        if supplier is None and context.default_main_supplier:
            supplier = component.add('Suppliers')
        if supplier is not None:
            _fill(supplier, {'MainSupplier': context.default_main_supplier}, changed)
    # Binary cache envelopes always contain physical records, including symbol
    # sections without an associated footprint. An empty boundary definition
    # expresses that absence; copying the shared footprint would invent data.
    if destination == 'dip':
        for definition in board.select('CacheLib/Slots/Slot/Definition'):
            if definition.child('Pattern') is None:
                pattern = definition.append(new_pattern().bind_schema(library_records.PATTERN))
                library_records.bind_records(pattern)
                changed.append(pattern)
        prepare_primary_order(board, destination='dip', report=report)
    for table in board.select('Tables/Table'):
        options = _child(table, 'AutoUpdate')
        _fill(options, dict(RowType=0, PickOffX=0, PickOffY=0, Header=False, BomRowNumber=False,
            BomTotal=False, PickMirror=False, PickOrigin=False, AssemblyName='', Separator=''), changed)

    renamed, added = complete_user_markings(board)
    if renamed:
        info(report, 'empty-user-field-name', destination,
             'Named blank component fields Untitled in the output view.', renamed,
             recoverability='source field names remain unchanged')
    if added:
        info(report, 'user-field-marking-defaults', destination,
             'Added hidden global marking rules for component custom fields.', added,
             recoverability='field text and individual placements remain unchanged')
    if changed:
        info(report, 'binary-output-defaults' if destination == 'dip' else 'output-defaults',
             destination, 'Supplied required output settings for absent optional data.',
             tuple(dict.fromkeys(changed)), recoverability='stored source settings remain unchanged; context customizes fallbacks')
    if context.path_variables is not None:
        prepare_variable_paths(board, context.path_variables, project_dir=context.project_dir)
    normalize_frames(board, common_fiducials=settings['ShowCompFiducials'],
                     common_only=destination == 'dipxml', destination=destination, report=report)
    materialize_sizes(board, destination=destination, report=report)
    if destination in ('dip', 'asc'):
        materialize_markings(board, context=context, destination=destination, report=report)
    view.references.validate()
    return view, context
