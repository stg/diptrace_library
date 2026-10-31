"""Project a detached XML tree onto an explicitly supported older dialect.

These are serialization conventions, not historical properties of the model.
Paths distinguish library, board, title and global font settings: equal field
names do not imply equal units or availability.
"""
from ....common.conversion import info, warn
from ....common.xml_catalog import record_key


def _omit(node, name, *, default, rule, message, report):
    field = node.child(name)
    if field is not None:
        if field.values != (default,):
            warn(report, rule, 'dipxml', message, (field,))
        field.detach()


def _fonts(source, *, report):
    for node in source.walk(include_self=True):
        for floating, legacy in (('FontSizeFloat', 'Size' if node.kind == 'NameFont' else 'FontSize'),
                                  ('MarkingFontSizeFloat', 'MarkingFontSize')):
            if (field := node.child(floating)) is not None:
                if field.values != node.one(legacy).values:
                    warn(report, 'fractional-font-size', 'dipxml',
                         'Destination font sizes are rounded to integral values', (field,))
                field.detach()
        _omit(node, 'FontMono', default=False, rule='monospaced-font',
              message='Destination omits monospaced vector-font selection', report=report)


def adapt_library(library, *, version, report=None):
    """Apply library conventions independently of any owning PCB document."""
    if version.current_fields:
        return
    _fonts(library, report=report)
    for pad in library.select('Library/Patterns/Pattern/Pads/Pad'):
        if (field := pad.child('DefStyle')) is not None:
            inherited = pad['Style'] == pad.parent.parent.one('DefPad')['Style']
            if field.values != (inherited,):
                warn(report, 'pad-style-inheritance', 'dipxml',
                     'Destination infers pad inheritance from the selected style; independent geometry remains', (pad,))
            field.detach()
    if version.application == (4, 3, 0, 5):
        for shape in library.select('Library/Patterns/Pattern/Shapes/Shape'):
            _omit(shape, 'PadId', default=-1, rule='pattern-drawing-pad',
                  message='Destination omits a footprint drawing\'s pad association; geometry remains', report=report)


def _previous_rules(board, report):
    previous = board.child('LastDRC')
    if previous is None:
        return
    current = board.child('DRC')

    def settings(node):
        if node is None:
            return None
        copy = node.clone()
        copy.kind = 'DRC'
        for name in ('ShowList', 'RealTimeMode', 'DRCDone'):
            if (field := copy.child(name)) is not None:
                field.detach()
        return record_key(copy)

    if settings(previous) == settings(current):
        info(report, 'previous-design-rules', 'dipxml',
             'Destination omits previous check rules identical to the current rules', (previous,))
    else:
        warn(report, 'previous-design-rules', 'dipxml',
             'Destination omits the separate previous design-rule settings', (previous,))
    previous.detach()


def adapt_document(document, *, version, report=None):
    """Adapt only generated syntax, leaving all current design facts untouched."""
    if version.current_fields:
        return
    source = document.one('/Source')
    board = source.one('Board')
    _fonts(board, report=report)
    for pad in board.select('Components/Component/Pads/Pad'):
        # Loss is checked against current geometry before syntax projection;
        # ordinary pads infer their status, whereas vias initialize it false.
        if (field := pad.child('DefStyle')) is not None:
            field.detach()

    for net in board.select('Nets/Net'):
        _omit(net, 'AllowLoops', default=False, rule='net-loop-policy',
              message='Destination omits per-net loop permissions', report=report)
    for shape in board.select('Shapes/Shape'):
        _omit(shape, 'PictureFlipped', default=False, rule='picture-flipped',
              message='Destination omits the drawing picture-flip setting', report=report)
    if (settings := board.child('Settings')) is not None:
        _omit(settings, 'SchemNetClasses', default=False, rule='schematic-net-classes',
              message='Destination omits schematic net-class synchronization', report=report)
    for field in board.select('SheetSettings/*/Fields/Field'):
        _omit(field, 'FontColor', default=0, rule='title-font-color',
              message='Destination omits separate title text colors', report=report)
    _previous_rules(board, report)
    if version.application < (5, 2, 0, 0):
        for pour in board.select('CopperPours/CopperPour'):
            _omit(pour, 'TraceShieldGroup', default=-1, rule='pour-trace-shield',
                  message='Destination omits copper-pour trace-shield groups', report=report)
    if version.application == (4, 3, 0, 5):
        # These are the fields absent from this known output profile. Library
        # fields with similar names are handled in their separate vocabulary.
        for node in board.walk(include_self=True):
            for name in ('ShieldGroup', 'PosShieldGroup', 'NegShieldGroup'):
                _omit(node, name, default=-1, rule='shield-groups',
                      message='Destination omits shield-group assignments', report=report)
        for net in board.select('Nets/Net'):
            _omit(net, 'HiddenId', default=-1, rule='persistent-net-id',
                  message='Destination omits persistent net identifiers', report=report)
