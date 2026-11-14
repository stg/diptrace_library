"""Current standalone physical arrays with caller-owned family revision gates."""
from . import footprint_objects, footprint_records
from .model import Element
from .footprint_codec import write_pad_geometry, write_pad_extensions
from .dimension_codec import write_dimension_properties
from .drawing_codec import write_text_properties
from .library_group_bounds import rows as group_rows


def write_library_groups(writer, collection, *, layout=None):
    rows = tuple(group_rows(collection, layout=layout)) if collection is not None else ()
    writer.integer(len(rows))
    for enabled, index, x, y in rows:
        writer.boolean(enabled)
        writer.integer(index)
        writer.number(x)
        writer.number(y)


def write_library_pads(writer, pattern):
    pads=pattern.select('Pads/Pad')
    boundary=footprint_objects.new_pad()
    writer.integer(len(pads)+2)
    for index,pad in enumerate((boundary,*pads,boundary)):
        writer.integer(index if 0 < index <= len(pads) else -1)
        writer.fields(pad,'number','X Y')
        writer.fields(pad,'text','StringNumber Name')
        write_pad_geometry(writer,pad)
        writer.fields(pad,'boolean','Locked Sided')
        writer.fields(pad,'integer','DisableTopMask DisableBottomMask DisableTopPaste DisableBottomPaste')
        writer.fields(pad,'number','CustomSwell_New CustomShrink_New')
        writer.field(pad,'Group','integer')
        write_pad_extensions(writer,pad)


def _font_extension(writer, owner, extended_fonts):
    if extended_fonts:
        writer.boolean(owner.get('FontMono',False))
        writer.field(owner,'FontSize','number')


def write_library_graphics(writer, pattern, *, drawing_pad_links, extended_fonts):
    shapes=pattern.select('Shapes/Shape')
    boundary=footprint_objects.new_pattern_drawing()
    writer.integer(len(shapes)+2)
    for shape in (boundary,*shapes,boundary):
        writer.field(shape,'Type','integer')
        writer.field(shape,'Locked','boolean')
        writer.field(shape,'Layer','integer')
        writer.field(shape,'FontName','text')
        writer.field(shape,'VectorFont','boolean')
        writer.field(shape,'FontSize','integer')
        writer.fields(shape,'number','FontScale FontWidth')
        writer.field(shape,'TextShow','integer')
        writer.field(shape,'Width','number')
        writer.rows(shape.child('Points_New'),'pt','number number')
        write_text_properties(writer,shape)
        writer.field(shape,'AllLayers','boolean')
        writer.field(shape,'Group','integer')
        if drawing_pad_links:
            selected=shape['PadId']
            writer.integer(0 if selected < 0 else selected)
        _font_extension(writer,shape,extended_fonts)
    holes=pattern.select('Holes/Hole')
    boundary=Element('Hole',False,False,0,0,0,0,-1).bind_schema(footprint_records.HOLE)
    writer.integer(len(holes)+2)
    for hole in (boundary,*holes,boundary):
        writer.field(hole,'Enabled','boolean')
        writer.fields(hole,'number','X Y Diam HoleDiam')
        writer.field(hole,'Locked','boolean')
        writer.field(hole,'Group','integer')
    dimensions=pattern.select('Dimensions/Dimension')
    writer.integer(len(dimensions))
    for dimension in dimensions:
        writer.fields(dimension,'boolean','Enabled Locked')
        write_dimension_properties(writer,dimension)
        writer.field(dimension,'Group','integer')
        _font_extension(writer,dimension,extended_fonts)
