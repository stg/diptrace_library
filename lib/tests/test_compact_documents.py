"""The compact field facade preserves real schematic and PCB model behavior."""
import unittest

from lib import ConversionReport, parse, serialize
from lib.common.element_storage import RecordItems
from lib.schematic.tests.test_named_fields import design as schematic
from lib.pcb.tests.test_dip_output import configured_document as pcb


class CompactDocumentTests(unittest.TestCase):
    def test_normal_imports_use_slots_but_explicit_text_views_keep_syntax(self):
        from lib import parse_source
        for factory, binary, xml in ((schematic, 'dch', 'dchxml'), (pcb, 'dip', 'dipxml')):
            source = factory()
            for format in (binary, 'asc', xml):
                encoded = serialize(source, format=format, report=ConversionReport())
                model = parse(encoded, report=ConversionReport())
                self.assertTrue(any(type(node._content) is RecordItems
                                    for node in model.root._record_walk(include_self=True)))
                if format != binary:
                    inspected = parse_source(encoded, report=ConversionReport())
                    self.assertFalse(any(type(node._content) is RecordItems
                                         for node in inspected.root._record_walk(include_self=True)))

    def test_all_format_directions_keep_identical_outputs_and_diagnostics(self):
        for factory, formats in ((schematic, ('dch', 'asc', 'dchxml')),
                                 (pcb, ('dip', 'asc', 'dipxml'))):
            source = factory()
            for input_format in formats:
                encoded = serialize(source, format=input_format, report=ConversionReport())
                document = parse(encoded, report=ConversionReport())
                expected = {}
                for output_format in formats:
                    report = ConversionReport()
                    expected[output_format] = (serialize(document, format=output_format, report=report),
                        [(n.severity, n.rule, n.message, n.paths) for n in report.notices])
                document.root._compact_fields(recursive=True, retain_debug=True)
                self.assertTrue(any(isinstance(node._items, RecordItems) for node in document.root.walk(include_self=True)))
                document.validate()
                for output_format in formats:
                    with self.subTest(input=input_format, output=output_format):
                        report = ConversionReport()
                        actual = serialize(document, format=output_format, report=report)
                        self.assertEqual(actual, expected[output_format][0])
                        self.assertEqual([(n.severity, n.rule, n.message, n.paths) for n in report.notices],
                                         expected[output_format][1])

    def test_schematic_queries_edits_and_copies_keep_coordinated_references(self):
        document = schematic()
        part = document.one('/Schematic/Components/Part')
        field = part.one('RefDes')
        document.root._compact_fields(recursive=True)
        part['RefDes'], part['Value'] = 'R8', '22k'
        self.assertEqual(field.values, ('R8',))
        self.assertIs(document.one('/Schematic/Components/Part', where=lambda p: p['Value'] == '22k'), part)
        copied = document.copy(part, fields={'RefDes': 'R9'})
        self.assertEqual(copied['RefDes'], 'R9')
        self.assertTrue(document.references.outgoing(copied, role='component-page'))
        document.clone().validate()
        document.validate()

    def test_pcb_queries_edits_and_clone_keep_pad_and_net_relationships(self):
        document = pcb()
        part = document.one('/Board/Components/Component')
        value = part.one('Value')
        document.root._compact_fields(recursive=True)
        part['Value'] = 'Edited'
        self.assertEqual(value.values, ('Edited',))
        cloned = document.clone()
        cloned.one('/Board/Components/Component')['Value'] = 'Copy'
        self.assertEqual(part['Value'], 'Edited')
        self.assertEqual(cloned.one('/Board/Components/Component')['Value'], 'Copy')
        self.assertEqual(len(cloned.references), len(document.references))
        cloned.validate()
        document.validate()


if __name__ == '__main__':
    unittest.main()
