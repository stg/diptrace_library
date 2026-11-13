"""Assemble current PCB XML data with explicit whole-document coverage checks."""
from ....common.conversion import export_diagnostics
from ....common.units import XmlUnits
from ....common.xml import set_attribute, dumps_plan
from ....common.xml_plan import XmlBuilder, XmlPlan
from ...model.document import Document
from ...model.library_records import DESIGN_LINKS
from ..errors import PcbError
from ..output_validation import check_tree
from .class_output import project_classes
from .component_output import _project_with_checked_patterns
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
    plan = section.freeze() if isinstance(section, XmlBuilder) else XmlPlan.from_element(section)
    if not plan.children and not plan.arguments and not plan.attributes and plan.kind not in ('CopperLayers', 'Components', 'Nets'):
        return
    if any(child.kind == plan.kind for child in target.children):
        raise PcbError(f'{target.kind}: duplicate XML projection for {plan.kind}')
    target.append(plan)


@export_diagnostics('dipxml')
def _project(document, *, version=None, units=None, legacy_picture_files=None, report=None):
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
    source = XmlBuilder('Source')
    for name, value in (('Type', 'DipTrace-PCB'), ('Version', profile.application_text), ('Units', scale.units)):
        set_attribute(source, name, value)
    source.append(library.plan)
    target = source.add('Board')
    for section in _sections(board, scale=scale, library=library, keys=keys, profile=profile,
                             legacy_picture_files=legacy_picture_files, report=report):
        _append(target, section)
    for fragment in (project_length_rules(board, keys=keys, units=scale),
                     project_design_rules(board, keys=keys, units=scale, report=report)):
        for section in tuple(fragment.children()):
            section.detach()
            _append(target, section)
    return adapt_document(source.freeze(), version=profile, report=report)


def _sections(board, *, scale, library, keys, profile, legacy_picture_files, report):
    """Generate one section at a time, retaining only compact projected facts."""
    yield project_outline(board, units=scale)
    yield project_layers(board, units=scale)
    yield project_non_signals(board)
    yield project_groups(board, report=report)
    yield project_vias(board, units=scale, report=report)
    yield project_hierarchy_sheets(board)
    yield project_assembly_variants(board)
    yield _project_with_checked_patterns(board, library=library, units=scale, report=report, _factory=XmlBuilder)
    yield project_classes(board, keys=keys, units=scale, report=report)
    yield project_nets(board, keys=keys, units=scale, display_metrics=profile.routing_metrics_in_display_units, report=report)
    yield project_pairs(board, keys=keys, units=scale, display_metrics=profile.routing_metrics_in_display_units, report=report)
    yield project_pairs(board, keys=keys, units=scale, report=report, removed=True)
    yield project_pours(board, units=scale, report=report)
    yield project_drawings(board, units=scale, legacy_picture_files=legacy_picture_files,
                         physical_font_width=profile.physical_font_width, report=report)
    yield project_dimensions(board, keys=keys, units=scale, physical_font_width=profile.physical_font_width, report=report)
    yield project_settings(board, units=scale, report=report)
    yield project_sheet(board, units=scale)
    yield project_panel(board, units=scale, display_metrics=profile.panel_metrics_in_display_units,
                      side_gaps=profile.application != (4, 3, 0, 5), report=report)
    yield project_connectivity(board)
    yield project_paths(board, report=report)
    yield project_ratlines(board, keys=keys, units=scale, report=report)
    yield project_tables(board, units=scale, physical_font_width=profile.physical_font_width,
                       legacy_cell_spacing=profile.legacy_cell_line_spacing, report=report)
    yield project_results(board, keys=keys, units=scale, report=report)


@export_diagnostics('dipxml')
def project_document(document, *, version=None, units=None, legacy_picture_files=None, report=None):
    """Materialize editable XML from the same facts used for direct output."""
    plan = _project(document, version=version, units=units, legacy_picture_files=legacy_picture_files, report=report)
    result = Document(representation='dipxml')
    result.root.append(plan.element())
    return result


@export_diagnostics('dipxml')
def serialize_document(document, *, version=None, units=None, legacy_picture_files=None, report=None):
    """Emit UTF-8 without constructing a complete editable XML tree."""
    from .syntax import DIALECT
    plan = _project(document, version=version, units=units, legacy_picture_files=legacy_picture_files, report=report)
    return dumps_plan(plan, dialect=DIALECT, canonical_numbers=True).encode('utf-8')
