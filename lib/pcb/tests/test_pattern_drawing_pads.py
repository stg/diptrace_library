"""Drawing pad assignments use footprint-local identities, not saved keys."""
import unittest
from xml.etree import ElementTree

from lib.common.conversion import ConversionReport
from lib.common.references import ReferenceError
from lib.pcb.formats import io
from lib.pcb.tests.test_dipxml_library import read, source


CACHED = '/Board/CacheLib/Slots/Slot/Definition/Pattern'
PLACED = '/Board/Components/Component/Pattern'


def design(key=17, *, zero_pad=False):
    root = ElementTree.fromstring(source())
    root.find('Library/Library/Patterns/Pattern/Shapes/Shape').set('PadId', str(key))
    if zero_pad:
        for pad in root.iter('Pad'):
            if pad.get('Id') == '17':
                pad.set('Id', '0')
        root.find('Library/Components/Component/Part/Pins/Pin').set('PadId', '0')
        root.find('Library/Components/Component/Part/InternalConnections/IntCon').set('X', '0')
        root.find('Board/Nets/Net/Pads/Item').set('Pad', '0')
        root.find('Board/Nets/Net/Traces/Trace').set('SubObject1', '0')
    report = ConversionReport()
    document = read(ElementTree.tostring(root, encoding='unicode'), report=report)
    return document, report


class PatternDrawingPadTests(unittest.TestCase):
    def test_unavailable_xml_pad_keys_detach_only_the_assignment(self):
        for key in (0, 404):
            with self.subTest(key=key):
                document, report = design(key)
                for path in (CACHED, PLACED):
                    shape = document.one(path+'/Shapes/Shape')
                    self.assertIsNone(shape['Pad'])
                    self.assertEqual(shape['PadId'], -1)
                    self.assertIsNone(shape.child('PadId'))
                    self.assertEqual(len(shape.select('Points_New/pt')), 2)
                notices = [n for n in report.notices if n.rule == 'unavailable-drawing-pad']
                self.assertEqual(len(notices), 1)
                self.assertEqual(notices[0].severity, 'info')
                self.assertFalse(report.errors)
                document.references.validate()

    def test_declared_zero_key_is_a_real_pad_assignment(self):
        document, report = design(0, zero_pad=True)
        self.assertNotIn('unavailable-drawing-pad', {n.rule for n in report.notices})
        for path in (CACHED, PLACED):
            pattern = document.one(path)
            shape = pattern.one('Shapes/Shape')
            self.assertIs(shape['Pad'], pattern.one('Pads/Pad[1]'))
            self.assertEqual(shape['PadId'], 1)

    def test_assignment_follows_reordering_in_each_independent_footprint(self):
        document, _ = design()
        for path in (CACHED, PLACED):
            pattern = document.one(path)
            shape = pattern.one('Shapes/Shape')
            pad = shape['Pad']
            pad.move_to(pad.parent, 1)
            self.assertIs(shape['Pad'], pad)
            self.assertEqual(shape['PadId'], 2)
        document.references.validate()

    def test_edits_require_local_pad_identity_and_derived_index_is_read_only(self):
        document, _ = design()
        pattern = document.one(CACHED)
        shape = pattern.one('Shapes/Shape')
        other = pattern.one('Pads/Pad[2]')
        shape['Pad'] = other
        self.assertIs(shape['Pad'], other)
        with self.assertRaises(ReferenceError):
            shape['Pad'] = document.one(PLACED+'/Pads/Pad[1]')
        self.assertIs(shape['Pad'], other)
        with self.assertRaises(TypeError):
            shape['PadId'] = 1
        shape['Pad'] = None
        self.assertEqual(shape['PadId'], -1)
        shape['Pad'] = other
        with self.assertRaises(ReferenceError):
            other.detach()
        with self.assertRaises(ReferenceError):
            shape.move_to(document.one(PLACED+'/Shapes'))
        self.assertIs(shape.parent, pattern.one('Shapes'))

    def test_copy_and_clone_remap_the_assignment_to_their_own_pad(self):
        document, _ = design()
        definition = document.one(CACHED).parent
        copied = document.copy(definition, parent=definition.parent)
        shape = copied.one('Pattern/Shapes/Shape')
        self.assertIs(shape['Pad'], copied.one('Pattern/Pads/Pad[1]'))
        self.assertIsNot(shape['Pad'], definition.one('Pattern/Pads/Pad[1]'))
        cloned = document.clone()
        self.assertIs(cloned.one(PLACED+'/Shapes/Shape')['Pad'], cloned.one(PLACED+'/Pads/Pad[1]'))
        document.references.validate()
        cloned.references.validate()

    def test_xml_roundtrip_preserves_identity_and_dip_omission_is_reported(self):
        document, _ = design()
        rebuilt = io.parse(io.serialize(document, format='dipxml', report=ConversionReport()),
                           report=ConversionReport())
        for path in (CACHED, PLACED):
            self.assertIs(rebuilt.one(path+'/Shapes/Shape')['Pad'], rebuilt.one(path+'/Pads/Pad[1]'))
        report = ConversionReport()
        io.serialize(document, format='dip', report=report)
        self.assertTrue({'cached-drawing-pad', 'placed-drawing-pad'} <= {n.rule for n in report.warnings})
        self.assertIs(document.one(PLACED+'/Shapes/Shape')['Pad'], document.one(PLACED+'/Pads/Pad[1]'))

    def test_ascii_omission_warns_and_preserves_geometry_without_changing_source(self):
        document, _ = design()
        shapes = [document.one(path+'/Shapes/Shape') for path in (CACHED, PLACED)]
        targets = [shape['Pad'] for shape in shapes]
        geometry = [[point.values for point in shape.select('Points_New/pt')] for shape in shapes]
        report = ConversionReport()
        rebuilt = io.parse(io.serialize(document, format='asc', report=report), report=ConversionReport())
        self.assertTrue({'cached-footprint-drawing-options', 'placed-drawing-pad'}
                        <= {notice.rule for notice in report.warnings})
        self.assertFalse(report.errors)
        for path, shape, target, points in zip((CACHED, PLACED), shapes, targets, geometry):
            # A placed footprint can acquire calculated text during export.
            # Select the original primitive whose pad mapping is being tested.
            current = rebuilt.one(path+'/Shapes/Shape',
                                  where=lambda drawing: drawing['Type'] == shape['Type'])
            self.assertIsNone(current['Pad'])
            self.assertEqual([point.values for point in current.select('Points_New/pt')], points)
            self.assertIs(shape['Pad'], target)
            self.assertEqual([point.values for point in shape.select('Points_New/pt')], points)


if __name__ == '__main__':
    unittest.main()
