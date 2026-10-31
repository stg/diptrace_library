"""Document-level ASC views and compatibility fields over current public data."""
from ....common.model import (Element, Value)
from .projection import (ProjectionError, _head, _ordered, _plain, _value, _visible)
from ....common.cell_text import (cell_text_lines, cell_lines, asc_cell_text)
from ....common.asc_library import project_library_paths as _project_library_paths


from ...model.vocabulary import (PAGE_CONNECTOR_FIELDS)
from ...model.vocabulary import (BUS_FIELDS)
from ...model.vocabulary import (BUS_LINE_FIELDS)
from ...model.vocabulary import (TABLE_FIELDS)
from ...model.vocabulary import (CELL_FIELDS)


def project_page_connector(connector):
    return _ordered(connector,PAGE_CONNECTOR_FIELDS)


def project_bus(bus):
    def lines(node):
        result=_head(node)
        for line in _visible(node):
            if line.kind != 'Line':
                raise ProjectionError(f'{node.path}: expected Line, found {line.kind}')
            result.append(_ordered(line,BUS_LINE_FIELDS))
        return result
    return _ordered(bus,BUS_FIELDS,{'Lines':lines})


def project_group(group):
    return _ordered(group,('Enabled','Selected'))


def project_library_paths(container,kind):
    """Flatten owned path records into format Folder/Folder_Variable siblings."""
    try:
        return _project_library_paths(container,kind,convert=_value,visible=_visible,variable_fallback=True)
    except ValueError as error:
        raise ProjectionError(str(error)) from error


def project_table(table):
    columns=len(table.one('ColWidths').children('pt'))
    rows=len(table.one('RowHeights').children('pt'))
    def sizes(node):
        result=_plain(node)
        result.set_values()
        return result
    def cells(node):
        source=_visible(node)
        if any(cell.kind != 'Cell' for cell in source) or len(source) != columns*rows:
            raise ProjectionError(f'{node.path}: cells do not form the declared rectangular grid')
        result=Element('Cells',columns)
        for index,cell in enumerate(source):
            column,row=divmod(index,rows)
            unknown=[n.kind for n in _visible(cell) if n.kind not in CELL_FIELDS]
            if unknown:
                raise ProjectionError(f'{cell.path}: no cell projection for {unknown}')
            # Current flat array order is column-major. An imported positional
            # annotation is provenance, not a second editable grid identity.
            values=cell_lines(cell)
            record=Element('Cell',rows,column,row,*map(_value,cell.arguments))
            for name in CELL_FIELDS:
                if name == 'Text':
                    record.add(name,_value(Value.of(asc_cell_text(cell))))
                elif name == 'TextLine':
                    text=record.add(name)
                    for line in values:
                        text.add('pt',_value(Value.of(line)))
                else:
                    fields=cell.children(name)
                    if len(fields) != 1:
                        raise ProjectionError(f'{cell.path}: expected one {name}')
                    record.append(_plain(fields[0]))
            result.append(record)
        return result
    return _ordered(table,TABLE_FIELDS,{'ColWidths':sizes,'RowHeights':sizes,'Cells':cells})


def legacy_global_fields(schematic, *, initial=None):
    """Generate two compatibility slots from current modern label choices."""
    names=('ShowText','ShowText2','TextAlign','TextAlign2','FieldName1','FieldName2')
    fields = dict(zip(names, initial or (0, 0, 0, 0, '', '')))
    choices=[]
    for name, mode in (('ShowRefDes_Global',2),('ShowName_Global',1),('ShowValue_Global',3),
                       ('ShowManufacturer_Global',6),('ShowDatasheet_Global',7)):
        values=schematic.one(name).values
        if values[0] == 1:
            if name == 'ShowName_Global' and values[1] != 1:
                mode=4
            choices.append((mode,values[-1],None))
    for user in schematic.one('ShowUserfield_Global').children('pt'):
        name,key,state,position=user.values
        if state == 1:
            choices.append((5,position,name))
    for index,(mode,alignment,name) in enumerate(choices[:2]):
        suffix='2' if index else ''
        fields['ShowText'+suffix]=mode
        fields['TextAlign'+suffix]=alignment
        if name is not None:
            fields['FieldName'+str(index+1)]=name
    alignments={1:0,2:1,3:5,5:2,7:3}
    for name in ('TextAlign','TextAlign2'):
        fields[name]=alignments.get(fields[name],fields[name])
    return fields
