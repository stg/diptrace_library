"""Line-oriented standalone ASC syntax with family-selected empty blocks."""
from .asc_text import number_text


def _value(argument):
    if argument.kind == 'number':
        return number_text(argument.value)
    if argument.kind != 'string':
        raise ValueError('ASC output requires projected numbers or text')
    return '"'+argument.value+'"'


def _render(node, indent, collections):
    if node.kind == 'ModelBody':
        result = [' '*indent+'(ModelBody']
        result.extend(' '*(indent+2)+_value(value) for value in node.arguments)
        result.append(' '*indent+')')
        return '\n'.join(result)
    head = '('+node.kind+''.join(' '+_value(value) for value in node.arguments)
    children = node.children()
    block = (children or node.kind in collections or node.kind in ('Category', 'Type')
             and node.parent is not None and node.parent.kind in ('Categories', 'Category'))
    if not block:
        return ' '*indent+head+')'
    result = [' '*indent+head]
    flat_drawing = False
    for child in children:
        if node.kind == 'Shapes':
            if child.kind == 'Shape':
                flat_drawing = True
                child_indent = indent+2
            else:
                child_indent = indent+4 if flat_drawing else indent+2
        else:
            child_indent = indent+2
        result.append(_render(child, child_indent, collections))
    result.append(' '*indent+')')
    return '\n'.join(result)


def dumps(document, *, collections):
    source, library = document.root.children()
    return _render(source, 0, collections)+'\n'+_render(library, 2, collections)+'\n()\n'
