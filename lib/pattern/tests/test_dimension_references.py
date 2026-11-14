"""Local attachments keep their identities through ordinary data edits."""
import unittest
from unittest.mock import patch

from lib.common.references import ReferenceError
from lib.pattern.formats.libxml.read import parse
from lib.pattern.model import new_pattern
from lib.pattern.tests.test_libxml_read import XML
from lib.pattern.tests.comparison import snapshot


DIMENSIONS = '''<Holes><Hole Id="21" X="4" Y="2" Diam="2" HoleDiam="1"/></Holes>
<Dimensions>
<Dimension Type="Horizontal" Connected1="Pad" SubObject1="7" Point1="0"
    Connected2="Pad" SubObject2="17" Point2="0"/>
<Dimension Type="Free" Connected1="Shape" SubObject1="30" Point1="0"
    Connected2="Hole" SubObject2="21" Point2="0" Group="8"/>
</Dimensions>'''


def source():
    return XML.replace('</Pattern></Patterns>', DIMENSIONS+'</Pattern></Patterns>')


class PatternDimensionTests(unittest.TestCase):
    def test_calculated_text_extents_do_not_override_dimension_facts(self):
        original = parse(source())
        supplied = source().replace('<Dimension Type=',
            '<Dimension TextWidth="777" TextHeight="999" Type=')
        self.assertEqual(snapshot(original), snapshot(parse(supplied)))
        dimension = parse(supplied).one('/Library/Patterns/Pattern/Dimensions/Dimension[1]')
        self.assertIsNone(dimension.child('TextWidth'))
        self.assertIsNone(dimension.child('TextHeight'))

    def test_calculated_text_extents_still_require_numeric_values(self):
        for name in ('TextWidth', 'TextHeight'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                parse(source().replace('<Dimension Type=', f'<Dimension {name}="bad" Type='))

    def test_endpoints_follow_pad_order_without_a_rebuild(self):
        document = parse(source())
        pattern = document.one('/Library/Patterns/Pattern')
        dimension = pattern.one('Dimensions/Dimension[1]')
        first, second = pattern.one('Pads').children('Pad')
        first_link, = document.references.outgoing(dimension, role='pattern-dimension-1')
        self.assertIs(first, first_link.target)
        with patch.object(document.root, 'walk', side_effect=AssertionError('global scan')), \
                patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
            second.move_to(first.parent, index=0)
            self.assertEqual(2, dimension['SubObject1'])
            self.assertEqual(1, dimension['SubObject2'])
            self.assertIs(first, first_link.target)
        document.validate()

    def test_graphic_and_hole_attachments_are_owned_identities(self):
        document = parse(source())
        pattern = document.one('/Library/Patterns/Pattern')
        dimension = pattern.one('Dimensions/Dimension[2]')
        shape, hole = pattern.one('Shapes/Shape'), pattern.one('Holes/Hole')
        self.assertIs(shape, document.references.outgoing(dimension, role='pattern-dimension-1')[0].target)
        self.assertIs(hole, document.references.outgoing(dimension, role='pattern-dimension-2')[0].target)
        self.assertIs(pattern.one('Pattern_Groups/pt'), dimension['Group'])
        with self.assertRaises(ReferenceError):
            shape['Type'] = 8
        with self.assertRaises(ReferenceError):
            hole['Enabled'] = False
        self.assertEqual(1, shape['Type'])
        self.assertTrue(hole['Enabled'])
        document.validate()

    def test_attachment_cannot_silently_change_to_another_pattern(self):
        document = parse(source())
        pattern = document.one('/Library/Patterns/Pattern')
        another = new_pattern('Another')
        document.one('/Library/Patterns').append(another)
        dimension = pattern.one('Dimensions/Dimension[1]')
        with self.assertRaises(ReferenceError):
            dimension.move_to(another.one('Dimensions'))
        self.assertIs(pattern.one('Dimensions'), dimension.parent)
        document.validate()

    def test_copy_and_clone_retarget_to_their_own_members(self):
        document = parse(source())
        pattern = document.one('/Library/Patterns/Pattern')
        copied = document.copy(pattern, parent=pattern.parent)
        copied_dimension = copied.one('Dimensions/Dimension[2]')
        self.assertIs(copied.one('Holes/Hole'), document.references.outgoing(
            copied_dimension, role='pattern-dimension-2')[0].target)
        cloned = document.clone()
        for item in cloned.select('/Library/Patterns/Pattern'):
            dimension = item.one('Dimensions/Dimension[1]')
            self.assertIs(item.one('Pads/Pad[1]'), cloned.references.outgoing(
                dimension, role='pattern-dimension-1')[0].target)
        document.validate()
        cloned.validate()

    def test_missing_endpoint_remains_explicit_and_scope_guarded(self):
        document = parse(source().replace('SubObject1="7"', 'SubObject1="779"'))
        dimension = document.one('/Library/Patterns/Pattern/Dimensions/Dimension[1]')
        self.assertEqual(779, dimension['SubObject1'])
        self.assertEqual(1, len(document.references.issues))
        another = new_pattern('Another')
        document.one('/Library/Patterns').append(another)
        with self.assertRaises(ReferenceError):
            dimension.move_to(another.one('Dimensions'))
        document.validate()

    def test_missing_public_key_cannot_select_an_unrelated_compacted_pad(self):
        document = parse(source().replace('SubObject1="7"', 'SubObject1="1"'))
        dimension = document.one('/Library/Patterns/Pattern/Dimensions/Dimension[1]')
        self.assertEqual(1, dimension['SubObject1'])
        self.assertEqual([], document.references.outgoing(dimension, role='pattern-dimension-1'))
        self.assertEqual(1, len(document.references.issues))
        self.assertTrue(document.references.unresolved_slot(dimension.one('SubObject1')))
        copied = document.clone()
        self.assertEqual(1, len(copied.references.issues))
        copied.validate()
        document.validate()

    def test_terminal_polygon_endpoint_follows_its_vertex(self):
        terminal = '''<Terminals><Terminal Shape="Polygon" X="0" Y="0">
            <Points><Item X="0" Y="0"/><Item X="1" Y="0"/><Item X="0" Y="1"/></Points>
            </Terminal></Terminals>'''
        text = XML.replace('</PadStyle>', terminal+'</PadStyle>')
        text = text.replace('</Pattern></Patterns>', '''<Dimensions>
            <Dimension Type="Free" Connected1="Terminal" Object1="1" SubObject1="0" Point1="2"
                Connected2="None"/></Dimensions></Pattern></Patterns>''')
        document = parse(text)
        pattern = document.one('/Library/Patterns/Pattern')
        dimension = pattern.one('Dimensions/Dimension')
        terminal = pattern.one('Pads/Pad[1]/PadTerminal')
        point = terminal.one('ShapePoints/pt[2]')
        self.assertIs(point, document.references.outgoing(dimension, role='pattern-dimension-1')[0].target)
        point.move_to(point.parent, index=0)
        self.assertEqual(1, dimension['Point1'])
        with self.assertRaises(ReferenceError):
            terminal['Type'] = 0
        document.validate()


if __name__ == '__main__':
    unittest.main()
