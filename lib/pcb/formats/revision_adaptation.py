"""Project newer settings onto an older destination, leaving the design intact."""
from ...common.conversion import warn
from ...common.font_codec import compatibility_size


def prepare_binary_revision(document, *, version, report=None):
    """Adapt an already detached export view and report meaningful omissions."""
    if version >= 62:
        return
    board = document.one('/Board')
    rounded, mono, shields, trace_shields = [], [], [], []
    nodes = board.walk(include_self=True) if version < 61 else ()
    for node in nodes:
        if node.schema is None:
            continue
        for name in node.schema.fields:
            field = node.child(name)
            if field is None:
                continue
            if version < 61 and name.endswith('FontSize'):
                value = field.values[0]
                result = compatibility_size(value)
                if result != value:
                    field.set_values(result)
                    rounded.append(field)
            if version < 61 and name.endswith('FontMono') and field.values[0]:
                field.set_values(False)
                mono.append(field)
            if name.endswith('ShieldGroup') and field.values[0] >= 0:
                if name == 'TraceShieldGroup' and version < 58:
                    trace_shields.append(field)
                elif name != 'TraceShieldGroup' and version < 57:
                    shields.append(field)
    for rule, message, nodes in (
            ('fractional-font-size', 'Destination font sizes are rounded to integral values', rounded),
            ('monospaced-font', 'Destination omits monospaced vector-font selection', mono),
            ('shield-groups', 'Destination omits shield-group assignments', shields),
            ('pour-trace-shield', 'Destination omits copper-pour trace-shield groups', trace_shields)):
        if nodes:
            warn(report, rule, 'dip', message, nodes)
    if version < 55:
        panel = board.one('Panel')
        if any(panel[name] != board.get(source, 0) for name, source in
               (('LeftGap', 'PanelDX'), ('RightGap', 'PanelDX'),
                ('TopGap', 'PanelDY'), ('BottomGap', 'PanelDY'))):
            warn(report, 'panel-side-gaps', 'dip',
                 'Destination derives panel side gaps from horizontal and vertical board spacing', (panel,))
    if version < 56:
        nodes = [net.one('HiddenId') for net in board.select('Nets/Net') if net.get('HiddenId', -1) != -1]
        if nodes:
            warn(report, 'persistent-net-id', 'dip', 'Destination omits persistent net identifiers', nodes)
    if version < 59:
        nodes = [shape.one('PictureFlipped') for shape in board.select('Shapes/Shape') if shape.get('PictureFlipped', False)]
        if nodes:
            warn(report, 'picture-flipped', 'dip', 'Destination omits the drawing picture-flip setting', nodes)
    if version < 60 and board.get('SchemNetClasses', False):
        warn(report, 'schematic-net-classes', 'dip', 'Destination omits schematic net-class synchronization',
             (board.one('SchemNetClasses'),))
    if version < 62:
        nodes = [net.one('AllowLoops') for net in board.select('Nets/Net') if net.get('AllowLoops', False)]
        if nodes:
            warn(report, 'net-loop-policy', 'dip', 'Destination omits per-net loop permissions', nodes)
