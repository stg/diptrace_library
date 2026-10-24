"""Receiver compatibility notices must not rewrite authored punctuation."""
import unittest

from lib import ExportReport, new_schematic, parse
from lib.schematic.model.objects import (new_symbol, new_schematic_shape)
from lib.schematic.model.refs import (bind_schematic_references)


class AscReceiverTextTests(unittest.TestCase):
    def test_literal_punctuation_survives_library_cycles_and_reports_receiver_loss(self):
        source = new_schematic()
        part = source.one('/Schematic/Components').append(new_symbol('Part!Name', 'U!1'))
        for name, value in (('Value', 'A!B'), ('Manufacturer', 'M!N'),
                            ('Datasheet', 'D!S'), ('PartName', 'P!Q'), ('ModelString', 'X!Y')):
            part.set_field(name, value)
        part.one('ModelBody').add('Line', 'L!R')
        part.one('UserFields').add('UserField', 'F!G', 'V!W', 0, 0, 7, 0, 0, 0, 0, 0)
        shape = source.one('/Schematic/Shapes').append(new_schematic_shape(0))
        shape.set_field('Type', 10)
        shape.one('Points_New').add('pt', 0, 5)
        shape.one('TextLine').add('pt', 'S!T!!U')
        bind_schematic_references(source)
        for format in ('dch', 'asc', 'dchxml'):
            current = source
            for cycle in range(3):
                with self.subTest(format=format, cycle=cycle):
                    report = ExportReport()
                    current = parse(getattr(current, 'to_'+format+'_bytes')(report=report), format=format)
                    notices = [n for n in report.warnings if n.rule == 'asc-reader-text-normalization']
                    self.assertEqual(len(notices), int(format == 'asc'))
                    if notices:
                        self.assertEqual(len(notices[0].paths), 8)
                    loaded = current.one('/Schematic/Components/Part')
                    self.assertEqual(loaded.values, ('Part!Name', 'U!1'))
                    self.assertEqual(loaded.scalar('Value'), 'A!B')
                    self.assertEqual(loaded.scalar('Datasheet'), 'D!S')
                    self.assertEqual(loaded.one('ModelBody/Line').values, ('L!R',))
                    self.assertEqual(loaded.one('UserFields/UserField').values[:2], ('F!G', 'V!W'))
                    self.assertEqual(current.one('/Schematic/Shapes/Shape/TextLine/pt').values, ('S!T!!U',))
        self.assertEqual(part.scalar('Value'), 'A!B')

    def test_unaffected_field_does_not_receive_a_blanket_receiver_warning(self):
        source = new_schematic()
        part = source.one('/Schematic/Components').append(new_symbol('Part', 'U1'))
        part.set_field('Datasheet', 'D!S')
        bind_schematic_references(source)
        report = ExportReport()
        output = parse(source.to_asc_bytes(report=report), format='asc')
        self.assertEqual(output.one('/Schematic/Components/Part').scalar('Datasheet'), 'D!S')
        self.assertNotIn('asc-reader-text-normalization', {n.rule for n in report.notices})

    def test_sanitizer_substitution_does_not_duplicate_a_literal_punctuation_notice(self):
        source = new_schematic()
        part = source.one('/Schematic/Components').append(new_symbol('Part', 'U1'))
        part.set_field('Value', '"quoted"')
        bind_schematic_references(source)
        report = ExportReport()
        output = parse(source.to_asc_bytes(report=report), format='asc')
        self.assertEqual(output.one('/Schematic/Components/Part').scalar('Value'), '!quoted!')
        self.assertIn('asc-text-sanitization', {n.rule for n in report.warnings})
        self.assertNotIn('asc-reader-text-normalization', {n.rule for n in report.notices})


if __name__ == '__main__':
    unittest.main()
