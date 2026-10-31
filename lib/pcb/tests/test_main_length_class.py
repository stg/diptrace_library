"""The main working rule retains a class selection and independent working data."""
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.asc import dumps, loads_bytes
from lib.common.conversion import ConversionReport
from lib.common.references import Property, ReferenceError
from lib.pcb.formats import io
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.formats.capabilities import DIP, DIPXML
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.writer import Writer
from lib.pcb.formats.dip.write_electrical import write_length_rules
from lib.pcb.model.objects import new_document, new_net, new_net_class
from lib.pcb.tests.test_dipxml_electrical import prepared
from lib.pcb.tests.test_length_rule_inputs import asc_source, xml_source


def design():
    document = new_document()
    board = document.one('/Board')
    classes = board.one('NetClasses')
    net_class = classes.append(new_net_class('Routed'))
    board['DefaultClass'] = net_class
    selected = classes.append(new_net_class('Selected source'))
    for current in (net_class, selected):
        current['AllLayers'] = True
        current.add('LayProperties').add('LayProperty')
    selected['FixedLength'], selected['LengthDelta'] = 50, 3
    net = board.one('Nets').append(new_net('Signal'))
    net['Class'] = net_class
    main = board.add('MainLengthRule')
    main['Name'], main['FixedLength'], main['Delta'] = 'Working copy', 17, Decimal('.2')
    main['Class'] = selected
    row = main.add('Rules').add('Rule')
    row['Net'], row['Length'], row['Error'] = net, 18, True
    document.validate()
    return document


class MainLengthClassTests(unittest.TestCase):
    def test_ascii_and_xml_import_keep_main_data_separate_from_generated_class_results(self):
        ascii = asc_source().replace('(MainLengthRule "Y" -1 7.62 "N" "Y" -1 0',
                                     '(MainLengthRule "Working copy" 17 0.2 "N" "Y" 1 1')
        xml = xml_source().replace('<MainLengthRule Type="By User">',
            '<MainLengthRule Type="By NetClass" NetClass="70" FixedLength="17" Delta=".2">')
        for source, expected in ((prepare_core(ascii), (17, Decimal('.2'))),
                                 (prepared(xml), (51, Decimal('.6')))):
            result = assemble_rules(source)
            main = result.document.one('/Board/MainLengthRule')
            selected = result.classes[1]
            self.assertIs(main['Class'], selected)
            self.assertEqual((main['FixedLength'], main['Delta']), expected)
            self.assertNotEqual(main['FixedLength'], selected['FixedLength'])
            self.assertIsNotNone(selected.child('LengthResults'))
            self.assertIsNone(main.child('Type'))
            self.assertIsNone(main.child('NetClass'))
            result.document.references.validate()

    def test_class_reordering_and_retargeting_update_only_the_selection(self):
        document = design()
        main = document.one('/Board/MainLengthRule')
        selected = main['Class']
        probe = document.root.add('Probe', 0)
        document.references.bind(probe, main, Property(probe, 'NetClass'), role='probe')
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole tree scan')), \
                patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            selected.move_to(selected.parent, 0)
            self.assertEqual((main['NetClass'], probe.values[0]), (0, 0))
            selected['Name'], selected['FixedLength'] = 'Renamed class', 99
            self.assertEqual((main['Name'], main['FixedLength']), ('Working copy', 17))
            main['Class'] = document.one('/Board/NetClasses/NetClass[2]')
            self.assertEqual(probe.values[0], 1)
        document.validate()

    def test_selection_scope_and_referenced_removal_are_atomic(self):
        document = design()
        main = document.one('/Board/MainLengthRule')
        selected = main['Class']
        user = document.one('/Board').add('LengthRules').add('LengthRule')
        before = dumps(document, preserve=False)
        with self.assertRaises(ReferenceError):
            user['Class'] = selected
        other = design().one('/Board/NetClasses/NetClass[1]')
        with self.assertRaises(ReferenceError):
            main['Class'] = other
        with self.assertRaises(ReferenceError):
            document.remove(selected)
        self.assertEqual(dumps(document, preserve=False), before)
        main['Class'] = None
        document.remove(selected)
        self.assertEqual(main['NetClass'], -1)
        document.validate()

    def test_document_clone_remaps_the_class_and_keeps_working_connections(self):
        document = design()
        duplicate = document.clone()
        main = duplicate.one('/Board/MainLengthRule')
        self.assertIs(main['Class'], duplicate.one('/Board/NetClasses/NetClass[2]'))
        self.assertIsNot(main['Class'], document.one('/Board/MainLengthRule')['Class'])
        self.assertIs(main.one('Rules/Rule')['Net'], duplicate.one('/Board/Nets/Net'))
        duplicate.validate()

    def test_wire_class_index_and_rule_kind_are_independent_values(self):
        document = design()
        board = document.one('/Board')
        board.one('MainLengthRule')['Class'] = board.one('NetClasses/NetClass[1]')
        for version in DIP.write_versions:
            writer = Writer(version)
            writer.header()
            write_length_rules(writer, board)
            reader = Reader(bytes(writer.buffer))
            self.assertEqual(reader.text(), 'Working copy')
            self.assertEqual((reader.number(), reader.number()), (17, Decimal('.2')))
            self.assertEqual((reader.boolean(), reader.boolean()), (True, True))
            self.assertEqual((reader.integer(), reader.integer()), (0, 1))
        raw = loads_bytes(io.serialize(document, format='asc', report=ConversionReport()))
        self.assertEqual(raw.one('/Board/MainLengthRule').values[-2:], (0, 1))

    def test_every_output_profile_retains_selection_without_replacing_working_values(self):
        document = design()
        before = dumps(document, preserve=False)
        profiles = [('asc', None), *(('dip', version) for version in DIP.write_versions),
                    *(('dipxml', version) for version in DIPXML.write_versions)]
        for format, version in profiles:
            with self.subTest(format=format, version=version):
                data = io.serialize(document, format=format, version=version, report=ConversionReport())
                if format == 'asc':
                    self.assertEqual(loads_bytes(data).one('/Board/MainLengthRule').values[-2:], (1, 1))
                rebuilt = io.parse(data, report=ConversionReport())
                main = rebuilt.one('/Board/MainLengthRule')
                self.assertIs(main['Class'], rebuilt.one('/Board/NetClasses/NetClass[2]'))
                self.assertEqual((main['Name'], main['FixedLength'], main['Delta']),
                                 ('Working copy', 17, Decimal('.2')))
                self.assertTrue(main['AnyError'])
                self.assertIsNot(main.one('Rules/Rule')['Net']['Class'], main['Class'])
                self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
