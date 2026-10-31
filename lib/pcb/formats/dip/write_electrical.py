"""Binary classifications, material stack and supplied electrical calculations."""
from ....common.catalog_codec import write_category_types
from ....common.model import Element
from ...model import board_rules, length_matching, pad_records, teardrops
from ..errors import PcbError
from ..output_indices import OutputIndices, pad_endpoint
from ..output_validation import check_tree


def write_metadata(writer, board, outputs):
    for output in outputs:
        writer.field(output.pattern.one('Model3D'), 'Units', 'integer')
    for pour in board.select('CopperPours/CopperPour'):
        writer.field(pour, 'RatlineMode', 'integer')
    for output in outputs:
        component, pattern = output.component, output.pattern
        writer.field(pattern, 'Mounting', 'integer')
        writer.fields(component, 'text', 'Datasheet Manufacturer')
        writer.field(pattern, 'Pattern_CategoryName', 'text')
        writer.field(pattern, 'Pattern_CategoryIndex', 'integer')
        write_category_types(writer, pattern, 'Pattern_CategoryTypes')
        writer.field(component, 'Component_CategoryName', 'text')
        writer.field(component, 'Component_CategoryIndex', 'integer')
        write_category_types(writer, component, 'Component_CategoryTypes')
        writer.rows(pattern.child('PossibleNames'), 'PossibleName', 'text')


def write_layer_stack(writer, board, outputs):
    if (source := board.child('LayerStackItems')) is not None:
        check_tree(source, board_rules.COLLECTIONS['LayerStackItems'], destination='DIP')
    writer.field(board, 'LayerStackName', 'text')
    rows = board.select('LayerStackItems/LayerStackItem')
    writer.integer(len(rows))
    for row in rows:
        writer.field(row, 'Lay', 'integer')
        material = row.one('Material')
        writer.field(material, 'Name', 'text')
        writer.field(material, 'Type', 'integer')
        writer.field(material, 'VariableThickness', 'boolean')
        writer.fields(material, 'number', 'Thickness Constant TraceWidth')
    for output in outputs:
        for pad in output.pads:
            writer.field(pad, 'SignalDelay', 'number')
    writer.fields(board.one('Settings'), 'boolean', 'StackLength SignalDelayLength')


def _connections(writer, owner):
    rows = owner.select('Rules/Rule') if owner is not None else ()
    writer.integer(len(rows))
    for row in rows:
        writer.field(row, 'NetId', 'integer')
        for end in (1, 2):
            for value in pad_endpoint(row, end):
                writer.integer(value)
        writer.field(row, 'Length', 'number')
        writer.field(row, 'Error', 'boolean')


def _length_policy(writer, owner, indices):
    if owner.schema is length_matching.POLICY:
        check_tree(owner, length_matching.POLICY, destination='DIP')
        writer.field(owner, 'Name', 'text')
        writer.fields(owner, 'number', 'FixedLength Delta')
        selected = owner['Class'] if owner.kind == 'MainLengthRule' else None
        results, net_class, kind = owner, indices.class_number(selected), int(selected is not None)
    else:
        writer.field(owner, 'Name', 'text')
        writer.fields(owner, 'number', 'FixedLength LengthDelta')
        results, net_class, kind = owner.child('LengthResults'), indices.class_number(owner), 1
        if results is not None:
            check_tree(results, length_matching.RESULTS, destination='DIP')
    error = results['AnyError'] if results is not None else False
    writer.boolean(error)
    writer.boolean(error)
    writer.integer(net_class)
    writer.integer(kind)
    _connections(writer, results)


def write_length_rules(writer, board, *, indices=None):
    indices = indices or OutputIndices(board)
    main = board.child('MainLengthRule')
    if main is None:
        main = Element('MainLengthRule').bind_schema(length_matching.POLICY)
    _length_policy(writer, main, indices)
    if (source := board.child('LengthRules')) is not None:
        check_tree(source, length_matching.POLICIES, destination='DIP')
    for net_class in indices.classes:
        if net_class.child('LengthResults') is not None and not net_class['CheckLength']:
            raise PcbError(f'{net_class.path}: inactive class length results require normalization')
    writer.integer(len(indices.length_policies))
    for owner in indices.length_policies:
        _length_policy(writer, owner, indices)
    for net_class in indices.classes:
        writer.fields(net_class, 'number', 'LengthDelta FixedLength')
    for net in board.select('Nets/Net'):
        writer.field(net, 'Highlighted', 'boolean')


def _teardrop_parameters(writer, owner):
    source = owner.child('TeardropParams')
    if source is None:
        source = Element('TeardropParams').bind_schema(pad_records.TEARDROP)
    check_tree(source, pad_records.TEARDROP, destination='DIP')
    writer.fields(source, 'integer', 'PadVia Smd Trace TJunc')
    writer.fields(source, 'number', 'PadViaWidth PadViaLength SmdWidth SmdLength TraceLength TJuncLength')


def write_teardrops(writer, board, outputs):
    """Supplied polygons and current trace memberships, without recalculation."""
    for output in outputs:
        for pad in output.pads:
            _teardrop_parameters(writer, pad)
    for net in board.select('Nets/Net'):
        _teardrop_parameters(writer, net)
        for trace in net.select('Traces/Trace'):
            source = trace.child('ConnectedTeardrops')
            if source is not None:
                check_tree(source, teardrops.MEMBERS, destination='DIP')
            writer.rows(source, 'Item', 'integer')
        source = net.child('Teardrops')
        if source is not None:
            check_tree(source, teardrops.TEARDROPS, destination='DIP')
        rows = net.select('Teardrops/Teardrop')
        writer.integer(len(rows))
        for row in rows:
            writer.field(row, 'Lay', 'integer')
            writer.fields(row, 'number', 'DrawX DrawY')
            writer.rows(row.child('Points'), 'pt', 'number number')
