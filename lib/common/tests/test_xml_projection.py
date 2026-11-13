"""Generated XML retains key, positional and unresolved-reference checks."""
import unittest
from unittest.mock import patch

from lib.common.model import Document
from lib.common.references import ReferenceError, Segment
from lib.common.xml_plan import XmlBuilder, XmlPlan
from lib.common.xml_projection import XmlProjection
from lib.schematic.formats.dchxml.refs import (
    _specifications, bind_references, validate_references,
)


def source_plan():
    source = XmlBuilder('Source')
    source.attribute('Type', 'DipTrace-Schematic')
    definitions = source.add('Library').add('Components')
    style = definitions.add('Component')
    style.attribute('ComponentStyle', 'Device')
    style.add('Part').add('Pins').add('Pin')
    schematic = source.add('Schematic')
    settings = schematic.add('SheetSettings')
    settings.add('ActiveSheet', 0)
    settings.add('Sheets').add('Sheet').attribute('Id', 0)
    part = schematic.add('Components').add('Part')
    for name, value in (('Id', 0), ('ComponentStyle', 'Device'), ('ComponentPart', 0), ('Sheet', 0)):
        part.attribute(name, value)
    part.add('Pins').add('Pin').attribute('NetId', 0)
    net = schematic.add('Nets').add('Net')
    net.attribute('Id', 0)
    wires = net.add('Wires')
    route = wires.add('Wire')
    route.attribute('Id', 0)
    points = route.add('Points')
    for x in (0, 1, 2):
        point = points.add('Point')
        point.attribute('X', x)
        point.attribute('Y', 0)
    join = wires.add('Wire')
    for name, value in (('Id', 1), ('Connected1', 'Wire'), ('Object1', 0), ('SubObject1', 1), ('Bus1', -1)):
        join.attribute(name, value)
    return source


def reference_facts(graph):
    def target_path(target):
        return ((target.start.path, target.end.path) if isinstance(target, Segment) else target.path)
    return [(r.source.path, r.role, target_path(r.target),
             tuple((item.field.path, item.argument) for item in r.indices)) for r in graph]


class XmlProjectionTests(unittest.TestCase):
    def test_temporary_audit_handles_are_released_without_touching_projection_facts(self):
        plan = source_plan().freeze()
        before = plan.key()
        with XmlProjection(plan) as projection:
            projection.audit(_specifications, validate_references)
            self.assertTrue(projection.root._handles)
        self.assertIsNone(projection.references)
        self.assertIsNone(projection.root._handles)
        self.assertEqual(plan.key(), before)
        with projection:
            self.assertEqual(projection.audit(_specifications, validate_references), [])

    def test_incorrect_generated_projection_is_an_error_not_an_unresolved_target(self):
        from lib.common.references import Key
        builder = source_plan()
        builder.children[1].children[2].children[0].attribute('Id', 7)
        def specifications(document):
            part = document.one('/Source/Schematic/Components/Part')
            net = document.one('/Source/Schematic/Nets/Net')
            yield part, net, 'test-key', (Key(part.child('Id')),), ()
        with XmlProjection(builder.freeze()) as projection, self.assertRaisesRegex(ReferenceError, 'disagrees'):
            projection.audit(specifications, lambda document: None)

    def test_normal_text_output_does_not_materialize_the_whole_projection(self):
        from lib import ConversionReport, new_schematic
        document = new_schematic()
        with patch.object(XmlPlan, 'element', side_effect=AssertionError('editable materialization')):
            output = document.to_dchxml(report=ConversionReport())
        self.assertIn('Type="DipTrace-Schematic"', output)

    def test_borrowed_audit_matches_editable_keys_indices_and_segment_targets(self):
        plan = source_plan().freeze()
        document = Document()
        document.root.append(plan.element())
        bind_references(document)
        document.validate()
        with patch.object(XmlPlan, 'element', side_effect=AssertionError('editable materialization')):
            projection = XmlProjection(plan)
            self.assertEqual(projection.audit(_specifications, validate_references), [])
        self.assertEqual(reference_facts(projection.references), reference_facts(document.references))
        part = projection.one('/Source/Schematic/Components/Part')
        self.assertIs(part.child('Id'), part.children('Id')[0])
        self.assertIs(part.child('Id').parent, part)

    def test_unresolved_targets_remain_explicit_and_do_not_disable_other_checks(self):
        builder = source_plan()
        builder.children[1].children[1].children[0].attribute('ComponentStyle', 'Missing')
        plan = builder.freeze()
        document = Document()
        document.root.append(plan.element())
        bind_references(document)
        document.validate()
        projection = XmlProjection(plan)
        issues = projection.audit(_specifications, validate_references)
        self.assertEqual([(source.path, message) for source, message in issues],
                         [(issue.source.path, issue.message) for issue in document.references.issues])
        self.assertEqual(reference_facts(projection.references), reference_facts(document.references))

    def test_duplicate_and_wrongly_typed_keys_are_rejected_without_materialization(self):
        for value in (0, 'not a numeric key'):
            source = source_plan()
            parts = source.children[1].children[1]
            parts.add('Part').attribute('Id', value)
            projection = XmlProjection(source.freeze())
            with self.subTest(value=value), self.assertRaises(ReferenceError):
                projection.audit(_specifications, validate_references)

    def test_schematic_bytes_and_inspection_share_profile_units_reports_and_source_safety(self):
        from lib import ConversionReport, DchXmlExportContext
        from lib.schematic.formats.dchxml.syntax import dumps
        from lib.tests.test_hierarchy import HierarchyTests
        from lib.tests.test_library_font_widths import design
        for document in (HierarchyTests().design()[0], design()):
            original = document.to_dch_bytes(report=ConversionReport())
            for version in (46, 47, 48, 52):
                for units in ('mm', 'mil', 'inch'):
                    with self.subTest(version=version, units=units):
                        context = DchXmlExportContext(units=units)
                        inspected, emitted = ConversionReport(), ConversionReport()
                        view = document.as_dchxml(version=version, context=context, report=inspected)
                        expected = dumps(view, canonical_numbers=True)
                        actual = document.to_dchxml(version=version, context=context, report=emitted)
                        self.assertEqual(actual, expected)
                        self.assertEqual(emitted.notices, inspected.notices)
            self.assertEqual(document.to_dch_bytes(report=ConversionReport()), original)


if __name__ == '__main__':
    unittest.main()
