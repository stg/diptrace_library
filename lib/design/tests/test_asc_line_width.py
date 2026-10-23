"""One current pen setting, with inherited display supplied at export."""
from decimal import Decimal
import unittest

from lib.design import AscExportContext, ExportReport, new_schematic, parse_asc
from lib.design.schematic_objects import new_pattern_shape, new_symbol
from lib.design.schematic_refs import bind_schematic_references


def source(*, cached=False, current_width=-1, named=True):
    document = new_schematic()
    part = document.one('/Schematic/Components').append(new_symbol('Box', 'U1'))
    pattern = part.one('Pattern')
    pattern.set_values('Frame')
    pattern.set_field('Width', 30)
    pattern.set_field('Height', 30)
    shape = pattern.one('Shapes').insert(new_pattern_shape(kind=1), 1)
    shape.set_field('Width', -1)
    shape.one('Points_New').add('pt', -1, -1)
    shape.one('Points_New').add('pt', 1, 1)
    if cached:
        slot = document.one('/Schematic/CacheLib/Slots').add('Slot', 0, '')
        slot.add('VariablePath', '')
        definition = slot.add('Definition', 0)
        definition.append(new_symbol('Cached box', '', placed=False))
        definition.append(pattern.clone())
    bind_schematic_references(document)
    raw = parse_asc(document.to_asc_bytes().decode('cp1252'))
    shape_record = raw.one('/Schematic/Components/Part/Pattern/Shapes/Shape[2]')
    shape_record.set_argument(16, Decimal('.73'))
    widths = raw.one('/Schematic/Components/Part/Pattern/Shapes').children('Width')
    widths[1].set_values(current_width)
    if not named:
        widths[1].detach()
    if cached:
        raw.one('/Schematic/CacheLib/cl_Components/cl_Component/cl_Pattern/cl_Shapes/cl_Shape[2]').set_argument(16, Decimal('.57'))
        widths = raw.one('/Schematic/CacheLib/cl_Components/cl_Component/cl_Pattern/cl_Shapes').children('cl_Width')
        widths[1].set_values(current_width)
        if not named:
            widths[1].detach()
    return raw.as_schematic()


def shape(document):
    return document.one('/Schematic/Components/Part/Pattern/Shapes/Shape[2]')


def width(document, context=None):
    projected = document.as_asc(context=context)
    drawing = shape(projected)
    return drawing.values[16], drawing.parent.children('Width')[1].values[0]


class AscLineWidthTests(unittest.TestCase):
    def test_named_width_replaces_both_placed_and_cached_header_widths(self):
        current = source(cached=True, current_width=Decimal('.28'))
        for _ in range(3):
            projected = current.as_asc()
            self.assertEqual(shape(projected).values[16], Decimal('.28'))
            cached = projected.one('/Schematic/CacheLib/cl_Components/cl_Component/cl_Pattern/cl_Shapes/cl_Shape[2]')
            self.assertEqual(cached.values[16], Decimal('.28'))
            self.assertFalse(current.root.changed)
            current = parse_asc(projected.to_asc_bytes().decode('cp1252')).as_schematic()

    def test_repeated_asc_cycles_keep_inheritance_without_header_history(self):
        current = source()
        for _ in range(3):
            self.assertEqual(width(current), (Decimal('.1'), -1))
            self.assertIsNone(shape(current).child('StoredData'))
            self.assertFalse(current.root.changed)
            current = parse_asc(current.to_asc_bytes().decode('cp1252')).as_schematic()

    def test_context_resolves_only_inheritance_and_never_overrides_explicit_width(self):
        current = source()
        context = AscExportContext(line_width=lambda layer: .42)
        self.assertEqual(width(current, context), (Decimal('.42'), -1))
        self.assertEqual(width(current), (Decimal('.1'), -1))
        self.assertFalse(current.root.changed)
        shape(current).set_field('Width', Decimal('.9'))
        self.assertEqual(width(current, context), (Decimal('.9'), Decimal('.9')))

    def test_export_depends_on_current_layer_and_width_without_edit_history(self):
        for field, value in (('Width', -2), ('Layer', 1)):
            current = source()
            shape(current).set_field(field, value)
            self.assertEqual(width(current)[0], Decimal('.1'))
            context = AscExportContext(line_width=lambda layer: Decimal('.2') if layer == 1 else Decimal('.3'))
            expected = Decimal('.2') if field == 'Layer' else Decimal('.3')
            self.assertEqual(width(current, context)[0], expected)
        current = source()
        shape(current).set_field('Layer', 1)
        shape(current).set_field('Layer', 0)
        self.assertEqual(width(current), width(source()))

    def test_header_supplies_width_when_the_named_setting_is_absent(self):
        current = source(cached=True, named=False)
        self.assertEqual(shape(current).scalar('Width'), Decimal('.73'))
        cached = current.one('/Schematic/CacheLib/Slots/Slot/Definition/Pattern/Shapes/Shape[2]')
        self.assertEqual(cached.scalar('Width'), Decimal('.57'))
        for destination in ('dch', 'asc', 'dchxml'):
            with self.subTest(destination=destination):
                from lib.design import parse
                converted = parse(getattr(current, 'to_'+destination+'_bytes')(), format=destination)
                self.assertEqual(shape(converted).scalar('Width'), Decimal('.73'))

    def test_invalid_context_is_an_export_error_without_changing_the_source(self):
        current = source()
        for invalid in ('invalid', -1, True):
            report = ExportReport()
            context = AscExportContext(line_width=lambda layer: invalid)
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'nonnegative number'):
                current.to_asc_bytes(context=context, report=report)
            self.assertEqual(len(report.errors), 1)
        self.assertFalse(current.root.changed)


if __name__ == '__main__':
    unittest.main()
