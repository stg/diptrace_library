"""Edited inactive data adapts on an output view without changing authored facts."""
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.common.schema import MISSING
from lib.common.references import ReferenceError
from lib.common.structural_edits import assembly
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import DIP, DIPXML
from lib.pcb.formats.export_view import prepare_export
from lib.pcb.model.objects import (new_component, new_document, new_net, new_net_class,
                                   new_pair, new_removed_pair)
from lib.pcb.tests import test_programmatic_workflow as workflow


def inactive_board():
    document = new_document()
    board = document.one('/Board')
    component = new_component('Unused', 'X1')
    component['Enabled'] = False
    board.one('Components').append(component)
    net = new_net('Unused net')
    net['Enabled'] = False
    board.one('Nets').append(net)
    pair = new_pair('Unused pair')
    pair['Enabled'] = False
    board.add('DifferentialPairs').append(pair)
    for collection, kind in (('Shapes', 'Shape'), ('CopperPours', 'CopperPour'),
                             ('Dimensions', 'Dimension'), ('Tables', 'Table'),
                             ('DesignErrors', 'DesignError')):
        node = board.add(collection).add(kind)
        for name, field in node.schema.fields.items():
            if field.required and field.getter is None:
                value = field.default
                if value is MISSING:
                    value = {'boolean': False, 'integer': 0, 'number': 0, 'text': ''}[field.kind]
                    if name.startswith('Connected'):
                        value = -1
                node[name] = value
        node['Enabled'] = False
    return document


