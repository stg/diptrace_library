"""Build, search, edit and convert a small connected PCB without a donor file."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.pcb.model.markings import USER_FIELDS
from lib.pcb.formats.export_view import prepare_export
from lib.pcb.formats.io import parse, serialize
from lib.pcb.model.objects import (new_document, new_component, new_pad, new_net,
                                   new_trace, new_point, new_user_field)


def build():
    design = new_document()
    board = design.one('/Board')
    net = board.one('Nets').append(new_net('SIGNAL'))
    pads = []
    for prefix, x in (('J', 30), ('R', 60)):
        component = board.one('Components').append(new_component('Example', design.refdes(prefix).first_free()))
        component['X'], component['Y'] = x, 30
        pattern = component.one('Pattern')
        pattern['Width'], pattern['Height'] = 6, 6
        pad = pattern.one('Pads').append(new_pad('1'))
        pad['PadWidth_New'], pad['PadHeight_New'] = 3, 3
        pad['PadHole'], pad['PadHoleH'] = Decimal('1.2'), Decimal('1.2')
        pad['Net'] = net
        pads.append(pad)
    trace = net.one('Traces').append(new_trace())
    for x in (30, 60):
        point = trace.one('Points').append(new_point(x=x, y=30, width=Decimal('.9')))
        point['Layer'] = board.one('Layers/Layer[1]')
    trace['Target1'], trace['Target2'] = pads
    design.validate()
    return design


class ProgrammaticWorkflowTests(unittest.TestCase):
    def assert_connected(self, design, *, refdes='R1'):
        board = design.one('/Board')
        net = board.one('Nets/Net')
        component = design.select('/Board/Components/Component', where=lambda row: row['RefDes'] == refdes)[0]
        pad = component.one('Pattern/Pads/Pad')
        trace = net.one('Traces/Trace')
        self.assertIs(pad['Net'], net)
        self.assertIs(trace['Target2'], pad)
        self.assertEqual(trace['Connected2'], 'Pad')
        self.assertEqual(trace['Object2'], component._ordinal())
        self.assertIs(trace.one('Points/Point[1]')['Layer'], board.one('Layers/Layer[1]'))
        design.validate()

    def test_constructed_connected_data_converts_between_all_three_formats(self):
        design = build()
        before = dumps(design, preserve=False)
        for input_format in ('dip', 'asc', 'dipxml'):
            report = ConversionReport()
            current = parse(serialize(design, format=input_format, report=report), report=report)
            self.assert_connected(current)
            self.assertEqual([n for n in report.warnings if n.rule != 'import-diagnostic'], [])
            for output_format in ('dip', 'asc', 'dipxml'):
                with self.subTest(source=input_format, destination=output_format):
                    rebuilt = parse(serialize(current, format=output_format, report=ConversionReport()),
                                    report=ConversionReport())
                    self.assert_connected(rebuilt)
        self.assertEqual(dumps(design, preserve=False), before)

    def test_refdes_search_data_edits_and_reordering_maintain_links_without_routing(self):
        design = build()
        resistor = design.select('/Board/Components/Component', where=lambda row: row['RefDes'] == 'R1')[0]
        trace = design.one('/Board/Nets/Net/Traces/Trace')
        geometry = [(point['X'], point['Y']) for point in trace.select('Points/Point')]
        resistor['RefDes'] = design.refdes('R').first_free()
        resistor['X'] = 90
        resistor.one('UserFields').append(new_user_field('Purpose', 'Sense input'))
        resistor.move_to(resistor.parent, 0)
        self.assertEqual(resistor['RefDes'], 'R2')
        self.assertEqual(trace['Object2'], 0)
        self.assertEqual([(point['X'], point['Y']) for point in trace.select('Points/Point')], geometry)
        for format in ('dip', 'asc', 'dipxml'):
            with self.subTest(format=format):
                rebuilt = parse(serialize(design, format=format, report=ConversionReport()), report=ConversionReport())
                self.assert_connected(rebuilt, refdes='R2')
                self.assertEqual(rebuilt.one('/Board/Components/Component[1]')['X'], 90)
                self.assertEqual(rebuilt.one('/Board/Components/Component[1]/UserFields/UserField')['Value'], 'Sense input')

    def test_created_component_field_collections_are_typed_and_editable(self):
        design = build()
        fields = design.one('/Board/Components/Component[1]/UserFields')
        self.assertIs(fields.schema, USER_FIELDS)
        field = fields.add('UserField', 'Drawing note', 'Example', 0)
        field['Value'] = 'Changed'
        self.assertEqual(field.values, ('Drawing note', 'Changed', 0))
        design.validate()

    def test_ascii_fallbacks_do_not_invent_an_unsupported_border_zone_setting(self):
        design = build()
        self.assertIsNone(design.one('/Board').child('SheetSettings'))
        view, _ = prepare_export(design, destination='asc', report=ConversionReport())
        self.assertIsNone(view.one('/Board/SheetSettings').child('BorderZones'))
        report = ConversionReport()
        serialize(design, format='asc', report=report)
        self.assertNotIn('sheet-border-zones', [notice.rule for notice in report.warnings])
        design.one('/Board').add('SheetSettings').add('BorderZones')['Visible'] = True
        report = ConversionReport()
        serialize(design, format='asc', report=report)
        self.assertIn('sheet-border-zones', [notice.rule for notice in report.warnings])


if __name__ == '__main__':
    unittest.main()
