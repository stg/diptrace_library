"""Generated XML routing sections preserve current geometry and linked rules."""
from decimal import Decimal
import unittest
from xml.etree import ElementTree

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.units import XmlUnits
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import FORMATS, XML_APPLICATION_VERSIONS
from lib.pcb.formats.dipxml.class_output import project_classes
from lib.pcb.formats.dipxml.length_output import project_length_rules
from lib.pcb.formats.dipxml.net_output import project_nets
from lib.pcb.formats.dipxml.output_keys import OutputKeys
from lib.pcb.formats.dipxml.pair_output import project_pairs
from lib.pcb.formats.dipxml.syntax import dumps
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dipxml_library import read, source
from lib.pcb.tests.test_length_rule_inputs import xml_source
from lib.pcb.tests.test_xml_component_output import context as component_context


def with_component_library(text):
    root = ElementTree.fromstring(text)
    patterns = root.find('Library')
    root.remove(patterns)
    library = ElementTree.Element('Library', Type='DipTrace-ComponentLibrary',
                                  Version='5.3.5.1', Units='mm')
    library.append(patterns)
    ElementTree.SubElement(library, 'Components')
    root.insert(0, library)
    return ElementTree.tostring(root, encoding='unicode')


def context(document, *, units='mm', report=None):
    report = ConversionReport() if report is None else report
    output, library = component_context(document, units=units, report=report)
    board, target = document.one('/Board'), output.one('/Source/Board')
    scale, keys = XmlUnits(units), OutputKeys(board, library)
    target.one('Nets').detach()
    target.append(project_nets(board, keys=keys, units=scale, report=report))
    target.append(project_classes(board, keys=keys, units=scale, report=report))
    target.append(project_pairs(board, keys=keys, units=scale, report=report))
    for section in tuple(project_length_rules(board, keys=keys, units=scale).children()):
        section.move_to(target)
    return output, library


def reopen(document, *, units='mm', report=None):
    output, _ = context(document, units=units, report=report)
    return read(dumps(output), report=ConversionReport()), output


