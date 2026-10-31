"""Physical template compaction retains authored source data and live references."""
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.common.footprint_objects import new_pattern_drawing
from lib.common.references import ReferenceError
from lib.common.schema import MISSING
from lib.common.structural_edits import assembly
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import DIPXML
from lib.pcb.formats.export_view import prepare_export
from lib.pcb.tests import test_xml_pattern_output as templates


PATHS = (templates.PATH, '/Board/Components/Component[1]/Pattern')


def blank_drawing(pattern):
    # Typed attachment chooses the cached or placed schema. Only genuinely
    # shared writable drawing defaults come from the document-free constructor.
    prototype = new_pattern_drawing()
    drawing = pattern.one('Shapes').add('Shape')
    for name, field in drawing.schema.fields.items():
        if field.getter is None and prototype.child(name) is not None:
            drawing[name] = prototype[name]
    for name in ('TextLine', 'Points_New'):
        if drawing.child(name) is None:
            drawing.add(name)
    drawing.move_to(drawing.parent, 0)
    return drawing


def edited():
    document = templates.design()
    expected = {}
    for path in PATHS:
        pattern = document.one(path)
        expected[path] = tuple(len(pattern.select(query)) for query in
                               ('Shapes/Shape', 'Holes/Hole', 'Dimensions/Dimension'))
        # The empty slot and authored dormant geometry have different reporting
        # needs, despite both using Type 0 for physical drawings.
        blank_drawing(pattern)
        dormant = blank_drawing(pattern)
        dormant.one('TextLine').add('pt', 'Dormant outline')
        for point in ((1, 2), (3, 4)):
            dormant.one('Points_New').add('pt', *point)
        hole = pattern.one('Holes').add('Hole')
        for name, value in dict(Enabled=False, Locked=False, X=1, Y=2, Diam=3, HoleDiam=1).items():
            hole[name] = value
        if hole.schema.fields['Group'].getter is None:
            hole['Group'] = -1
        dimension = pattern.one('Dimensions').add('Dimension')
        for name, field in dimension.schema.fields.items():
            if field.required and field.getter is None:
                value = field.default
                if value is MISSING:
                    value = {'boolean': False, 'integer': 0, 'number': 0, 'text': ''}[field.kind]
                    if name.startswith('Connected'):
                        value = -1
                dimension[name] = value
        dimension['Enabled'] = False
    document.one(templates.PATH)['Name_Description'] = 'Independent template description'
    document.validate()
    return document, expected


class InactivePatternTests(unittest.TestCase):
    def test_every_xml_profile_compacts_cached_and_placed_physical_records(self):
        document, expected = edited()
        before = dumps(document, preserve=False)
        for version in DIPXML.write_versions:
            with self.subTest(version=version):
                report = ConversionReport()
                current = io.parse(io.serialize(document, format='dipxml', version=version,
                                   report=report), report=ConversionReport())
                for path, counts in expected.items():
                    pattern = current.one(path)
                    self.assertEqual(tuple(len(pattern.select(query)) for query in
                        ('Shapes/Shape', 'Holes/Hole', 'Dimensions/Dimension')), counts)
                self.assertEqual(current.one(templates.PATH)['Name_Description'],
                                 'Independent template description')
                for rule, count, severity in (('inactive-library-records', 3, 'warning'),
                        ('inactive-records', 3, 'warning'), ('inactive-empty-drawings', 2, 'info')):
                    notices = [n for n in report.notices if n.rule == rule]
                    self.assertEqual(sum(len(n.paths) for n in notices), count)
                    self.assertEqual({n.severity for n in notices}, {severity})
                self.assertEqual(report.errors, [])
                current.validate()
                repeated = io.parse(io.serialize(current, format='dipxml', version=version,
                                    report=ConversionReport()), report=ConversionReport())
                self.assertEqual(dumps(current, preserve=False), dumps(repeated, preserve=False))
                self.assertEqual(dumps(document, preserve=False), before)

    def test_live_dimensions_follow_surviving_members_after_compaction(self):
        document, _ = edited()
        for path in PATHS:
            dimension = document.one(path + '/Dimensions/Dimension[1]')
            target = document.references.outgoing(dimension)
            self.assertTrue(target)
        current = io.parse(io.serialize(document, format='dipxml', report=ConversionReport()),
                           report=ConversionReport())
        for path in PATHS:
            dimension = current.one(path + '/Dimensions/Dimension')
            targets = [r.target for r in current.references.outgoing(dimension)]
            self.assertIn(current.one(path + '/Pads/Pad[1]'), targets)
            self.assertIn(current.one(path + '/Holes/Hole'), targets)

    def test_other_format_views_keep_their_representable_inactive_geometry(self):
        document, _ = edited()
        before = dumps(document, preserve=False)
        for destination in ('dip', 'asc'):
            view, _ = prepare_export(document, destination=destination, report=ConversionReport())
            for path in PATHS:
                pattern = view.one(path)
                self.assertEqual(len([r for r in pattern.select('Shapes/Shape') if r['Type'] == 0]), 2)
                self.assertEqual(len([r for r in pattern.select('Holes/Hole') if not r['Enabled']]), 1)
                self.assertEqual(len([r for r in pattern.select('Dimensions/Dimension') if not r['Enabled']]), 1)
        self.assertEqual(dumps(document, preserve=False), before)

    def test_retained_dimension_cannot_lose_its_hole_target_silently(self):
        document = templates.design()
        with assembly(document):
            document.one(templates.PATH + '/Holes/Hole')['Enabled'] = False
        before, report = dumps(document, preserve=False), ConversionReport()
        with self.assertRaises(ReferenceError):
            io.serialize(document, format='dipxml', report=report)
        self.assertTrue(report.errors)
        self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
