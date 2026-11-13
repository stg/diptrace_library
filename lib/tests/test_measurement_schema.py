"""Both document families declare physical quantities without guessing by name."""
import unittest

from lib import schematic_schema
from lib.pcb.model.catalogue import pcb_schema
from lib.common import footprint_records, symbol_records, supplier_records
from lib.common.measurements import LengthUnits


class MeasurementSchemaTests(unittest.TestCase):
    def test_every_scalar_number_has_an_explicit_domain_in_both_catalogues(self):
        for catalogue in (schematic_schema(), pcb_schema()):
            for record in catalogue.values():
                for field in record.fields.values():
                    if 'number' in field.kind.split('|'):
                        with self.subTest(record=record.name, field=field.name):
                            self.assertTrue(field.unit)

    def test_shared_physical_records_have_the_same_measurements_in_both_families(self):
        for record in (footprint_records.PATTERN,
                       footprint_records.MODEL_OFFSET, footprint_records.MODEL_ROTATE,
                       footprint_records.MODEL_ZOOM):
            for catalogue in (schematic_schema(), pcb_schema()):
                with self.subTest(record=record.name):
                    actual = catalogue[record.name]
                    for name, field in record.fields.items():
                        self.assertEqual(actual.fields[name].unit, field.unit)
                        self.assertEqual(actual.fields[name].unit_sentinels, field.unit_sentinels)
                        self.assertIs(actual.fields[name].unit_selector, field.unit_selector)
        # PCB pads extend the shared definition with placed/library constraints.
        for actual in (schematic_schema()['Pad'], pcb_schema()['PcbPad'], pcb_schema()['LibraryPad']):
            for name, field in footprint_records.PAD.fields.items():
                if field.unit:
                    self.assertEqual(actual.fields[name].unit, field.unit)

    def test_identically_named_3d_axes_have_different_domains(self):
        units = LengthUnits('inch')
        for name in ('X', 'Y', 'Z'):
            self.assertEqual(units.field_value(footprint_records.MODEL_OFFSET.fields[name], 76.2), 1.)
            self.assertEqual(units.field_value(footprint_records.MODEL_ROTATE.fields[name], 76.2), 76.2)
            self.assertEqual(units.field_value(footprint_records.MODEL_ZOOM.fields[name], 76.2), 76.2)

    def test_font_size_price_and_percentages_are_not_physical_lengths(self):
        units = LengthUnits('inch')
        for field in (footprint_records.PATTERN_SHAPE.fields['FontSize'],
                      footprint_records.PAD.fields['PadCorner'],
                      supplier_records.QUOTE.fields['Price']):
            self.assertEqual(units.field_value(field, 76.2), 76.2)
        self.assertEqual(units.field_value(symbol_records.PIN.fields['Length'], 76.2), 1.)

    def test_real_inherited_values_remain_separate_from_signed_geometry(self):
        units = LengthUnits('mm')
        mask = footprint_records.PAD.fields['CustomSwell_New']
        stroke = footprint_records.PATTERN_SHAPE.fields['FontWidth']
        coordinate = footprint_records.MODEL_OFFSET.fields['X']
        self.assertEqual(units.field_value(mask, -1000), -1000)
        self.assertEqual(units.field_value(mask, -.75), -.25)
        self.assertEqual(units.field_value(stroke, -2), -2)
        self.assertEqual(units.field_value(stroke, 3), 1.)
        self.assertEqual(units.field_value(coordinate, -3), -1.)


if __name__ == '__main__':
    unittest.main()