class XmlRoutingOutputTests(unittest.TestCase):
    def test_missing_point_via_styles_do_not_inherit_adjacent_selections(self):
        root = ElementTree.fromstring(source())
        board = root.find('Board')
        styles = ElementTree.SubElement(board, 'ViaStyles')
        style = ElementTree.SubElement(styles, 'ViaStyle',
                                       Id='62', Size='0.6', HoleSize='0.3')
        ElementTree.SubElement(style, 'Name').text = 'Through'
        points = board.find('Nets/Net/Traces/Trace/Points')
        points.clear()
        # Omission before and after explicit choices must remain a local absence.
        selections = (None, '62', None, '-1', '62', None)
        for index, selection in enumerate(selections):
            point = ElementTree.SubElement(points, 'Point',
                Id=str(index), X=str(index), Y='0', Lay='0', Width='0.3')
            if selection is not None:
                point.set('ViaStyle', selection)
        path = '/Board/Nets/Net/Traces/Trace[1]/Points/Point'
        expected = [-1, 0, -1, -1, 0, -1]

        def check(document):
            actual = document.select(path)
            self.assertEqual([point['ViaStyle'] for point in actual], expected)
            via = document.one('/Board/ViaStyles/ViaStyle')
            for point, selection in zip(actual, expected):
                self.assertIs(point['Via'], via if selection == 0 else None)
            document.references.validate()

        for application in XML_APPLICATION_VERSIONS.values():
            with self.subTest(input=application):
                root.set('Version', application)
                document = io.parse(ElementTree.tostring(root), report=ConversionReport())
                check(document)
        before = model_text(document, preserve=False)
        for capability in FORMATS.values():
            for version in capability.write_versions:
                with self.subTest(format=capability.format, version=version):
                    current = document
                    for _ in range(2):
                        data = io.serialize(current, format=capability.format, version=version,
                                            report=ConversionReport())
                        current = io.parse(data, report=ConversionReport())
                        check(current)
        self.assertEqual(model_text(document, preserve=False), before)

    def test_absent_newer_fields_use_model_defaults_without_becoming_source_fields(self):
        document = read(source(), report=ConversionReport())
        component = document.one('/Board/Components/Component')
        pad = component.one('Pattern/Pads/Pad[1]')
        net = document.one('/Board/Nets/Net')
        for record, names in ((component, ('ShieldGroup',)), (pad, ('ShieldGroup', 'SignalDelay')),
                              (net, ('HiddenId', 'AllowLoops'))):
            for name in names:
                del record[name]
        before = model_text(document, preserve=False)
        rebuilt, _ = reopen(document)
        self.assertEqual(rebuilt.one('/Board/Components/Component')['ShieldGroup'], -1)
        self.assertEqual(rebuilt.one('/Board/Components/Component/Pattern/Pads/Pad[1]')['SignalDelay'], 0)
        self.assertEqual(rebuilt.one('/Board/Nets/Net')['HiddenId'], -1)
        self.assertFalse(rebuilt.one('/Board/Nets/Net')['AllowLoops'])
        self.assertEqual(model_text(document, preserve=False), before)

    def assert_facts(self, actual, expected):
        self.assertEqual(actual.keys(), expected.keys())
        for name, value in expected.items():
            if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
                self.assertLessEqual(abs(actual[name]-value), Decimal('1e-23'), name)
            else:
                self.assertEqual(actual[name], value, name)

    def test_routes_teardrops_and_phase_values_survive_units_and_repeated_output(self):
        document = read(source(), report=ConversionReport())
        first, second = document.select('/Board/Nets/Net/Traces/Trace[1]/Points/Point')
        first['PhaseFwd'], first['PhaseBack'] = None, 0
        second['PhaseFwd'], second['PhaseBack'] = Decimal('-1.25'), Decimal('3.5')
        second['MeanderAngle'] = Decimal('21.5')
        first['Width'] = -1
        expected = signature(document.one('/Board/Nets'))
        unchanged = model_text(document, preserve=False)
        for units in ('mm', 'mil', 'inch'):
            current = document
            for _ in range(3):
                current, output = reopen(current, units=units)
                self.assert_facts(signature(current.one('/Board/Nets')), expected)
                self.assertIsNone(output.one('/Source/Board/Nets/Net/Traces/Trace[1]/Points/Point[1]').child('Width'))
                current.references.validate()
        self.assertEqual(model_text(document, preserve=False), unchanged)

    def test_reordering_uses_targets_rather_than_stale_numeric_selectors(self):
        document = read(source(), report=ConversionReport())
        pad = document.one('/Board/Components/Component/Pattern/Pads/Pad[1]')
        pad.move_to(pad.parent, 1)
        first, second = document.select('/Board/Nets/Net/Traces/Trace')
        selected = first.one('Points/Point[2]')
        selected.move_to(selected.parent, 0)
        second.move_to(second.parent, 0)
        drop = document.one('/Board/Nets/Net/Teardrops/Teardrop')
        document.copy(drop, parent=drop.parent)
        drop.move_to(drop.parent, 1)
        expected = signature(document.one('/Board/Nets'))
        rebuilt, _ = reopen(document)
        self.assert_facts(signature(rebuilt.one('/Board/Nets')), expected)
        routes = rebuilt.select('/Board/Nets/Net/Traces/Trace')
        self.assertIs(routes[0]['Target1'], routes[1].one('Points/Point[1]'))
        self.assertIs(routes[1]['Target1'], rebuilt.one('/Board/Components/Component/Pattern/Pads/Pad[2]'))
        rebuilt.references.validate()

    def test_class_rules_permissions_and_length_results_use_current_identities(self):
        document = read(with_component_library(xml_source()), report=ConversionReport())
        sections = ('Nets', 'NetClasses', 'MainLengthRule', 'LengthRules')
        expected = {name: signature(document.one('/Board/'+name)) for name in sections}
        for units in ('mm', 'mil', 'inch'):
            rebuilt, _ = reopen(document, units=units)
            for name in sections:
                self.assert_facts(signature(rebuilt.one('/Board/'+name)), expected[name])
            special = rebuilt.one('/Board/NetClasses/NetClass[2]')
            self.assertIs(rebuilt.one('/Board/Nets/Net')['Class'], special)
            rule = special.one('LengthResults/Rules/Rule')
            self.assertIs(rule['Pad1'], rebuilt.one('/Board/Components/Component/Pattern/Pads/Pad[1]'))
            self.assertEqual(special['MaxIncorrectWayValue'], Decimal('12.5'))
            rebuilt.references.validate()

    def test_unknown_route_content_is_rejected_without_mutating_the_model(self):
        document = read(source(), report=ConversionReport())
        document.one('/Board/Nets/Net/Traces/Trace[1]').add('UnmappedRouteData', 7)
        before = model_text(document, preserve=False)
        with self.assertRaisesRegex(PcbError, 'no PCB DIPXML projection'):
            reopen(document)
        self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
