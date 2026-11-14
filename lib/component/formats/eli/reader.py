"""Named standalone component records over the shared scalar/storage codecs."""
from ....common.binary_records import RecordReader
from ....common import (drawing_records, footprint_records, group_records,
                       library_metadata, symbol_records)
from .binary import Cursor


class Reader(RecordReader, Cursor):
    source_format = 'eli'
    retain_source = False

    def record_definition(self, node):
        if node.kind == 'Pattern':
            return footprint_records.PATTERN
        if (record := footprint_records.nested_definition(node)) is not None:
            return record
        if node.parent is not None and node.parent.kind == 'Shapes' and node.kind == 'Shape':
            owner = node.parent.parent
            return symbol_records.DRAWING if owner is not None and owner.kind == 'Part' else footprint_records.PATTERN_SHAPE
        if node.parent is None:
            return None
        return {
            ('Pads', 'Pad'): footprint_records.PAD,
            ('Pins', 'Pin'): symbol_records.PIN,
            ('Holes', 'Hole'): footprint_records.HOLE,
            ('Dimensions', 'Dimension'): footprint_records.DIMENSION,
            ('Pattern_Groups', 'pt'): group_records.LOCAL_GROUP,
            ('Points_New', 'pt'): drawing_records.POINT,
            ('TextLine', 'pt'): drawing_records.TEXT_LINE,
            ('Library', 'Categories'): library_metadata.CATEGORIES,
            ('Categories', 'Category'): library_metadata.CATALOG_CATEGORY,
            ('Category', 'Type'): library_metadata.CATALOG_TYPE,
            ('Type', 'Subtype'): library_metadata.CATALOG_SUBTYPE,
            ('Library', 'Subfolders'): library_metadata.SUBFOLDERS,
            ('Subfolders', 'Folder'): library_metadata.SUBFOLDER,
            ('Parts', 'Part'): symbol_records.SYMBOL,
        }.get((node.parent.kind, node.kind))
