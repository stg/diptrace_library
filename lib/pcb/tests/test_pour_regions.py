"""Available, unassigned and unavailable fill classification stay distinct."""
import unittest
from unittest.mock import patch

from lib.common.asc import dumps, loads_bytes
from lib.common.conversion import ConversionReport
from lib.common.model import Element
from lib.common.references import Property, ReferenceError
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import DIP
from lib.pcb.formats.dip.pours import read_base_pours
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.writer import Writer
from lib.pcb.formats.dip.write_graphics import write_base_pours
from lib.pcb.model.objects import new_document


FILL = '/Board/CopperPours/CopperPour[1]/Fill'


def design(*, available=True):
    document = new_document()
    pour = document.one('/Board').add('CopperPours').add('CopperPour')
    pour['Enabled'], pour['Poured'] = True, True
    pour['Layer'] = document.one('/Board/Layers/Layer[1]')
    points = pour.add('Points')
    for point in ((0, 0), (10, 0), (10, 10)):
        points.add('pt', *point)
    fill = pour.add('Fill')
    if available:
        groups = fill.add('Regions')
        first, second = groups.add('Region', 2), groups.add('Region', 7)
    line = fill.add('Lines').add('Line')
    for name, value in dict(X1=1, Y1=2, X2=3, Y2=4).items():
        line[name] = value
    spoke = fill.add('SpokeLine').add('Line')
    for name, value in dict(X1=3, Y1=4, X2=5, Y2=6, Width=1).items():
        spoke[name] = value
    polygon = fill.add('Polygons').add('Poly')
    points = polygon.add('Points')
    for point in ((1, 1), (3, 1), (2, 3)):
        points.add('pt', *point)
    if available:
        line['Region'], polygon['Region'] = first, second
    document.validate()
    return document


