"""Assemble the public XML view of a complete editable schematic."""

from ..export_view import (prepare_export)
from .syntax import (set_attribute)
from .buses import (project_buses, project_bus_connectors, project_groups)
from .components import (project_component)
from .graphics import (project_drawings)
from .library import (project_library)
from .nets import (project_nets, project_net_classes, project_differential_pairs)
from .project import (project_libraries, project_simulator)
from .settings import (project_sheet_settings, project_settings, project_erc)
from .tables import (project_tables)
from ....common.units import XmlUnits
from ...model.document import (Document)
from ....common.model import (IncompleteDocumentError)
from ....common.conversion import (export_diagnostics)
from ..export_context import DchXmlExportContext, resolve_export_context
from ..capabilities import DCHXML


@export_diagnostics('dchxml')
def project_document(document, *, context=None, version=DCHXML.default_write_version, report=None):
    """Create detached XML data; preserve full precision rather than RTL spelling.

    Output styles share only complete equal public records. This is a public
    format conversion, not a reconstruction of every binary-only fact.
    """
    if not document.complete or document.representation != 'schematic':
        raise IncompleteDocumentError('complete shared schematic data is required for XML conversion')
    version = DCHXML.output_version(version)
    context = resolve_export_context(context, 'dchxml')
    override = context.marking_style
    context = context.resolved(document)
    from ..dch.versions import (xml_application_version)
    application_version = xml_application_version(version)
    if document.metadata.get('source_version', version) > version:
        from ....common.conversion import (info)
        info(report, 'schema-version', 'dchxml', f'output uses schema {version}; newer fields follow their individual conversion rules')
    if version < 47:
        from ....common.conversion import (warn)
        from ..compatibility import (nondefault_net_ids)
        hidden = nondefault_net_ids(document.one('/Schematic'))
        if hidden:
            warn(report, 'net-hidden-id', 'dchxml', 'nondefault Net.HiddenId is omitted by output schema below 47', hidden)
    from ...model.schema import (validate_public_content)
    validate_public_content(document, allow_xml_fields=True)
    view = prepare_export(document, marking_style=override, text_layout=context.text_layout,
                          additional_user_fields=context.additional_user_fields,
                          retain_inactive=('Nets', 'Buses', 'PageConnectors', 'Groups'), materialize_markings=False,
                          refresh_user_fields=context.refresh_user_fields, destination='dchxml', report=report)
    schematic = view.one('/Schematic')
    from ..revision_adaptation import (prepare_revisions)
    prepare_revisions(schematic, destination='dchxml', version=version, report=report)
    from ..compatibility import (report_text_omissions, report_generated_marking_attributes)
    report_text_omissions(view, destination='dchxml', report=report)
    report_generated_marking_attributes(schematic,
        use_part_font_color=context.use_part_font_color in (True, 'Y'),
        font_name=context.marking_style.font_name, report=report)
    from ..pictures import (prepare_pictures)
    prepare_pictures(schematic,destination='dchxml',filenames=context.legacy_picture_files,report=report)
    if context.path_variables is not None:
        from ..path_variables import (prepare_variable_paths)
        prepare_variable_paths(schematic, context.path_variables,
            project_dir=context.project_dir if context.project_dir is not None else schematic.scalar('ProjectDir', ''))
    units = XmlUnits(context.units)
    library = project_library(schematic, units=units, version=version, report=report)
    output = Document(representation='dchxml')
    source = output.root.add('Source')
    for name, value in (('Type', 'DipTrace-Schematic'), ('Version', application_version),
                         ('Units', context.units)):
        set_attribute(source, name, value)
    source.append(library.element)
    target = source.add('Schematic')
    target.append(project_sheet_settings(schematic, units=units, active_sheet=context.active_sheet, version=version))
    target.append(project_settings(schematic, units=units, grid_snap=context.grid_snap, style=context.marking_style,
                  use_part_font_color=context.use_part_font_color, project_dir=context.project_dir, version=version))
    target.append(project_libraries(schematic))
    set_attribute(target.add('DesignCache'), 'Count', library.cache_count)
    target.append(project_net_classes(schematic, units=units))
    target.append(project_erc(schematic))
    components = target.add('Components')
    for part, (style, variant) in library.component_styles.items():
        components.append(project_component(part, units=units, component_style=style, component_part=variant, version=version))
    for collection in (project_nets(schematic, units=units, hidden_ids=version >= 47),
                       project_differential_pairs(schematic, include_ids=version >= 47),
                       project_buses(schematic, units=units), project_bus_connectors(schematic, units=units),
                       project_drawings(schematic, units=units, version=version), project_tables(schematic, units=units, version=version)):
        if collection.children():
            target.append(collection)
    simulator = project_simulator(schematic, version=version)
    if simulator is not None:
        target.append(simulator)
    groups = project_groups(schematic)
    if groups.children():
        target.append(groups)
    output.metadata.update(source_format='dchxml', projected_from='schematic', target_schema=version,
                           export_equivalent=False, style_sharing='complete public records',
                           numeric_precision='full model precision')
    from .refs import (bind_references)
    bind_references(output)
    return output
