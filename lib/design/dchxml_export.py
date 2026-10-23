"""Assemble the public XML view of a complete editable schematic."""
from dataclasses import dataclass, field, replace

from .asc_export import prepare_export
from .dchxml import set_attribute
from .dchxml_buses import project_buses, project_bus_connectors, project_groups
from .dchxml_components import project_component
from .dchxml_graphics import project_drawings
from .dchxml_library import project_library
from .dchxml_nets import project_nets, project_net_classes, project_differential_pairs
from .dchxml_project import project_libraries, project_simulator
from .dchxml_settings import project_sheet_settings, project_settings, project_erc
from .dchxml_tables import project_tables
from .dchxml_units import DchXmlUnits
from .markings import MarkingStyle, resolve_marking_style
from .model import Document, IncompleteDocumentError
from .path_variables import PathVariables
from .text_layout import TextLayout, default_layout
from .export_defaults import display_units
from .conversion import export_diagnostics


@dataclass(frozen=True)
class DchXmlExportContext:
    """Optional output choices over stored settings and standard defaults."""
    units: str | None = None
    marking_style: MarkingStyle | None = None
    grid_snap: bool | None = None
    active_sheet: int = 0
    project_dir: str | None = None
    text_layout: TextLayout = field(default_factory=default_layout)
    use_part_font_color: bool | None = None
    additional_user_fields: tuple = ()
    legacy_picture_files: tuple | None = None
    path_variables: PathVariables | None = None
    refresh_user_fields: bool = False

    def __post_init__(self):
        if self.units is not None:
            DchXmlUnits('inch' if self.units == 'in' else self.units)
        if self.grid_snap is not None and not isinstance(self.grid_snap, bool):
            raise TypeError('grid_snap must be a boolean')
        if not isinstance(self.refresh_user_fields, bool):
            raise TypeError('refresh_user_fields must be a boolean')
        if self.marking_style is not None and not isinstance(self.marking_style, MarkingStyle):
            raise TypeError('marking_style must be a MarkingStyle')
        if self.path_variables is not None and not isinstance(self.path_variables, PathVariables):
            raise TypeError('path_variables must be a PathVariables configuration')

    def resolved(self, document):
        schematic = document.one('/Schematic')
        settings = schematic.one('Settings')
        units = self.units or display_units(document)
        style = resolve_marking_style(document, self.marking_style)
        return replace(self, units='inch' if units == 'in' else units,
            project_dir=self.project_dir if self.project_dir is not None else schematic.scalar('ProjectDir', ''),
            marking_style=style,
            grid_snap=self.grid_snap if self.grid_snap is not None else settings.scalar('GridSnap', True),
            use_part_font_color=self.use_part_font_color if self.use_part_font_color is not None else settings.scalar('UsePartFontColor', False))


@export_diagnostics('dchxml')
def project_document(document, *, context=None, version=46, report=None):
    """Create detached XML data; preserve full precision rather than RTL spelling.

    Output styles share only complete equal public records. This is a public
    format conversion, not a reconstruction of every binary-only fact.
    """
    if not document.complete or document.representation != 'schematic':
        raise IncompleteDocumentError('complete shared schematic data is required for XML conversion')
    if context is None:
        context = DchXmlExportContext()
    if not isinstance(context, DchXmlExportContext):
        raise TypeError('XML conversion requires a DchXmlExportContext')
    override = context.marking_style
    context = context.resolved(document)
    if version not in (46, 47, 48):
        raise ValueError('XML output supports target schemas 46, 47 and 48')
    if document.metadata.get('source_version', version) > version:
        from .conversion import info
        info(report, 'schema-version', 'dchxml', f'output uses schema {version}; newer fields follow their individual conversion rules')
    if version < 47:
        from .conversion import warn, nondefault_net_ids
        hidden = nondefault_net_ids(document.one('/Schematic'))
        if hidden:
            warn(report, 'net-hidden-id', 'dchxml', 'nondefault Net.HiddenId is omitted by output schema below 47', hidden)
    from .schematic_schema import validate_public_content
    validate_public_content(document, allow_xml_fields=True)
    view = prepare_export(document, marking_style=override, text_layout=context.text_layout,
                          additional_user_fields=context.additional_user_fields,
                          retain_inactive=('Nets', 'Buses', 'PageConnectors', 'Groups'), materialize_markings=False,
                          refresh_user_fields=context.refresh_user_fields, destination='dchxml', report=report)
    schematic = view.one('/Schematic')
    from .conversion import report_text_omissions, report_generated_marking_attributes
    report_text_omissions(view, destination='dchxml', report=report)
    report_generated_marking_attributes(schematic,
        use_part_font_color=context.use_part_font_color in (True, 'Y'),
        font_name=context.marking_style.font_name, report=report)
    from .pictures import prepare_pictures
    prepare_pictures(schematic,destination='dchxml',filenames=context.legacy_picture_files,report=report)
    if context.path_variables is not None:
        from .path_variables import prepare_variable_paths
        prepare_variable_paths(schematic, context.path_variables,
            project_dir=context.project_dir if context.project_dir is not None else schematic.scalar('ProjectDir', ''))
    units = DchXmlUnits(context.units)
    library = project_library(schematic, units=units, version=version, report=report)
    output = Document(representation='dchxml')
    source = output.root.add('Source')
    for name, value in (('Type', 'DipTrace-Schematic'), ('Version', '4.3.0.5' if version == 46 else '4.9.5.0'),
                         ('Units', context.units)):
        set_attribute(source, name, value)
    source.append(library.element)
    target = source.add('Schematic')
    target.append(project_sheet_settings(schematic, units=units, active_sheet=context.active_sheet))
    target.append(project_settings(schematic, units=units, grid_snap=context.grid_snap, style=context.marking_style,
                  use_part_font_color=context.use_part_font_color, project_dir=context.project_dir))
    target.append(project_libraries(schematic))
    set_attribute(target.add('DesignCache'), 'Count', library.cache_count)
    target.append(project_net_classes(schematic, units=units))
    target.append(project_erc(schematic))
    components = target.add('Components')
    for part, (style, variant) in library.component_styles.items():
        components.append(project_component(part, units=units, component_style=style, component_part=variant))
    for collection in (project_nets(schematic, units=units, hidden_ids=version >= 47),
                       project_differential_pairs(schematic, include_ids=version >= 47),
                       project_buses(schematic, units=units), project_bus_connectors(schematic, units=units),
                       project_drawings(schematic, units=units), project_tables(schematic, units=units)):
        if collection.children():
            target.append(collection)
    simulator = project_simulator(schematic)
    if simulator is not None:
        target.append(simulator)
    groups = project_groups(schematic)
    if groups.children():
        target.append(groups)
    output.metadata.update(source_format='dchxml', projected_from='schematic', target_schema=version,
                           export_equivalent=False, style_sharing='complete public records',
                           numeric_precision='full model precision')
    from .dchxml_refs import bind_references
    bind_references(output)
    return output
