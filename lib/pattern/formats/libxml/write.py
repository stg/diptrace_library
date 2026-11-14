"""Standalone pattern-library XML from the current owned authoring model."""
import secrets

from ....common.conversion import export_diagnostics, warn
from ....common.library_link_projection import check_issues
from ....common.library_catalogue import ROLES as CATALOGUE_ROLES
from ....common.units import XmlUnits
from ....common.xml import dumps_plan, set_attribute
from ....common.xml_catalog import CategoryCatalog, StylePlans
from ....common.xml_library_physical import project_pattern
from ....common.xml_plan import XmlBuilder, XmlPlan
from ..export_view import prepare_export
from .syntax import DIALECT
from .versions import XmlVersion


def _pattern(pattern, *, styles, units, profile, report, text_layout):
    if any(pattern['Verification']):
        warn(report, 'pattern-verification', 'libxml',
             'XML omits saved pattern verification states', (pattern,))
    return project_pattern(pattern, styles=styles, units=units, profile=profile,
                           destination='libxml', report=report, text_layout=text_layout)


@export_diagnostics('libxml')
def project_document(document, *, version=None, units='mm', report=None, text_layout=None):
    profile = XmlVersion.output(version)
    document = prepare_export(document, destination='libxml', report=report)
    check_issues(document, roles=CATALOGUE_ROLES)
    scale = XmlUnits(units)
    library = document.one('/Library')
    target = XmlBuilder('Library')
    for name, value in (('Type', 'DipTrace-PatternLibrary'), ('Version', profile.text),
                        ('Name', library['Name']), ('Hint', library['Hint']), ('Units', scale.units)):
        set_attribute(target, name, value)
    if profile.current_fields:
        set_attribute(target, 'UID32', secrets.randbits(32))
    styles = StylePlans('PadStyles', 'PadStyle', 'Name', 'Pad')
    patterns = tuple(_pattern(pattern, styles=styles, units=scale, profile=profile, report=report, text_layout=text_layout)
                     for pattern in library.select('Patterns/Pattern'))
    catalog = CategoryCatalog(key='Number')
    catalog.seed(library.child('Categories'))
    target.append(XmlPlan.from_element(catalog.element))
    target.append(styles.plan)
    target.append(XmlPlan('Patterns', children=patterns))
    return target.freeze()


@export_diagnostics('libxml')
def dumps(document, *, version=None, units='mm', report=None, text_layout=None):
    plan = project_document(document, version=version, units=units, report=report, text_layout=text_layout)
    return dumps_plan(plan, dialect=DIALECT)
