"""XML retains dimension geometry when calculated markings have no drawing key."""
import unittest
from xml.etree import ElementTree

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import DIPXML
from lib.pcb.tests.test_dipxml_library import read, source


COMPONENT = '/Board/Components/Component'


def design(*, kind='Text', generated=True, side='Top', attached_side='1'):
    root = ElementTree.fromstring(source())
    pattern = root.find('Library/Library/Patterns/Pattern')
    shape = pattern.find('Shapes/Shape')
    shape.set('Type', kind)
    if kind == 'Text':
        ElementTree.SubElement(ElementTree.SubElement(shape, 'Lines'), 'Item').text = 'marking'
    dimensions = ElementTree.SubElement(pattern, 'Dimensions')
    other = '2' if attached_side == '1' else '1'
    local = dict(X1='1', Y1='2', X2='3', Y2='4', XD='5', YD='6')
    local.update({'Connected'+attached_side: 'Shape', 'SubObject'+attached_side: '9',
                  'Point'+attached_side: '0', 'Connected'+other: 'None'})
    ElementTree.SubElement(dimensions, 'Dimension', local)
    component = root.find('Board/Components/Component')
    component.set('Side', side)
    component.set('Angle', '0')
    dimensions = ElementTree.SubElement(root.find('Board'), 'Dimensions')
    board = dict(X1='7', Y1='8', X2='9', Y2='10', XD='11', YD='12')
    board.update({'Connected'+attached_side: 'Pattern Shape', 'Object'+attached_side: component.get('Id'),
                  'SubObject'+attached_side: '9', 'Point'+attached_side: '0', 'Connected'+other: 'None'})
    ElementTree.SubElement(dimensions, 'Dimension', board)
    document = read(ElementTree.tostring(root), report=ConversionReport())
    document.one(COMPONENT+'/Pattern/Shapes/Shape')['MarkingGenerated'] = generated
    return document


def geometry(document):
    component = document.one(COMPONENT)
    # These fixtures use zero-angle placement. Compare board coordinates so a
    # receiving format may choose a different local footprint origin.
    assert component['Angle'] == 0
    local = component.one('Pattern/Dimensions/Dimension')
    board = document.one('/Board/Dimensions/Dimension')
    return (tuple(board[axis+suffix] for suffix in ('1', '2', 'D') for axis in ('X', 'Y')),
            tuple(component[axis]+local[axis+suffix]
                  for suffix in ('1', '2', 'D') for axis in ('X', 'Y')))


class XmlMarkingAttachmentTests(unittest.TestCase):
    def test_board_and_placed_dimensions_warn_and_become_free_without_moving(self):
        for side, endpoint in (('Top', '1'), ('Top', '2'), ('Bottom', '1'), ('Bottom', '2')):
            document = design(side=side, attached_side=endpoint)
            expected = geometry(document)
            before = model_text(document, preserve=False)
            for version in DIPXML.write_versions:
                with self.subTest(side=side, endpoint=endpoint, version=version):
                    report = ConversionReport()
                    data = io.serialize(document, format='dipxml', version=version, report=report)
                    current = io.parse(data, report=ConversionReport())
                    for path, role in (('/Board/Dimensions/Dimension', 'board-dimension-'+endpoint),
                                       (COMPONENT+'/Pattern/Dimensions/Dimension', 'pattern-dimension-'+endpoint)):
                        dimension = current.one(path)
                        self.assertEqual(dimension['Connected'+endpoint], -1)
                        self.assertFalse(current.references.outgoing(dimension, role=role))
                    self.assertEqual(geometry(current), expected)
                    notices = [notice for notice in report.warnings if notice.rule == 'dimension-marking-attachment']
                    self.assertEqual(len(notices), 2)
                    self.assertEqual(report.errors, [])
                    self.assertEqual(model_text(document, preserve=False), before)
                    current.references.validate()

    def test_binary_and_asc_keep_the_saved_marking_attachments(self):
        document = design()
        for format in ('dip', 'asc'):
            with self.subTest(format=format):
                report = ConversionReport()
                current = io.parse(io.serialize(document, format=format, report=report), report=ConversionReport())
                # Export may complete other calculated captions from the marking
                # settings. The existing selected drawing retains its identity.
                shape = current.one(COMPONENT+'/Pattern/Shapes/Shape[1]')
                self.assertTrue(shape['MarkingGenerated'])
                self.assertEqual(shape['TextShow'], 0)
                self.assertEqual(shape.one('TextLine/pt').values, ('marking',))
                for path, role in (('/Board/Dimensions/Dimension', 'board-dimension-1'),
                                   (COMPONENT+'/Pattern/Dimensions/Dimension', 'pattern-dimension-1')):
                    dimension = current.one(path)
                    self.assertEqual(dimension['Connected1'], 1)
                    self.assertIs(current.references.outgoing(dimension, role=role)[0].target, shape)
                self.assertFalse(any(n.rule == 'dimension-marking-attachment' for n in report.notices))

    def test_literal_text_and_flagged_nontext_keep_their_attachments(self):
        for kind, generated in (('Text', False), ('Line', True)):
            document = design(kind=kind, generated=generated)
            for version in DIPXML.write_versions:
                with self.subTest(kind=kind, version=version):
                    report = ConversionReport()
                    current = io.parse(io.serialize(document, format='dipxml', version=version, report=report),
                                       report=ConversionReport())
                    shape = current.one(COMPONENT+'/Pattern/Shapes/Shape')
                    for path, role in (('/Board/Dimensions/Dimension', 'board-dimension-1'),
                                       (COMPONENT+'/Pattern/Dimensions/Dimension', 'pattern-dimension-1')):
                        dimension = current.one(path)
                        self.assertEqual(dimension['Connected1'], 1)
                        self.assertIs(current.references.outgoing(dimension, role=role)[0].target, shape)
                    self.assertFalse(any(n.rule == 'dimension-marking-attachment' for n in report.notices))
                    self.assertEqual(report.errors, [])


if __name__ == '__main__':
    unittest.main()
