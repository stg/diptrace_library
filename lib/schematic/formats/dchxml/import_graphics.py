"""Schematic drawings read directly into own named physical drawing data."""
from .components import (HORZ, VERT)
from .graphics import (DRAWING_TYPES)
from .import_library_values import (read_path)
from .import_values import (enum_value, length, point, replace_rows)
from ....common.model import (Element)
from ...model.new import (fields)
from .fonts import (read_font, read_text_extent)


def read_drawings(record, schematic, *, units, sheets):
    result = []
    for index, source in enumerate(record.rows('Shapes', 'Shape')):
        source.integer('Id', index)
        kind = enum_value(source.value('Type', 'None'), DRAWING_TYPES)
        sheet = source.integer('Sheet', 0)
        if sheet not in sheets:
            raise ValueError(f'{source.node.path}: unresolved sheet Id {sheet}')
        drawing = Element('Shape', index)
        fields(drawing, Enabled=True, Selected=source.boolean('Selected', False),
               Type=kind, FontSize=source.integer('FontSize', 6), FontColor=source.integer('FontColor', 0),
               Color=source.integer('Color', 0), BrushColor=0, FontType=0, Page=sheets[sheet],
               Group=source.integer('Group', -1),
               PenWidth=length(source.number('LineWidth'), units) if source.has('LineWidth') else -1,
               FontName=source.text('FontName', ''), BitmapIndex=-1,
               RelatedNet=source.integer('NetId', -1), RelatedBus=source.integer('BusId', -1),
               Locked=source.boolean('Locked', False), VectorFont=source.boolean('FontVector', True),
               FontWidth=source.number('FontWidth', -1), FontScale=source.number('FontScale', 1),
               TextAngle=source.number('Angle', 0), LineSpacing=source.number('LineSpacing', 1.2))
        for public, own, labels in (('HorzAlign', 'TextHorz', HORZ), ('VertAlign', 'TextVert', VERT),
                                    ('TextAlign', 'TextAlign', HORZ)):
            drawing.add(own, enum_value(source.value(public, labels[0]), labels, negative=labels[-1]))
        for public, own in (('PictureWidth', 'Picture_Width'), ('PictureHeight', 'Picture_Height')):
            drawing.add(own, length(source.number(public, 0), units))
        fields(drawing, Picture_Transparent=source.number('PictureTransparent', 0),
               Picture_Proportions=source.boolean('PictureProportions', False), Picture_File='', Picture_File_Variable='')
        drawing.add('PictureFlipped', source.boolean('PictureFlipped', False))
        read_font(source, drawing)
        read_text_extent(source)
        filename = source.take('PictureFile')
        if filename is not None:
            actual, variable = read_path(filename)
            drawing.set_field('Picture_File', actual)
            drawing.set_field('Picture_File_Variable', variable)
        points = drawing.add('Points_New')
        for item in source.rows('Points', 'Point'):
            points.add('pt', *point(item, units))
            item.finish()
        lines = drawing.add('TextLine')
        for item in source.rows('TextLines', 'TextLine'):
            lines.add('pt', item.content())
            item.finish(allow_text=True)
        source.finish()
        result.append(drawing)
    replace_rows(schematic, 'Shapes', result)
