"""Named standalone library decoding over the shared scalar/storage codecs."""
from ....common.binary_records import RecordReader
from ....common import footprint_records as physical
from ....common import drawing_records, group_records, library_metadata
from .binary import Cursor


class Reader(RecordReader, Cursor):
    source_format = 'lib'
    retain_source = False

    def record_definition(self, node):
        if node.kind == 'Pattern':
            return physical.PATTERN
        if (record := physical.nested_definition(node)) is not None:
            return record
        parent = node.parent
        if parent is None:
            return None
        return {
            ('Pads', 'Pad'): physical.PAD,
            ('Shapes', 'Shape'): physical.PATTERN_SHAPE,
            ('Holes', 'Hole'): physical.HOLE,
            ('Dimensions', 'Dimension'): physical.DIMENSION,
            ('Pattern_Groups', 'pt'): group_records.LOCAL_GROUP,
            ('Points_New', 'pt'): drawing_records.POINT,
            ('TextLine', 'pt'): drawing_records.TEXT_LINE,
            ('Categories', 'Category'): library_metadata.CATALOG_CATEGORY,
            ('Category', 'Type'): library_metadata.CATALOG_TYPE,
            ('Type', 'Subtype'): library_metadata.CATALOG_SUBTYPE,
        }.get((parent.kind, node.kind))
