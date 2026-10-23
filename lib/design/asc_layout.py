"""format schematic ASC layout from public records, without source-text replay."""
from .asc import _value


# These public array/count records keep an opening and closing line even when
# empty. Scalar fields use one line. The cl_ dialect shares most array names.
_ARRAYS=set('''Pages Components Pins Shapes Nets Parts Lines Buses Numbers Groups
Tables ColWidths RowHeights Cells NetClasses DifferentialPairs ShowUserfield_Global
PageConnectors UserFields ModelBody Component_CategoryTypes InternalConnections
PadTerminalCount PadMask_TopSegments PadMask_BotSegments PadPoints PadPoints_New
Pattern_Groups Pads Points Points_New Holes Dimensions Pattern_CategoryTypes
PossibleNames TextLine ShapePoints signals sim_ac sim_dc sim_tran sim_noise
ProjectLibs_Folders ProjectLibs_Libs DesignCache_Links cl_Categories cl_Subfolders
cl_Components cl_CategoryTypes cl_Groups cl_UserFields cl_ModelBody
cl_InternalConnections cl_Pattern_Groups cl_Pads cl_Point cl_Points cl_Points_New
cl_Shapes cl_Pins
cl_PadPoints cl_PadPoints_New cl_PadTerminalCount cl_PadMask_TopSegments
cl_PadMask_BotSegments cl_Holes cl_Dimensions cl_PossibleNames cl_TextLine
cl_ShapePoints Design_Cache_specific'''.split())


def _render(node,indent):
    children=node.children()
    parent=node.parent.kind if node.parent else ''
    multiline=bool(children) or node.kind in _ARRAYS or (parent,node.kind) in (
        ('cl_Categories','cl_Category'),('cl_Category','cl_Type'))
    string_rows = node.kind in ('ModelBody', 'cl_ModelBody')
    head='('+node.kind+('' if string_rows else ''.join(' '+_value(value,False) for value in node.arguments))
    if not multiline:
        return head+')'
    lines=[]
    if string_rows:
        lines.extend('\r\n'+' '*(indent+2)+_value(value,False) for value in node.arguments)
    footprint_drawings=(node.kind in ('Shapes','cl_Shapes') and parent in ('Pattern','cl_Pattern'))
    for child in children:
        # Footprint drawing properties are ASC siblings, but format layout
        # indents them below the preceding flat Shape header.
        extra=2 if footprint_drawings and child.kind not in ('Shape','cl_Shape') else 0
        if node.kind=='Pad' and child.kind=='PadPoints_New':
            extra=-2
        elif node.kind=='Points' and parent=='Pad':
            extra=-2
        elif node.kind=='cl_Point' and parent=='cl_Shapes':
            extra=-2
        elif node.kind=='UserFields' and parent=='Pattern':
            extra=-2
        elif (node.kind=='Shape' and child.kind=='Points' and node.parent is not None
              and node.parent.parent is not None and node.parent.parent.kind=='Schematic'):
            extra=2
        elif node.kind in ('PadMask_TopSegments','PadMask_BotSegments',
                            'cl_PadMask_TopSegments','cl_PadMask_BotSegments'):
            extra=2
        column=indent+2+extra
        lines.append('\r\n'+' '*column+_render(child,column))
    body=''.join(lines)
    return head+body+'\r\n'+' '*indent+')'


def dumps(document):
    """Dumps."""
    return ''.join(_render(node,0)+'\r\n' for node in document.root.children())
