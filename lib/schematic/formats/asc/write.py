"""Prepare a detached ASC view without changing the editable source document.

Export overrides are optional. Modern label choices and current drawings are
authoritative; destination bookkeeping is generated from them.
"""

from ...model.document import (Document)
from ....common.model import (Element, Value, IncompleteDocumentError)
from ..export_context import AscExportContext, resolve_export_context
from ....common.conversion import (export_diagnostics)


from ..export_view import prepare_export


from ...model.vocabulary import (SCHEMATIC_FIELDS)


@export_diagnostics('asc')
def project_document(document, *, context=None, report=None):
    """Build a complete ASC document from current DCH data and explicit context."""
    from .projection import (ProjectionError, _value, _plain, _visible, project_page, project_component, project_net, project_settings, project_schematic_drawing)
    from .cache_projection import (project_cache)
    from .document_projection import (legacy_global_fields, project_page_connector, project_bus, project_group, project_table, project_library_paths)
    from ....common.numbers import (calculation_number)
    if not document.complete:
        raise IncompleteDocumentError('complete shared schematic data is required for ASC conversion')
    context = resolve_export_context(context, 'asc')
    override = context.marking_style
    units_override = context.units
    context = context.resolved(document)
    if document.representation != 'schematic':
        raise ProjectionError('shared schematic data is required; normalize source views with as_schematic()')
    from ...model.schema import (validate_public_content)
    validate_public_content(document, allow_xml_fields=True)
    view=prepare_export(document,marking_style=override,text_layout=context.text_layout,
                        additional_user_fields=context.additional_user_fields,
                        refresh_user_fields=context.refresh_user_fields,
                        compact_inactive=context.compact_inactive, report=report,
                        default_main_supplier=context.default_main_supplier)
    from ..compatibility import (apply_capacity)
    apply_capacity(view, destination='asc', report=report)
    view.rebuild(force=False)
    source=view.one('/Schematic')
    from ..revision_adaptation import (prepare_revisions)
    prepare_revisions(source, destination='asc', report=report)
    from ..pictures import (prepare_pictures)
    prepare_pictures(source,destination='asc',filenames=context.legacy_picture_files,report=report)
    if context.path_variables is not None:
        from ..path_variables import (prepare_variable_paths)
        prepare_variable_paths(source, context.path_variables,
            project_dir=context.project_dir if context.project_dir is not None else source.scalar('ProjectDir', ''))
    unknown=[n.kind for n in _visible(view.root) if n.kind not in ('Source','Scale','Xpos','Ypos','Schematic')]
    if unknown:
        raise ProjectionError(f'no document projection for {unknown}')
    unknown=[n.kind for n in _visible(source) if n.kind not in SCHEMATIC_FIELDS]
    if unknown:
        raise ProjectionError(f'no schematic projection for {unknown}')
    output=Document(representation='asc')
    output.root.add('Source','DipTrace-Schematic',46)
    output.root.add('Units',context.units)
    value=_value(view.one('/Scale').arguments[0])
    output.root.add('Scale',Value(value.value,value.kind,'%',source=value.source))
    for name in ('Xpos','Ypos'):
        output.root.add(name,round(calculation_number(view.one('/'+name))))
    schematic=output.root.add('Schematic')
    legacy = legacy_global_fields(
        source, initial=context.legacy_text_slots or (0, 0, 0, 0, '', ''))
    def collection(node,kind,project):
        result=Element(node.kind,*map(_value,node.arguments))
        for item in _visible(node):
            if item.kind!=kind:
                raise ProjectionError(f'{node.path}: expected {kind}, found {item.kind}')
            result.append(project(item))
        return result
    layout=context.text_layout
    projectors={
        'Pages':lambda n:collection(n,'Page',project_page),
        'Components':lambda n:collection(n,'Part',lambda p:project_component(p,
            line_width=context.line_width,symbol_text_bounds=layout.symbol_bounds,
            generated_font_name=context.marking_style.font_name if override is not None else context.marking_style.font_name or None)),
        'PageConnectors':lambda n:collection(n,'PageConnector',project_page_connector),
        'Shapes':lambda n:collection(n,'Shape',lambda p:project_schematic_drawing(p,text_bounds=layout.symbol_bounds)),
        'Nets':lambda n:collection(n,'Net',project_net),
        'Buses':lambda n:collection(n,'Bus',project_bus),
        'Groups':lambda n:collection(n,'Group',project_group),
        'Tables':lambda n:collection(n,'Table',project_table),
        'CacheLib':lambda n:project_cache(n,line_width=context.line_width,symbol_text_bounds=layout.symbol_bounds),
        'ProjectLibs_Folders':lambda n:project_library_paths(n,'Folder'),
        'ProjectLibs_Libs':lambda n:project_library_paths(n,'Lib'),
    }
    for name in SCHEMATIC_FIELDS:
        if name=='PictureCount':
            # ASC writes a literal zero; modern pictures are file-backed.
            schematic.add(name,0)
            continue
        if name in legacy:
            schematic.add(name,_value(Value.of(legacy[name])))
            continue
        if name=='ProjectDir' and context.project_dir is not None:
            schematic.add(name,_value(Value.of(context.project_dir)))
            continue
        fields=source.children(name)
        if len(fields)!=1:
            raise ProjectionError(f'{source.path}: expected one {name}, found {len(fields)}')
        node=fields[0]
        if name=='Settings':
            use_color=context.use_part_font_color
            if use_color is None:
                use_color=node.scalar('UsePartFontColor')
            if use_color is None:
                raise ProjectionError('old files require an explicit use_part_font_color choice')
            projected=project_settings(node,grid_snap=context.grid_snap,units=units_override,
                part_font_size=context.marking_style.font_size,part_font_color=context.marking_style.font_color,
                use_part_font_color=use_color)
        else:
            projected=projectors.get(name,_plain)(node)
        if name=='ssimulator':
            for item in projected.children():
                if item.kind in ('signals','sim_ac','sim_dc','sim_tran','sim_noise'):
                    item.set_values(len(item.children()))
        schematic.append(projected)
    # Text-file restrictions follow geometry. This also reports irreversible
    # substitutions using only fields actually present in the destination.
    from .policy import (project_text)
    project_text(output, encoding=context.encoding, report=report)
    output.metadata.update(source_format='asc',projected_from='schematic',
        source_version=46,asc_layout='schematic-46',
        export_equivalence_verified=False)
    output._source_encoding=context.encoding
    from ...model.refs import (bind_schematic_references)
    bind_schematic_references(output)
    return output
