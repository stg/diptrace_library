"""Natural units use the same schematic/PCB edits and serialization paths."""
from pathlib import Path
import tempfile
import unittest

from lib import (
    ConversionReport, new_schematic, new_symbol, new_pin, new_net,
    document_family, serialize, write, read, symbol_bounds,
)
from lib.pcb import serialize as pcb_serialize
from lib.pcb.formats import io as pcb_io
from lib.pcb.tests.test_dip_output import configured_document


def schematic():
    document = new_schematic()
    part = document.one('/Schematic/Components').append(new_symbol('Example', 'R1'))
    part['X'], part['Y'] = 76.2, -3.
    pin = part.one('Pins').append(new_pin())
    pin['X'], pin['Y'] = 6., -3.
    net = document.one('/Schematic/Nets').append(new_net('SIGNAL'))
    pin['Net'] = net
    return document


class UnitDocumentTests(unittest.TestCase):
    def test_schematic_references_renames_and_refdes_helpers_use_same_objects(self):
        document = schematic()
        view = document.in_units('mm')
        part = view.one('/Schematic/Components/Part')
        pin = part.one('Pins/Pin')
        net = view.one('/Schematic/Nets/Net')
        self.assertIs(pin['Net'], net)
        net['Name'] = 'SENSOR'
        self.assertIs(pin['Net'], net)
        self.assertEqual(document.one('/Schematic/Nets/Net')['Name'], 'SENSOR')
        part['RefDes'] = 'R2'
        self.assertEqual(view.refdes('R').designators(), ['R2'])
        self.assertIs(view.refdes('R').matches()[0], part)
        copied = view.copy(part, fields={'RefDes': 'R3', 'X': 10.})
        self.assertEqual(copied.model['X'], 30.)
        with self.assertRaises(ValueError):
            copied['RefDes'] = 'R2'
        self.assertEqual(copied['RefDes'], 'R3')
        self.assertEqual(document_family(view), 'schematic')
        document.validate()

    def test_schematic_addition_converts_before_atomic_attachment_and_bounds_use_view_units(self):
        document = schematic()
        part = document.in_units('mm').one('/Schematic/Components/Part')
        pin = part.one('Pins').add('Pin', 1, 2., 3.)
        self.assertEqual((pin['X'], pin['Y']), (2., 3.))
        self.assertEqual((pin.model['X'], pin.model['Y']), (6., 9.))
        raw, visible = symbol_bounds(part.model), symbol_bounds(part)
        self.assertEqual((visible.left, visible.top, visible.right, visible.bottom),
                         tuple(value/3 for value in (raw.left, raw.top, raw.right, raw.bottom)))
        before = tuple(part.model.one('Pins').children())
        with self.assertRaises(ValueError):
            part.one('Pins').add('Pin', 2, 1., float('nan'))
        self.assertEqual(tuple(part.model.one('Pins').children()), before)
        # add() permits incremental construction, just like the canonical tree.
        # Complete the remaining authoring choices with the ordinary constructor.
        for field in new_pin(1).children():
            if field.kind not in pin:
                pin.append(field.clone())
        document.validate()

    def test_all_schematic_outputs_and_reports_ignore_the_selected_editing_units(self):
        document = schematic()
        for format in ('dch', 'asc', 'dchxml'):
            expected_report = ConversionReport()
            expected = serialize(document, format=format, report=expected_report)
            for units in ('mm', 'mil', 'inch'):
                with self.subTest(format=format, units=units):
                    report = ConversionReport()
                    view = document.in_units(units)
                    self.assertEqual(serialize(view, format=format, report=report), expected)
                    self.assertEqual(report.notices, expected_report.notices)
                    self.assertEqual(getattr(view, 'to_'+format+'_bytes')(report=ConversionReport()), expected)
        source = document.in_units('inch').as_dchxml(report=ConversionReport())
        self.assertEqual(source.representation, 'dchxml')
        with self.assertRaises(TypeError):
            source.in_units('mm')

    def test_pcb_editing_scales_geometry_without_changing_angles_or_inherited_widths(self):
        document = configured_document()
        view = document.in_units('mm')
        component = view.one('/Board/Components/Component')
        component['X'], component['Y'], component['Angle'] = 2., -3., .37
        self.assertEqual((component.model['X'], component.model['Y'], component.model['Angle']), (6., -9., .37))
        points = view.select('/Board/Nets/Net/Traces/Trace/Points/Point')
        point = points[1]
        point['Width'] = -1
        self.assertEqual(point.model['Width'], -1)
        point['Width'] = 1.
        self.assertEqual(point.model['Width'], 3.)
        selected = view.find_all('Point', where=lambda item: item.get('Width') == 1.)
        self.assertIn(point, selected)
        clone = view.clone()
        clone.one('/Board/Components/Component')['X'] = 4.
        self.assertEqual(component['X'], 2.)
        self.assertEqual(document_family(view), 'pcb')
        document.validate()

    def test_all_pcb_outputs_and_explicit_xml_inspection_share_canonical_data(self):
        document = configured_document()
        for format in ('dip', 'asc', 'dipxml'):
            expected_report = ConversionReport()
            expected = serialize(document, format=format, report=expected_report)
            for units in ('mm', 'mil', 'inch'):
                with self.subTest(format=format, units=units):
                    view = document.in_units(units)
                    report = ConversionReport()
                    self.assertEqual(pcb_serialize(view, format=format, report=report), expected)
                    self.assertEqual(report.notices, expected_report.notices)
                    self.assertEqual(pcb_io.serialize(view, format=format, report=ConversionReport()), expected)
        projected = pcb_io.project(document.in_units('inch'), format='dipxml', report=ConversionReport())
        self.assertEqual(projected.representation, 'dipxml')
        document.validate()

    def test_file_io_and_view_defaults_are_separate_from_destination_context(self):
        for document, format, path in ((schematic(), 'dch', '/Schematic/Components/Part'),
                                       (configured_document(), 'dip', '/Board/Components/Component')):
            with self.subTest(format=format), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary)/('example.'+format)
                view = document.in_units('mm')
                view.one(path)['X'] = 2.
                write(view, target, report=ConversionReport())
                reopened = read(target, report=ConversionReport())
                self.assertEqual(reopened.one(path)['X'], 6.)
                self.assertEqual(reopened.in_units('inch').one(path)['X'], 6/76.2)


if __name__ == '__main__':
    unittest.main()
