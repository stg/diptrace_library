"""Local missing references survive keyed output and adapt positional output."""
import unittest
import xml.etree.ElementTree as ET

from lib.common.conversion import ConversionReport
from lib.pattern.formats.libxml.read import parse
from lib.pattern.formats.libxml.write import dumps
from lib.pattern.formats.lib.read import parse as read_binary
from lib.pattern.formats.lib.write import encode
from lib.pattern.formats.asc.read import parse as read_asc
from lib.pattern.formats.asc.write import dumps as dumps_asc
from .test_dimension_references import source
from lib.pattern.model import new_internal_connection


def unavailable():
    return parse(source().replace('SubObject1="7"', 'SubObject1="1"')
                 .replace('PadId="17"', 'PadId="1"').replace('Group="8"', 'Group="1"'))


def content(document):
    return tuple((node.path, node.values) for node in document.root.walk(include_self=True))


class PatternUnresolvedOutputTests(unittest.TestCase):
    def test_electrical_connections_have_a_known_projection_loss(self):
        document = parse(source())
        pattern = document.one('/Library/Patterns/Pattern')
        pair = pattern.one('InternalConnections').append(new_internal_connection())
        pair['Pad1'], pair['Pad2'] = pattern.select('Pads/Pad')
        before = content(document)
        for write, read in ((encode, read_binary), (dumps_asc, read_asc), (dumps, parse)):
            report = ConversionReport()
            result = read(write(document, report=report))
            self.assertEqual([], result.select('/Library/Patterns/Pattern/InternalConnections/IntCon'))
            self.assertIn('pattern-internal-connections', {notice.rule for notice in report.warnings})
            self.assertEqual(before, content(document))
            self.assertEqual([], result.references.issues)
        pair.add('UnknownData', 42)
        for write in (encode, dumps_asc, dumps):
            with self.assertRaises(NotImplementedError):
                write(document, report=ConversionReport())

    def test_keyed_output_reserves_missing_keys_in_each_local_scope(self):
        document = unavailable()
        before = content(document)
        count = len(document.references.issues)
        self.assertEqual(5, count)
        result = document
        for _ in range(3):
            report = ConversionReport()
            text = dumps(result, report=report)
            root = ET.fromstring(text)
            self.assertNotIn('1', [pad.get('Id') for pad in root.findall('Patterns/Pattern/Pads/Pad')])
            result = parse(text)
            pattern = result.one('/Library/Patterns/Pattern')
            self.assertEqual(1, pattern.one('Shapes/Shape')['UnresolvedPadId'])
            dimension = pattern.select('Dimensions/Dimension')[0]
            self.assertEqual(1, dimension['SubObject1'])
            self.assertEqual([], result.references.outgoing(dimension, role='pattern-dimension-1'))
            self.assertEqual(count, len(result.references.issues))
            self.assertIn('unresolved-local-reference', {notice.rule for notice in report.warnings})
            result.validate()
        self.assertEqual(before, content(document))

    def test_positional_output_unassigns_only_the_missing_endpoint(self):
        document = unavailable()
        before = content(document)
        for write, read in ((encode, read_binary), (dumps_asc, read_asc)):
            report = ConversionReport()
            result = read(write(document, report=report))
            dimension = result.select('/Library/Patterns/Pattern/Dimensions/Dimension')[0]
            self.assertEqual(-1, dimension['Connected1'])
            self.assertEqual((0, 2), (dimension['Connected2'], dimension['SubObject2']))
            self.assertEqual([], result.references.issues)
            self.assertEqual(before, content(document))

    def test_missing_vertex_keeps_its_resolved_shape_key(self):
        text = source().replace('Type="Line"', 'Type="Polyline"').replace('Point1="0"\n    Connected2="Hole"',
            'Point1="99"\n    Connected2="Hole"')
        document = parse(text)
        self.assertEqual(1, len(document.references.issues))
        for _ in range(3):
            report = ConversionReport()
            text = dumps(document, report=report)
            root = ET.fromstring(text)
            shape = root.find('Patterns/Pattern/Shapes/Shape')
            dimension = root.findall('Patterns/Pattern/Dimensions/Dimension')[1]
            self.assertEqual(shape.get('Id'), dimension.get('SubObject1'))
            self.assertEqual('99', dimension.get('Point1'))
            document = parse(text)
            self.assertEqual(1, len(document.references.issues))
            document.validate()


if __name__ == '__main__':
    unittest.main()
