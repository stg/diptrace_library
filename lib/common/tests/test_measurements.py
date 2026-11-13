"""Natural measurements retain axes, typed domains and current model facts."""
from decimal import Decimal
import math
import unittest

from lib.common.measurements import (
    LengthUnits, get_default_units, set_default_units, using_units, nonnegative_length,
)
from lib.common.schema import Field, Record, with_units
from lib.common.units import XmlUnits


class MeasurementTests(unittest.TestCase):
    def test_shared_scales_match_xml_lengths_without_inheriting_its_axis_reversal(self):
        for name in ('mm', 'mil', 'inch'):
            view, xml = LengthUnits(name), XmlUnits(name)
            for value in (0, -.25, 76.2, Decimal('1.2345')):
                with self.subTest(units=name, value=value):
                    self.assertEqual(view.from_shared(value), xml.length(value))
                    self.assertEqual(view.to_shared(value), xml.internal_length(value))
                    self.assertEqual(view.from_shared(value, power=2), xml.area(value))
            self.assertGreater(view.from_shared(3), 0)
            self.assertLess(xml.point(0, 3)[1], 0)
        self.assertEqual(LengthUnits('in').units, 'inch')

    def test_default_changes_only_affect_new_views_and_contexts_restore_after_failure(self):
        original = get_default_units()
        try:
            set_default_units('mm')
            existing = LengthUnits()
            with self.assertRaises(RuntimeError):
                with using_units('inch'):
                    self.assertEqual(LengthUnits().units, 'inch')
                    self.assertEqual(existing.units, 'mm')
                    raise RuntimeError('probe')
            self.assertEqual(get_default_units(), 'mm')
            with using_units('mil'):
                with using_units('inch'):
                    self.assertEqual(LengthUnits().units, 'inch')
                self.assertEqual(LengthUnits().units, 'mil')
        finally:
            set_default_units(original)

    def test_mixed_tuple_conversion_leaves_identity_orientation_and_optional_values_intact(self):
        point = Field('Location', 'tuple', members=(
            Field('Id', 'integer'), Field('X', 'number', unit='shared length'),
            Field('Y', 'number', unit='shared length', nullable=True), Field('Angle', 'number', unit='radians')))
        value = (2**70+3, 76.2, None, 7.25)
        units = LengthUnits('inch')
        visible = units.field_value(point, value)
        self.assertEqual(visible, (2**70+3, 1., None, 7.25))
        self.assertIs(type(visible[0]), int)
        self.assertEqual(units.field_value(point, visible, to_shared=True, current=value), value)
        homogeneous = Field('Lengths', 'tuple', unit='shared length', item_kind='number')
        self.assertEqual(LengthUnits('mm').field_value(homogeneous, (3, -6)), (1., -2.))

    def test_inherited_selections_and_negative_physical_coordinates_have_distinct_rules(self):
        units = LengthUnits('mm')
        coordinate = Field('X', 'number', unit='shared length')
        clearance = Field('Clearance', 'number', unit='shared length', unit_sentinels=(-1,))
        stroke = Field('Width', 'number', unit='shared length', unit_selector=nonnegative_length)
        mask = Field('CustomSwell', 'number', unit='shared length', unit_sentinels=(-1000,))
        self.assertEqual(units.field_value(coordinate, -3), -1.)
        self.assertEqual(units.field_value(clearance, -1), -1)
        self.assertEqual(units.field_value(clearance, -.75), -.25)
        self.assertEqual(units.field_value(stroke, -.5), -.5)
        self.assertEqual(units.field_value(stroke, 3), 1.)
        self.assertEqual(units.field_value(mask, -1000), -1000)
        self.assertEqual(units.field_value(mask, -3), -1.)

    def test_unchanged_visible_assignments_never_accumulate_rounding(self):
        definitions = (Field('X', 'number', unit='shared length'),
                       Field('Area', 'number', unit='shared length squared'))
        for definition in definitions:
            for original in (0., .3, -.508, 133.35, math.nextafter(9., 10.)):
                current = original
                for _ in range(64):
                    for name in ('mm', 'mil', 'inch'):
                        units = LengthUnits(name)
                        visible = units.field_value(definition, current)
                        current = units.field_value(definition, visible, to_shared=True, current=current)
                self.assertEqual(current, original)
        nullable = Field('Width', 'number', unit='shared length', nullable=True)
        self.assertEqual(LengthUnits('mm').field_value(nullable, 2., to_shared=True, current=None), 6.)

    def test_unchanged_physical_value_takes_precedence_over_a_coinciding_selection(self):
        units = LengthUnits('mm')
        field = Field('Offset', 'number', unit='shared length', unit_sentinels=(-1,))
        visible = units.field_value(field, -3.)
        self.assertEqual(visible, -1.)
        self.assertEqual(units.field_value(field, visible, to_shared=True, current=-3.), -3.)
        self.assertEqual(units.field_value(field, -1, to_shared=True, current=3.), -1)

    def test_invalid_numbers_and_powers_are_not_silently_converted(self):
        units = LengthUnits('mm')
        for value in (True, None, '1'):
            with self.assertRaises(TypeError):
                units.from_shared(value)
        for value in (float('inf'), float('nan'), Decimal('NaN'), 10**1000):
            with self.assertRaises(ValueError):
                units.from_shared(value)
        for power in (0, 3, True, 1.):
            with self.assertRaises(ValueError):
                units.from_shared(1, power=power)
        with self.assertRaises(ValueError):
            LengthUnits('inch').to_shared(1e308)

    def test_conditional_units_reject_invalid_numbers_before_selecting_inheritance(self):
        units = LengthUnits('mm')
        stroke = Field('Width', 'number', unit='shared length', unit_selector=nonnegative_length)
        for value in (True, '1'):
            with self.assertRaises(TypeError):
                units.field_value(stroke, value)
        for value in (float('inf'), -float('inf'), float('nan'), Decimal('NaN')):
            with self.assertRaises(ValueError):
                units.field_value(stroke, value)

    def test_measurement_declarations_preserve_constraints_and_reject_unknown_fields(self):
        record = Record('Point', {'X': Field('X', 'number', required=True, nullable=True, default=None)})
        measured = with_units(record, {'X': 'shared length'}, sentinels={'X': (-1,)})
        self.assertEqual(record.fields['X'].unit, '')
        self.assertEqual(measured.fields['X'].unit, 'shared length')
        self.assertEqual(measured.fields['X'].unit_sentinels, (-1,))
        self.assertTrue(measured.fields['X'].required)
        self.assertTrue(measured.fields['X'].nullable)
        self.assertIsNone(measured.fields['X'].default)
        with self.assertRaises(KeyError):
            with_units(record, {'Other': 'shared length'})
        with self.assertRaises(TypeError):
            Field('X', unit_selector=3)


if __name__ == '__main__':
    unittest.main()
