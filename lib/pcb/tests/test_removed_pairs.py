"""Restorable pair geometry is editable data, separate from active routing."""
from copy import deepcopy
import unittest
from xml.etree import ElementTree

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.references import ReferenceError
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.asc.write import project as project_asc
from lib.pcb.formats.dip.write import encode
from lib.pcb.formats.capabilities import DIP
from lib.pcb.formats.dipxml.read import prepare
from lib.pcb.formats.dipxml.syntax import dumps as xml_text
from lib.pcb.formats.dipxml.write import project_document
from lib.pcb.model import routing_records
from lib.pcb.model.objects import new_removed_pair
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dip_output import configured_document, reopen
from lib.pcb.tests.test_dipxml_pairs import source as pair_source
from lib.pcb.tests.test_xml_routing_output import with_component_library


PATH = '/Board/RemovedDifferentialPairs/RemovedDifferentialPair'


def source(*, enabled=False):
    root = ElementTree.fromstring(with_component_library(pair_source()))
    board = root.find('Board')
    pair = deepcopy(board.find('DifferentialPairs/DifferentialPair'))
    pair.tag = 'RemovedDifferentialPair'
    pair.set('Enabled', 'Y' if enabled else 'N')
    pair.find('Name').text = 'Restorable pair'
    for name in ('AutoPadPoints', 'RouteMode'):
        pair.attrib.pop(name)
    for side in ('Pos', 'Neg'):
        pair.remove(pair.find(side+'SeparateTraces'))
    ElementTree.SubElement(board, 'RemovedDifferentialPairs').append(pair)
    return ElementTree.tostring(root, encoding='unicode')


@import_diagnostics('dipxml')
def read_xml(text):
    return assemble_graphics(prepare(text)).document


@import_diagnostics('asc')
def read_asc(text):
    return assemble_graphics(prepare_core(text)).document


