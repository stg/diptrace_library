"""Consume custom-layer keys and positional visibility into current layer data."""
from ....common.conversion import import_notice
from ....common.references import Index
from ...model.non_signal_layers import ROLE
from ..errors import PcbError


def prepare(board, removed):
    layers = board.select('NonSignals/NonSignal')
    keys = [layer.values[2] for layer in layers]
    explicit_order = any(key >= 0 and key != index for index, key in enumerate(keys))
    by_key = {}
    for key, layer in zip(keys, layers):
        if key >= 0:
            by_key.setdefault(key, layer)

    def target(key):
        if 0 <= key < len(layers) and (keys[key] == key or keys[key] < 0 and not explicit_order):
            return layers[key]
        return by_key.get(key) if key >= 0 else None

    panel = board.child('Settings')
    panel = panel.child('LayerPanel') if panel is not None else None
    choices = panel.child('NonSignals') if panel is not None else None
    if choices is not None:
        seen = set()
        for row in choices.children():
            if (row.kind != 'Item' or len(row.values) != 2 or row.children()
                    or type(row.values[0]) is not int or row.values[0] < 0 or type(row.values[1]) is not bool
                    or row.values[0] in seen):
                raise PcbError('non-signal visibility requires unique positions and boolean values')
            position, visible = row.values
            seen.add(position)
            if position < len(layers):
                layers[position].add('Visible', visible)
        if any(position >= len(layers) for position in seen):
            import_notice('info', 'non-signal-display-capacity', 'Discarded display entries without a current custom layer',
                          (choices,), recoverability='visibility of every current layer is retained')
        choices.detach()

    links, issues, normalized = [], [], []
    for kind, active_layer, fallback in (('Table', 4, 0), ('Dimension', 15, 13)):
        for source in board.select(kind+'s/'+kind):
            if source in removed:
                continue
            field = source.child('NonSignal')
            if field is None:
                continue
            if len(field.values) != 1 or type(field.values[0]) is not int:
                raise PcbError('non-signal selection requires one integer key')
            key = field.values[0]
            selected = target(key)
            if selected is None and source.get('Layer', 0) == active_layer:
                if layers:
                    selected = layers[-1]
                else:
                    source.one('Layer').set_values(fallback)
                normalized.append(source)
            elif selected is None and key >= 0 and not (key == 0 and not layers):
                issues.append((source, source.add('UnresolvedNonSignal', key)))
            if selected is not None:
                links.append((source, selected))
            field.detach()
    if normalized:
        import_notice('info', 'non-signal-layer-normalization',
            'Replaced unavailable active custom-layer selections with the last layer or the standard layer family',
            normalized, recoverability='current table and dimension contents are retained')
    return links, issues


def bind(document, plan):
    board = document.one('/Board')
    links, issues = plan
    for source, target in links:
        document.references.bind(source, target, role=ROLE, preserve=True)
    for source, field in issues:
        scope = board.child('NonSignals')
        document.references.note(source, ROLE+': remembered layer cannot be resolved', Index(field),
                                 collections=(scope if scope is not None else board,))
    if issues:
        import_notice('warning', 'unresolved-non-signal-layer', 'Remembered custom-layer selections are unavailable',
            (source for source, _ in issues), recoverability='assign NonSignalLayer to repair or clear the selection')
