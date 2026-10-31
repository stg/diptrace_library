"""Prepare inactive edited data on a detached PCB output view."""
from ...common.conversion import info
from ...common.inactive_output import report_omitted_records
from ..model import library_records
from .output_validation import field_value


# References owned by discarded check/table/dimension records must leave before
# their possible targets. Ordinary identity-aware removal preserves every live
# binding and rejects a retained reference into omitted content.
XML_COLLECTIONS = (
    'DesignErrors/DesignError', 'Tables/Table', 'Dimensions/Dimension',
    'CopperPours/CopperPour', 'Shapes/Shape', 'DifferentialPairs/DifferentialPair',
    'Nets/Net', 'Components/Component',
)


def _empty_drawing(node):
    if node.kind != 'Shape' or field_value(node, 'Type') != 0:
        return False
    if node.get('Name', '') or any(any(row.values) for row in node.select('TextLine/pt')):
        return False
    if any(node.select(path) for path in ('Points/pt', 'Points_New/pt')):
        return False
    if any(node.get(name, '') for name in ('Picture_File', 'Picture_File_Variable')):
        return False
    if node.child('PictureVector') is not None or node.child('UnresolvedKeys') is not None:
        return False
    for name in ('Group', 'PadId', 'ShieldGroup', 'Net', 'BitmapIndex'):
        value = node.get(name)
        if value is None or isinstance(value, int) and value < 0:
            continue
        return False
    return True


def compact_length_results(document, *, destination, report=None):
    """Class settings remain independent when their check is switched off."""
    omitted = [results for owner in document.select('/Board/NetClasses/NetClass')
               if not owner.get('CheckLength', False)
               and (results := owner.child('LengthResults')) is not None]
    if omitted:
        info(report, 'obsolete-class-length-results', destination,
             'Unchecked net classes omit calculated length results.', omitted,
             recoverability='source results and class settings remain; results can be recalculated when checking is enabled')
        for node in omitted:
            document.remove(node)


def compact_xml_board(document, *, report=None):
    """Remove inactive board objects from an already detached output view.

    This deliberately excludes cached definitions, groups and removed-pair
    restoration data. Their activation flags have different format meanings.
    """
    board = document.one('/Board')
    omitted = [node for path in XML_COLLECTIONS for node in board.select(path)
               if node.get('Enabled', True) is False]
    if omitted:
        # Capture original paths before removal changes the output-view ordinals.
        report_omitted_records(omitted, destination='dipxml', report=report, empty_drawing=_empty_drawing)
        for node in omitted:
            document.remove(node)


def compact_xml_patterns(document, *, report=None):
    """Compact physical member slots while retaining each template definition.

    Pads have current identities rather than saved slot flags. Groups and
    template metadata remain independent of the drawing/hole/dimension slots.
    """
    board = document.one('/Board')
    cached = library_records.patterns(board)
    placed = board.select('Components/Component/Pattern')
    omitted = []
    for patterns, rule in ((cached, 'inactive-library-records'), (placed, 'inactive-records')):
        records = []
        for pattern in patterns:
            records.extend(node for node in pattern.select('Dimensions/Dimension') if not node['Enabled'])
            records.extend(node for node in pattern.select('Shapes/Shape') if node['Type'] <= 0)
            records.extend(node for node in pattern.select('Holes/Hole') if not node['Enabled'])
        report_omitted_records(records, destination='dipxml', report=report, rule=rule,
                               empty_drawing=_empty_drawing)
        omitted.extend(records)
    for node in omitted:
        document.remove(node)
