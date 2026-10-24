"""Legacy labels modernize once using current properties and optional metrics."""
import math
import unittest
from unittest.mock import patch

from lib import ImportContext, new_schematic, parse
from lib.schematic.formats.dch.compat import (restore_legacy_dimensions, recenter_legacy_symbols)
from lib.schematic.formats.dch.labels import (upgrade_instance_labels, discard_legacy_label_slots)
from lib.schematic.formats.import_context import (modernize_font_settings)
from lib.schematic.model.objects import (new_symbol, new_symbol_shape)
from lib.schematic.layout.text_layout import (TextLayout)
from lib.common.text.vector import (TextMetrics)


def legacy_document(*, vector=True, dimensions=(10, 6), corners=((0, 0), (10, 6)), alignment=2, shifts=(1, 2)):
    document = new_schematic()
    # Build an obsolete input state for the import-modernization boundary.
    document._automatic_structure = False
    root = document.one('/Schematic')
    root.set_field('PartFontVector', vector)
    for name, value in (('ShowText', 2), ('TextAlign', alignment), ('ShowText2', 0), ('TextAlign2', 0)):
        root.set_field(name, value)
    settings = root.one('Settings')
    for name in ('PartFontSize', 'PartFontColor', 'UsePartFontColor'):
        settings.one(name).detach()
    part = root.one('Components').append(new_symbol('Box', 'R1'))
    for name in ('ShowRefDes', 'ShowName', 'ShowValue', 'ShowManufacturer', 'ShowDatasheet'):
        part.one(name).detach()
    for name, value in (('Width', dimensions[0]), ('Height', dimensions[1]), ('X', 100), ('Y', 200),
                        ('ShowText', 0), ('TextAlign', alignment), ('ShowText2', 0), ('TextAlign2', 0),
                        ('FieldIndex1', -1), ('FieldIndex2', -1), ('TextPosX', shifts[0]),
                        ('TextPosY', shifts[1]), ('TextPosX2', 0), ('TextPosY2', 0)):
        part.set_field(name, value)
    shape = part.one('Shapes').append(new_symbol_shape())
    for point in corners:
        shape.one('Points_New').add('pt', *point)
    return document, root, part


def modernize(root, context):
    modernize_font_settings(root, context)
    upgrade_instance_labels(39, root, font_size=root.one('Settings').scalar('PartFontSize'),
                            font_name=context.font_name, text_layout=context.layout)
    restore_legacy_dimensions(39, root)
    recenter_legacy_symbols(39, root)
    discard_legacy_label_slots(root)


class ImportContextTests(unittest.TestCase):
    def test_vector_labels_need_no_platform_service_or_source_snapshots(self):
        _, root, part = legacy_document()
        with patch('lib.schematic.layout.text_layout._system_metrics', side_effect=AssertionError('unexpected platform access')):
            modernize(root, ImportContext())
        self.assertEqual((part.scalar('X'), part.scalar('Y')), (105, 203))
        self.assertEqual(part.one('ShowRefDes').values[-3:-1], (-4, -8))
        self.assertEqual((part.scalar('X')-4, part.scalar('Y')-8), (101, 195))
        for name in ('ShowText', 'TextAlign', 'TextPosX', 'FieldIndex1'):
            self.assertIsNone(part.child(name))
        self.assertEqual(part.select('StoredData/OriginShift'), [])
        self.assertEqual(part.select('StoredData/Width'), [])
        self.assertEqual(root.one('Settings').scalar('PartFontSize'), 2)

    def test_injected_system_metrics_resolve_placement_during_import(self):
        calls = []
        def measure(text, family, size):
            calls.append((text, family, size))
            return TextMetrics(100, 20)
        _, root, part = legacy_document(vector=False, dimensions=(2, 10),
            corners=((-1, -5), (1, 5)), alignment=7, shifts=(1, 0))
        with patch('lib.schematic.layout.text_layout._system_metrics', side_effect=AssertionError('unexpected platform access')):
            modernize(root, ImportContext(font_size=3, font_name='ExampleSans', text_layout=TextLayout(measure)))
        self.assertEqual(calls, [('R1', 'ExampleSans', 25)])
        label = part.one('ShowRefDes')
        self.assertEqual(label.values[2:7], (8, 0, 1, -1, -1))
        self.assertAlmostEqual(float(label.values[-1]), math.pi/2)
        self.assertFalse(root.scalar('PartFontVector'))
        self.assertEqual(root.one('Settings').scalar('PartFontSize'), 3)

    def test_stored_settings_win_and_one_context_is_accepted_by_every_input(self):
        source = new_schematic()
        context = ImportContext(font_size=3)
        stored = source.one('/Schematic/Settings').scalar('PartFontSize')
        for format in ('dch', 'asc', 'dchxml'):
            data = getattr(source, 'to_'+format+'_bytes')()
            loaded = parse(data, format=format, context=context)
            self.assertEqual(loaded.one('/Schematic/Settings').scalar('PartFontSize'), stored)
        for invalid in (True, 0, 1.5):
            with self.assertRaises(ValueError):
                ImportContext(font_size=invalid)


if __name__ == '__main__':
    unittest.main()