class PourRegionTests(unittest.TestCase):
    def test_group_label_edits_update_members_and_projections_without_rebuilding(self):
        document = design()
        line = document.one(FILL+'/Lines/Line')
        group = line['Region']
        probe = document.root.add('Probe', 0)
        document.references.bind(probe, line, Property(probe, 'RegionId'), role='probe')
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole tree scan')), \
                patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            group['Number'] = 19
            self.assertEqual((line['RegionId'], probe.values[0]), (19, 19))
            line['Region'] = document.one(FILL+'/Regions/Region[2]')
            self.assertEqual(probe.values[0], 7)
        with self.assertRaises(TypeError):
            line['RegionId'] = 8
        document.validate()

    def test_duplicate_negative_and_cross_fill_edits_are_atomic(self):
        document = design()
        first, second = document.select(FILL+'/Regions/Region')
        before = dumps(document, preserve=False)
        for number in (2, -1):
            with self.assertRaises(ValueError):
                second['Number'] = number
            self.assertEqual(dumps(document, preserve=False), before)
        with self.assertRaises(ValueError):
            first.parent.add('Region', 2)
        other = document.one('/Board/CopperPours').add('CopperPour')
        group = other.add('Fill').add('Regions').add('Region', 20)
        line = document.one(FILL+'/Lines/Line')
        with self.assertRaises(ReferenceError):
            line['Region'] = group
        self.assertIs(line['Region'], first)
        with self.assertRaises(ReferenceError):
            first.move_to(group.parent)
        self.assertIs(first.parent, document.one(FILL+'/Regions'))

    def test_referenced_groups_require_explicit_disconnect_before_removal(self):
        document = design()
        line = document.one(FILL+'/Lines/Line')
        group = line['Region']
        with self.assertRaises(ReferenceError):
            document.remove(group)
        line['Region'] = None
        document.remove(group)
        self.assertEqual(line['RegionId'], -1)
        polygon = document.one(FILL+'/Polygons/Poly')
        polygon['Region'] = None
        document.one(FILL+'/Regions').detach()
        self.assertIsNone(document.one(FILL).child('Regions'))
        document.validate()

    def test_members_and_classification_cannot_leave_their_referenced_fill(self):
        document = design()
        other = document.one('/Board/CopperPours').add('CopperPour').add('Fill')
        lines = other.add('Lines')
        before = dumps(document, preserve=False)
        with self.assertRaises(ReferenceError):
            document.one(FILL+'/Lines/Line').move_to(lines)
        self.assertEqual(dumps(document, preserve=False), before)
        with self.assertRaises(ReferenceError):
            document.one(FILL+'/Regions').move_to(other)
        self.assertEqual(dumps(document, preserve=False), before)
        document.validate()

    def test_owned_fill_copy_and_document_clone_keep_their_group_identities(self):
        document = design()
        duplicate = document.clone()
        self.assertIs(duplicate.one(FILL+'/Lines/Line')['Region'], duplicate.one(FILL+'/Regions/Region[1]'))
        self.assertIsNot(duplicate.one(FILL+'/Regions/Region[1]'), document.one(FILL+'/Regions/Region[1]'))
        other = document.one('/Board/CopperPours').add('CopperPour')
        copied = document.copy(document.one(FILL), parent=other)
        self.assertIs(copied.one('Lines/Line')['Region'], copied.one('Regions/Region[1]'))
        self.assertIsNot(copied.one('Regions/Region[1]'), document.one(FILL+'/Regions/Region[1]'))
        document.validate()

    def test_valid_unassigned_and_available_empty_classifications_survive_all_binary_profiles(self):
        document = design()
        before = dumps(document, preserve=False)
        for version in DIP.write_versions:
            writer = Writer(version)
            writer.header()
            write_base_pours(writer, document.one('/Board'))
            data = bytes(writer.buffer)
            # The validity Boolean precedes the final three-byte priority.
            self.assertEqual(data[-4], 1)
            raw = read_base_pours(Reader(data), Element('Board'))[0]
            self.assertTrue(raw.regions_counted)
            self.assertEqual(raw.pour.one('Fill/SpokeLine/Line')['Region'], -1)
            rebuilt = io.parse(io.serialize(document, format='dip', version=version,
                report=ConversionReport()), report=ConversionReport())
            self.assertIsNotNone(rebuilt.one(FILL).child('Regions'))
            self.assertIsNone(rebuilt.one(FILL+'/SpokeLine/Line')['Region'])
            self.assertEqual(rebuilt.one(FILL+'/Lines/Line')['RegionId'], 2)
        self.assertEqual(dumps(document, preserve=False), before)
        fill = document.one(FILL)
        for name in ('Lines', 'SpokeLine', 'Polygons'):
            document.remove(fill.one(name))
        for group in tuple(fill.one('Regions').children()):
            group.detach()
        for format in ('asc', 'dip'):
            rebuilt = io.parse(io.serialize(document, format=format, report=ConversionReport()), report=ConversionReport())
            self.assertIsNotNone(rebuilt.one(FILL).child('Regions'))
            self.assertEqual(rebuilt.one(FILL+'/Regions').children(), [])

    def test_invalid_saved_labels_become_unavailable_without_changing_geometry(self):
        data = io.serialize(design(), format='asc', report=ConversionReport())
        raw = loads_bytes(data)
        raw.one('/Board/CopperPours/CopperPour/Regions_Counted').set_values('N')
        report = ConversionReport()
        document = io.parse(dumps(raw, preserve=False), report=report)
        self.assertIsNone(document.one(FILL).child('Regions'))
        self.assertTrue(document.one('/Board/CopperPours/CopperPour')['Poured'])
        self.assertEqual(document.one(FILL+'/Lines/Line')['X2'], 3)
        self.assertIsNone(document.one(FILL+'/Lines/Line')['Region'])
        self.assertIn('pour-regions-unavailable', {n.rule for n in report.infos})
        for format in ('asc', 'dip'):
            rebuilt = io.parse(io.serialize(document, format=format, report=ConversionReport()), report=ConversionReport())
            self.assertIsNone(rebuilt.one(FILL).child('Regions'))
            self.assertEqual(rebuilt.one(FILL+'/Polygons/Poly/Points/pt[1]')['X'], 1)

    def test_ascii_validity_is_independent_of_unassigned_members(self):
        document = design()
        raw = loads_bytes(io.serialize(document, format='asc', report=ConversionReport()))
        pour = raw.one('/Board/CopperPours/CopperPour')
        self.assertEqual(pour['Regions_Counted'], 'Y')
        self.assertEqual(pour.one('SpokeLine/pt').values[-1], -1)
        self.assertIsNone(pour.child('Regions'))
        rebuilt = io.parse(dumps(raw, preserve=False), report=ConversionReport())
        self.assertIsNotNone(rebuilt.one(FILL).child('Regions'))
        self.assertIsNone(rebuilt.one(FILL+'/SpokeLine/Line')['Region'])

    def test_unused_group_labels_report_loss_without_changing_the_source(self):
        document = design()
        document.one(FILL+'/Regions').add('Region', 19)
        before = dumps(document, preserve=False)
        for format in ('asc', 'dip'):
            report = ConversionReport()
            data = io.serialize(document, format=format, report=report)
            self.assertIn('unused-pour-regions', {notice.rule for notice in report.warnings})
            rebuilt = io.parse(data, report=ConversionReport())
            self.assertEqual([group['Number'] for group in rebuilt.select(FILL+'/Regions/Region')], [2, 7])
            self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