class RemovedPairTests(unittest.TestCase):
    def test_removed_pair_flags_and_references_are_current_typed_data(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                document = read_xml(source(enabled=enabled), report=ConversionReport())
                pair = document.one(PATH)
                self.assertIs(pair.schema, routing_records.REMOVED_PAIR)
                self.assertEqual(pair['Enabled'], enabled)
                self.assertEqual(pair['Name'], 'Restorable pair')
                self.assertIs(pair['PosNet'], document.one('/Board/Nets/Net[1]'))
                self.assertIs(pair.one('Segments/Segment')['PosTrace'], document.one('/Board/Nets/Net[1]/Traces/Trace[1]'))
                self.assertIs(pair.one('Segments/Segment')['Start'], pair.one('PadPoints/PadPoint'))
                center = pair.one('Segments/Segment/CenterPoints/CenterPoint')
                self.assertIs(center['PosStartPoint'], document.one('/Board/Nets/Net[1]/Traces/Trace[1]/Points/Point[1]'))
                self.assertNotIn('AutoPadPoints', pair.schema.fields)
                document.references.validate()

    def test_text_formats_reopen_the_same_restorable_geometry(self):
        document = read_xml(source(), report=ConversionReport())
        expected, before = signature(document.one(PATH)), dumps(document, preserve=False)
        xml = read_xml(xml_text(project_document(document, report=ConversionReport())), report=ConversionReport())
        ascii = read_asc(dumps(project_asc(document, report=ConversionReport()), preserve=False), report=ConversionReport())
        for current in (xml, ascii):
            self.assertEqual(signature(current.one(PATH)), expected)
            current.references.validate()
        self.assertEqual(dumps(document, preserve=False), before)

    def test_binary_restorable_sections_follow_each_supported_output_version(self):
        document = configured_document(source())
        pair = document.one(PATH)
        expected, before = signature(pair), dumps(document, preserve=False)
        for version in DIP.write_versions:
            with self.subTest(version=version):
                data = encode(document, version=version, report=ConversionReport())
                current = reopen(data, report=ConversionReport())
                self.assertEqual(signature(current.one(PATH)), expected)
                self.assertEqual(encode(current, version=version, report=ConversionReport()), data)
                current.references.validate()
        self.assertEqual(dumps(document, preserve=False), before)

    def test_restorable_geometry_does_not_become_live_point_membership(self):
        document = read_xml(source(), report=ConversionReport())
        center = document.one(PATH+'/Segments/Segment/CenterPoints/CenterPoint')
        point = document.one('/Board/Nets/Net[1]/Traces/Trace[1]/Points/Point[1]')
        before = point['PairTarget']
        with self.assertRaises(ReferenceError):
            point['PairTarget'] = center
        self.assertIs(point['PairTarget'], before)

    def test_copy_and_reorder_keep_restore_targets_and_internal_endpoints_coherent(self):
        document = read_xml(source(), report=ConversionReport())
        original = document.one(PATH)
        copied = document.copy(original, index=0)
        copied['Name'], copied['Enabled'] = 'Another restorable pair', True
        self.assertIs(copied.one('Segments/Segment')['Start'], copied.one('PadPoints/PadPoint'))
        self.assertIsNot(copied.one('Segments/Segment')['Start'], original.one('PadPoints/PadPoint'))
        trace = original.one('Segments/Segment')['PosTrace']
        point = trace.one('Points/Point[1]')
        point.move_to(point.parent)
        positive = original['PosNet']
        positive.move_to(positive.parent)
        for pair in (original, copied):
            self.assertIs(pair['PosNet'], positive)
            self.assertEqual(pair['PosNetIndex'], positive._ordinal())
            self.assertIs(pair.one('Segments/Segment/CenterPoints/CenterPoint')['PosStartPoint'], point)
            self.assertEqual(pair.one('Segments/Segment/CenterPoints/CenterPoint')['PosTrace_StartPoint'], point._ordinal())
        document.references.validate()
        current = read_xml(xml_text(project_document(document, report=ConversionReport())), report=ConversionReport())
        self.assertEqual(signature(current.one('/Board/RemovedDifferentialPairs')),
                         signature(document.one('/Board/RemovedDifferentialPairs')))

    def test_constructor_adds_independent_restorable_data_without_routing(self):
        document = configured_document(source())
        original = document.one(PATH)
        created = new_removed_pair('Empty restoration data')
        original.parent.append(created)
        created['PosNet'], created['NegNet'], created['Class'] = original['PosNet'], original['NegNet'], original['Class']
        created['Enabled'] = False
        current = reopen(encode(document, report=ConversionReport()), report=ConversionReport())
        saved = current.one('/Board/RemovedDifferentialPairs/RemovedDifferentialPair[2]')
        self.assertEqual(saved['Name'], 'Empty restoration data')
        self.assertFalse(saved['Enabled'])
        self.assertEqual(saved.select('Segments/Segment'), [])
        self.assertEqual(saved.select('PadPoints/PadPoint'), [])
        self.assertIs(saved['PosNet'], current.one('/Board/Nets/Net[1]'))
        current.references.validate()

    def test_removed_pair_shields_follow_the_binary_gate_and_remain_in_xml(self):
        document = configured_document(source())
        center = document.one(PATH+'/Segments/Segment/CenterPoints/CenterPoint')
        center['PosShieldGroup'], center['NegShieldGroup'] = 7, 8
        center.one('PosPoints/PosPoint')['ShieldGroup'] = 9
        before = dumps(document, preserve=False)
        for version in (54, 57, 62):
            report = ConversionReport()
            data = encode(document, version=version, report=report)
            current = reopen(data, report=ConversionReport())
            saved = current.one(center.path)
            self.assertEqual(saved.get('PosShieldGroup', -1), 7 if version >= 57 else -1)
            self.assertEqual(saved.get('NegShieldGroup', -1), 8 if version >= 57 else -1)
            self.assertEqual(saved.one('PosPoints/PosPoint').get('ShieldGroup', -1), 9 if version >= 57 else -1)
            self.assertEqual('shield-groups' in [n.rule for n in report.warnings], version < 57)
            self.assertEqual(encode(current, version=version, report=ConversionReport()), data)
        xml = read_xml(xml_text(project_document(document, report=ConversionReport())), report=ConversionReport())
        self.assertEqual(signature(xml.one(PATH)), signature(document.one(PATH)))
        self.assertEqual(dumps(document, preserve=False), before)

    def test_inactive_live_pair_is_discarded_but_removed_pair_flag_is_retained(self):
        text = source()
        root = ElementTree.fromstring(text)
        live = root.find('Board/DifferentialPairs')
        deleted = deepcopy(live.find('DifferentialPair'))
        deleted.set('Enabled', 'N')
        deleted.set('PosNet', '9999')
        deleted.set('NegNet', '9999')
        live.append(deleted)
        report = ConversionReport()
        current = read_xml(ElementTree.tostring(root, encoding='unicode'), report=report)
        baseline = read_xml(text, report=ConversionReport())
        self.assertEqual(signature(current.root), signature(baseline.root))
        self.assertFalse(current.one(PATH)['Enabled'])
        self.assertIn('inactive-differential-pairs', [notice.rule for notice in report.infos])

    def test_unresolved_restorable_range_can_be_inspected_and_repaired(self):
        root = ElementTree.fromstring(source())
        center = root.find('Board/RemovedDifferentialPairs/RemovedDifferentialPair/Segments/Segment/CenterPoints/CenterPoint')
        center.set('PosTrace_EndPoint', '999')
        report = ConversionReport()
        document = read_xml(ElementTree.tostring(root, encoding='unicode'), report=report)
        current = document.one(PATH+'/Segments/Segment/CenterPoints/CenterPoint')
        self.assertEqual(current['PosTrace_EndPoint'], 999)
        self.assertIn('unresolved-pair-range', [notice.rule for notice in report.warnings])
        with self.assertRaises(ReferenceError):
            current['PosEndPoint']
        current['PosEndPoint'] = document.one('/Board/Nets/Net[1]/Traces/Trace[1]/Points/Point[1]')
        self.assertIsNone(current.child('UnresolvedPosEndPointIndex'))
        document.references.validate()


if __name__ == '__main__':
    unittest.main()
