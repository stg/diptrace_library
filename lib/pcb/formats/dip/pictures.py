"""Modernize picture sources without reading external image companions."""
from ....common.picture_sources import picture_reference_index


def modernize_picture_sources(decoded):
    for item in decoded.upgrades.drawings:
        shape = item.drawing
        if shape['Type'] == 7:
            index = item.bitmap_index if decoded.header.version < 47 else -1
            shape.add('BitmapIndex', picture_reference_index(shape, index))
