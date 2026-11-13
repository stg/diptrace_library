"""Source detail is optional without changing authored facts or conversions."""
from dataclasses import replace
import unittest

from lib import ConversionReport, parse, parse_source, serialize
from lib.common.model import Element, SourceSpan, Value
from lib.common.schema import Field, Record
from lib.common.source_details import discard_source
from lib.schematic.formats.import_context import ImportContext as SchematicContext
from lib.pcb.formats.import_context import ImportContext as PcbContext
from lib.schematic.tests.test_named_fields import design as schematic
from lib.pcb.tests.test_dip_output import configured_document as pcb


class SourceDetailTests(unittest.TestCase):
    def test_all_inputs_have_equivalent_outputs_and_reports_in_both_modes(self):
        for factory, context, formats in ((schematic, SchematicContext(), ('dch', 'asc', 'dchxml')),
                                          (pcb, PcbContext(), ('dip', 'asc', 'dipxml'))):
            source = factory()
            self.assertFalse(context.retain_source)
            for incoming in formats:
                encoded = serialize(source, format=incoming, report=ConversionReport())
                reports = [ConversionReport(), ConversionReport()]
                lean = parse(encoded, context=context, report=reports[0])
                detailed = parse(encoded, context=replace(context, retain_source=True), report=reports[1])
                self.assertEqual([(n.rule, n.severity, n.paths) for n in reports[0].notices],
                                 [(n.rule, n.severity, n.paths) for n in reports[1].notices])
                for node in lean.root.walk(include_self=True):
                    self.assertIsNone(node.source)
                    self.assertIsNone(node._syntax)
                    self.assertTrue(all(v.source is None and v.lexeme is None for v in node.arguments))
                    notes = node._annotations or {}
                    self.assertFalse(any(isinstance(value, SourceSpan) for value in notes.values()))
                    self.assertTrue({'declared_pad_count', 'declared_shape_count', 'default_for_version',
                        'default_value', 'generated_default', 'derived_from', 'group_default_for_version',
                        'label_defaults_for_version', 'requires_asc_projection', 'xml_only'}.isdisjoint(notes))
                for outgoing in formats:
                    with self.subTest(incoming=incoming, outgoing=outgoing):
                        self.assertEqual(serialize(lean, format=outgoing, report=ConversionReport()),
                                         serialize(detailed, format=outgoing, report=ConversionReport()))

    def test_explicit_source_inspection_still_retains_details(self):
        for factory, formats in ((schematic, ('dch', 'asc', 'dchxml')),
                                 (pcb, ('dip', 'asc', 'dipxml'))):
            source = factory()
            for format in formats:
                with self.subTest(format=format):
                    inspected = parse_source(serialize(source, format=format, report=ConversionReport()),
                                             report=ConversionReport())
                    nodes = tuple(inspected.root.walk(include_self=True))
                    self.assertTrue(any(node.source is not None or node._syntax is not None or
                        node._annotations and 'xml_line' in node._annotations for node in nodes))

    def test_compact_cleanup_keeps_units_symbol_kinds_notes_and_live_handles(self):
        schema = Record('Row', {'Scale': Field('Scale', 'number'), 'Name': Field('Name', 'text')})
        span = SourceSpan('example', 1, 5)
        node = Element('Row', source=span).bind_schema(schema)
        scale = node.add('Scale', Value(25, 'number', '%', '25%', span))
        symbol = node.add('Name', Value('Token', 'symbol', lexeme='Token', source=span))
        symbol.annotations['note'] = 'authored note'
        node._compact_fields(retain_debug=True)
        identity = scale.uid
        discard_source(node)
        self.assertIs(node.one('Scale'), scale)
        self.assertEqual(scale.uid, identity)
        self.assertEqual((scale.arguments[0].value, scale.arguments[0].unit), (25, '%'))
        self.assertEqual(symbol.arguments[0].kind, 'symbol')
        self.assertEqual(symbol.annotations, {'note': 'authored note'})
        self.assertIsNone(symbol.arguments[0].lexeme)
        self.assertIsNone(node.source)

    def test_context_flag_requires_a_boolean(self):
        for context in (SchematicContext, PcbContext):
            with self.assertRaises(TypeError):
                context(retain_source=1)
