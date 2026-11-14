"""Compose current standalone LIB streams from the owned authoring model."""
from ....common.catalog_codec import write_categories,write_category_types
from ....common.conversion import export_diagnostics,warn
from ....common.footprint_codec import write_terminals, write_mask_segments
from ....common.library_model import write_library_model
from ....common.library_physical_output import write_library_pads, write_library_graphics, write_library_groups
from ....common.library_versions import library_text_layout
from ....common.font_codec import compatibility_size
from ..export_view import prepare_export,library_omissions
from .writer import Writer


def _parameters(writer,pattern):
    writer.fields(pattern,'boolean','VariableParameter1 VariableParameter2 VariableParameter3 VariableParameter4')
    writer.fields(pattern,'number','Width Height Spacing1 Spacing2')
    writer.field(pattern,'VariableParameter5','boolean')
    writer.field(pattern,'Spacing3','number')
    writer.field(pattern,'LockProperties','boolean')
    writer.fields(pattern,'integer','PatternOrientation Number1 Number2 Type')
    writer.fields(pattern,'number','PadWidth PadHeight')
    writer.field(pattern,'PadShape','integer')
    writer.field(pattern,'SurfacePad','boolean')
    writer.fields(pattern,'number','PadHole PadHoleH')
    writer.field(pattern,'PadHoleType','integer')
    writer.rows(pattern.child('PadPoints'),'pt','number number')
    writer.fields(pattern,'number','PadCorner PadShape_X PadShape_Y')
    write_terminals(writer,pattern)
    writer.fields(pattern,'number','PadMask_Percent PadMask_EdgeGap PadMask_SegmentGap PadMask_SegmentSide')
    write_mask_segments(writer,pattern)
    writer.fields(pattern,'integer','TopMask_State BotMask_State TopPaste_State BotPaste_State')
    writer.fields(pattern,'number','CustomSwell_New CustomShrink_New')


def _metadata(writer,pattern,*,layout):
    for name in ('Name','RefDes','Value'):
        writer.text(pattern.get(name,''))
    writer.fields(pattern,'number','OriginX OriginY')
    writer.fields(pattern,'boolean','OriginCross OriginCircle')
    writer.fields(pattern,'integer','OriginCommon OriginCourtyard')
    writer.fields(pattern,'text','Name_Description Name_Unique RecoveryCode')
    writer.fields(pattern,'boolean','RecoveryCode_Generator RecoveryCode_Model')
    writer.field(pattern,'Pattern_Manufacturer','text')
    write_library_groups(writer,pattern.one('Pattern_Groups'),layout=layout)
    writer.rows(pattern.one('UserFields'),'UserField','text text integer')
    write_library_model(writer,pattern,variable_filename=True,authoring_properties=True,keep_pins=True)
    writer.field(pattern,'Mounting','integer')
    writer.text(pattern.get('Datasheet',''))
    writer.fields(pattern,'text','Pattern_CategoryName')
    writer.field(pattern,'Pattern_CategoryIndex','integer')
    write_category_types(writer,pattern,'Pattern_CategoryTypes')
    writer.rows(pattern.child('PossibleNames'),'PossibleName','text')
    verification=pattern['Verification']
    writer.integer(len(verification))
    for flag in verification:
        writer.boolean(flag)
    supplier=pattern.child('Suppliers')
    for name in ('PartNumber','Manufacturer','Pattern','Supplier','Currency'):
        writer.text(supplier.get(name,'') if supplier is not None else '')


def _adapt_revision(document,writer):
    for pattern in document.select('/Library/Patterns/Pattern'):
        if writer.version < 25:
            linked=[shape for shape in pattern.select('Shapes/Shape') if shape['PadId'] >= 0]
            if linked:
                warn(writer.report,'drawing-pad-reference','lib','This LIB revision omits drawing-to-pad associations',linked)
        if writer.version < 26:
            for node in (*pattern.select('Shapes/Shape'),*pattern.select('Dimensions/Dimension')):
                size=node['FontSize']
                rounded=compatibility_size(size)
                if size != rounded:
                    node['FontSize']=rounded
                    warn(writer.report,'fractional-font-size','lib','Destination font sizes are rounded to integral values',(node,))
                if node.get('FontMono',False):
                    node['FontMono']=False
                    warn(writer.report,'monospaced-font','lib','Destination omits monospaced vector-font selection',(node,))


@export_diagnostics('lib')
def encode(document,*,version=None,report=None,text_layout=None):
    """Write declared current revisions; no input bytes or history are replayed."""
    writer=Writer(version,report=report)
    document=prepare_export(document,destination='lib',report=report)
    library=document.one('/Library')
    library_omissions(library,destination='lib',report=report)
    _adapt_revision(document,writer)
    layout=text_layout if text_layout is not None else library_text_layout(current=writer.version >= 26)
    patterns=library.select('Patterns/Pattern')
    writer.header(library,len(patterns))
    write_categories(writer,library)
    for pattern in patterns:
        _parameters(writer,pattern)
        write_library_pads(writer,pattern)
        write_library_graphics(writer,pattern,drawing_pad_links=writer.version >= 25,extended_fonts=writer.version >= 26)
        _metadata(writer,pattern,layout=layout)
    return bytes(writer.buffer)