class InactiveExportTests(unittest.TestCase):
    def test_unchecked_class_results_do_not_prevent_export_or_erase_class_settings(self):
        document = new_document()
        board = document.one('/Board')
        net_class = board.one('NetClasses').append(new_net_class('Limited'))
        board['DefaultClass'] = net_class
        net_class['CheckLength'], net_class['AllLayers'] = True, True
        net_class['FixedLength'], net_class['LengthDelta'] = 30, 3
        net_class.add('LayProperties').add('LayProperty')
        net = board.one('Nets').append(new_net('Measured'))
        net['Class'] = net_class
        results = net_class.add('LengthResults')
        connection = results.add('Rules').add('Rule')
        connection['Net'], connection['Length'], connection['Error'] = net, 12, True
        net_class['CheckLength'] = False
        document.validate()
        before = dumps(document, preserve=False)
        profiles = [('dip', version) for version in DIP.write_versions] + [('asc', None)]
        profiles += [('dipxml', version) for version in DIPXML.write_versions]
        for format, version in profiles:
            with self.subTest(format=format, version=version):
                report = ConversionReport()
                current = io.parse(io.serialize(document, format=format, version=version,
                                   report=report), report=ConversionReport())
                rebuilt = current.one('/Board/NetClasses/NetClass')
                self.assertEqual((rebuilt['CheckLength'], rebuilt['FixedLength'], rebuilt['LengthDelta']),
                                 (False, 30, 3))
                self.assertIsNone(rebuilt.child('LengthResults'))
                notice, = [n for n in report.infos if n.rule == 'obsolete-class-length-results']
                self.assertEqual(notice.paths, (results.path,))
                self.assertEqual(report.errors, [])
                self.assertEqual(dumps(document, preserve=False), before)
        self.assertTrue(results['AnyError'])
        net_class['CheckLength'] = True
        current = io.parse(io.serialize(document, format='dipxml', report=ConversionReport()),
                           report=ConversionReport())
        self.assertEqual(current.one('/Board/NetClasses/NetClass/LengthResults/Rules/Rule')['Length'], 12)

    def test_all_xml_profiles_omit_disabled_board_records_without_changing_source(self):
        document = inactive_board()
        before = dumps(document, preserve=False)
        document.validate()
        for version in (54, 58, 60, 62):
            with self.subTest(version=version):
                report = ConversionReport()
                current = io.parse(io.serialize(document, format='dipxml', version=version,
                                                report=report), report=ConversionReport())
                for collection, kind in (('Components', 'Component'), ('Nets', 'Net'),
                        ('DifferentialPairs', 'DifferentialPair'), ('Shapes', 'Shape'),
                        ('CopperPours', 'CopperPour'), ('Dimensions', 'Dimension'),
                        ('Tables', 'Table'), ('DesignErrors', 'DesignError')):
                    self.assertEqual(current.select('/Board/' + collection + '/' + kind), [])
                notice, = [n for n in report.warnings if n.rule == 'inactive-records']
                self.assertEqual(len(notice.paths), 7)
                empty, = [n for n in report.infos if n.rule == 'inactive-empty-drawings']
                self.assertEqual(len(empty.paths), 1)
                self.assertTrue(all(path.startswith('/Board[1]/') for path in notice.paths))
                self.assertEqual(report.errors, [])
                current.validate()
                repeated = io.parse(io.serialize(current, format='dipxml', version=version,
                    report=ConversionReport()), report=ConversionReport())
                self.assertEqual(dumps(current, preserve=False), dumps(repeated, preserve=False))
                self.assertEqual(dumps(document, preserve=False), before)

    def test_omitting_an_earlier_component_keeps_live_routing_bound_to_the_same_pad(self):
        document = workflow.build()
        component = new_component('Unused', 'X9')
        component['Enabled'] = False
        document.one('/Board/Components').insert(component, index=0)
        trace = document.one('/Board/Nets/Net/Traces/Trace')
        pad = trace['Target2']
        self.assertEqual(trace['Object2'], 2)
        self.assertIs(trace['Target2'], pad)
        before = dumps(document, preserve=False)
        for version in (54, 58, 60, 62):
            current = io.parse(io.serialize(document, format='dipxml', version=version,
                              report=ConversionReport()), report=ConversionReport())
            workflow.ProgrammaticWorkflowTests.assert_connected(self, current)
            self.assertEqual(current.one('/Board/Nets/Net/Traces/Trace')['Object2'], 1)
        self.assertIs(trace['Target2'], pad)
        self.assertEqual(dumps(document, preserve=False), before)

    def test_removed_pair_restoration_state_keeps_its_independent_enabled_flag(self):
        document = new_document()
        board = document.one('/Board')
        positive, negative = [board.one('Nets').append(new_net(name)) for name in ('P', 'N')]
        pair = board.add('RemovedDifferentialPairs').append(new_removed_pair('Restoration'))
        pair['PosNet'], pair['NegNet'], pair['Enabled'] = positive, negative, False
        before = dumps(document, preserve=False)
        for version in (54, 58, 60, 62):
            report = ConversionReport()
            current = io.parse(io.serialize(document, format='dipxml', version=version,
                              report=report), report=ConversionReport())
            saved = current.one('/Board/RemovedDifferentialPairs/RemovedDifferentialPair')
            self.assertFalse(saved['Enabled'])
            self.assertEqual(saved['PosNet']['Name'], 'P')
            self.assertEqual(saved['NegNet']['Name'], 'N')
            self.assertNotIn('inactive-records', [n.rule for n in report.notices])
        self.assertEqual(dumps(document, preserve=False), before)

    def test_invalid_live_reference_into_a_disabled_component_is_not_silently_discarded(self):
        document = workflow.build()
        # Simulate malformed supplied data; ordinary named edits reject this
        # connected-component state before it can be introduced.
        with assembly(document):
            document.one('/Board/Components/Component[2]')['Enabled'] = False
        before, report = dumps(document, preserve=False), ConversionReport()
        with self.assertRaises(ReferenceError):
            io.serialize(document, format='dipxml', report=report)
        self.assertTrue(report.errors)
        self.assertEqual(dumps(document, preserve=False), before)

    def test_formats_with_an_enabled_field_keep_their_existing_view_policy(self):
        document = inactive_board()
        before = dumps(document, preserve=False)
        for destination in ('dip', 'asc'):
            view, _ = prepare_export(document, destination=destination, report=ConversionReport())
            self.assertFalse(view.one('/Board/Components/Component')['Enabled'])
            self.assertFalse(view.one('/Board/Shapes/Shape')['Enabled'])
        self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
