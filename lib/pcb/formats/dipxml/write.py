"""Assemble current PCB XML data with explicit whole-document coverage checks."""
from ....common.conversion import export_diagnostics
from ....common.units import XmlUnits
from ....common.xml import set_attribute
from ...model.document import Document
from ...model.library_records import DESIGN_LINKS
from ..errors import PcbError
from ..output_validation import check_tree
from .class_output import project_classes
from .component_output import project_components
from .coverage import validate_document
from .dimension_output import project_dimensions
from .graphic_output import project_outline, project_non_signals, project_drawings
from .length_output import project_length_rules
from .library_output import project_library
from .net_output import project_nets
from .output_keys import OutputKeys
from .pair_output import project_pairs
from .pour_output import project_pours
from .project_options import project_paths, report_document_options
from .ratline_output import project_ratlines
from .resource_output import (project_layers, project_vias, project_groups,
                              project_hierarchy_sheets, project_assembly_variants)
from .result_output import project_results
from .rule_output import project_design_rules
from .settings_output import project_settings, project_sheet, project_panel, project_connectivity
from .table_output import project_tables
from .versions import XmlVersion
from .output_revision import adapt_document
from .pad_defaults import report_legacy_inference


def _append(target, section):
    if not section.children() and not section.arguments and section.kind not in ('CopperLayers', 'Components', 'Nets'):
        return
    if target.child(section.kind) is not None:
        raise PcbError(f'{target.path}: duplicate XML projection for {section.kind}')
    target.append(section)


@export_diagnostics('dipxml')
def project_document(document, *, version=None, units=None, legacy_picture_files=None, report=None):
    """Build the selected XML dialect from current editable data."""
    profile = XmlVersion.output(version)
    board = validate_document(document)
    document.references.validate()
    if not profile.current_fields:
        report_legacy_inference(board, report=report)
    report_document_options(board, report=report)
    if (links := board.child('DesignCache_Links')) is not None:
        check_tree(links, DESIGN_LINKS, destination='DIPXML')
    scale = XmlUnits(document.root['Units'] if units is None else units)
    library = project_library(board, units=scale, physical=board.select('Components/Component/Pattern'),
                              profile=profile, report=report)
    keys = OutputKeys(board, library)
    result = Document(representation='dipxml')
    source = result.root.add('Source')
    for name, value in (('Type', 'DipTrace-PCB'), ('Version', profile.application_text), ('Units', scale.units)):
        set_attribute(source, name, value)
    source.append(library.element)
    target = source.add('Board')
    sections = (
        project_outline(board, units=scale), project_layers(board, units=scale), project_non_signals(board),
        project_groups(board, report=report), project_vias(board, units=scale, report=report),
        project_hierarchy_sheets(board), project_assembly_variants(board),
        project_components(board, library=library, units=scale, report=report),
        project_classes(board, keys=keys, units=scale, report=report),
        project_nets(board, keys=keys, units=scale, display_metrics=profile.routing_metrics_in_display_units, report=report),
        project_pairs(board, keys=keys, units=scale, display_metrics=profile.routing_metrics_in_display_units, report=report),
        project_pairs(board, keys=keys, units=scale, report=report, removed=True),
        project_pours(board, units=scale, report=report),
        project_drawings(board, units=scale, legacy_picture_files=legacy_picture_files,
                         physical_font_width=profile.physical_font_width, report=report),
        project_dimensions(board, keys=keys, units=scale, physical_font_width=profile.physical_font_width, report=report),
        project_settings(board, units=scale, report=report), project_sheet(board, units=scale),
        project_panel(board, units=scale, display_metrics=profile.panel_metrics_in_display_units,
                      side_gaps=profile.application != (4, 3, 0, 5), report=report),
        project_connectivity(board), project_paths(board, report=report),
        project_ratlines(board, keys=keys, units=scale, report=report),
        project_tables(board, units=scale, physical_font_width=profile.physical_font_width,
                       legacy_cell_spacing=profile.legacy_cell_line_spacing, report=report),
        project_results(board, keys=keys, units=scale, report=report),
    )
    for section in sections:
        _append(target, section)
    for fragment in (project_length_rules(board, keys=keys, units=scale),
                     project_design_rules(board, keys=keys, units=scale, report=report)):
        for section in tuple(fragment.children()):
            section.detach()
            _append(target, section)
    adapt_document(result, version=profile, report=report)
    return result
