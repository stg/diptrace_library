"""Line-oriented standalone ASC output, including empty collection blocks."""
from ....common.asc_library_output import dumps as render


COLLECTIONS = frozenset('''Library Categories Patterns Pads Shapes Holes Layers UserFields
Dimensions Pattern_Groups PadPoints Points Points_New PadPoints_New PadTerminalCount
ShapePoints PadMask_TopSegments PadMask_BotSegments CategoryTypes PossibleNames TextLines'''.split())


def dumps(document):
    return render(document, collections=COLLECTIONS)
