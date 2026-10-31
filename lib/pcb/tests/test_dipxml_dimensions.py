"""Board XML dimensions resolve keys into the shared editable attachments."""
from decimal import Decimal
import unittest

from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.references import ReferenceError
from lib.pcb.model.dimensions import BOARD_ROLES
from lib.pcb.tests.test_dipxml_graphics import source, design


DIMENSIONS = '''<Dimensions>
  <Dimension Id="40" Type="Horizontal" Connected1="Board Outline" Point1="1"
      Connected2="Board Outline" Point2="2" ArrowSize="0.8" X1="1" Y1="2" X2="3" Y2="4" XD="5" YD="6"/>
  <Dimension Id="90" Connected1="Pad" Object1="8" SubObject1="17" Point1="0"
      Connected2="Net" Object2="7" SubObject2="91" Point2="1" Group="90"/>
  <Dimension Id="2" Connected1="Shape" Object1="23" Point1="2"
      Connected2="Plane" Object2="37" Point2="2" PointerMode="Comment"><PointerText>Note</PointerText></Dimension>
  <Dimension Id="3" Connected1="Pattern Shape" Object1="8" SubObject1="9" Point1="0"/>
</Dimensions>'''


def text():
    return source().replace('</Board>', DIMENSIONS+'</Board>')


def target(document, dimension, side=0):
    return document.references.outgoing(dimension, role=BOARD_ROLES[side])[0].target


class PcbXmlDimensionTests(unittest.TestCase):
    def test_source_keys_and_literal_vertices_bind_to_current_geometry(self):
        result = design(text())
        document, board = result.document, result.document.one('/Board')
        dims = board.select('Dimensions/Dimension')
        self.assertIs(target(document, dims[0]), board.one('Points/pt[2]'))
        self.assertIs(target(document, dims[0], 1), board.one('Points/pt[3]'))
        self.assertIs(target(document, dims[1]), result.rules.routing.core.pads[8, 1])
        self.assertEqual((dims[1]['Object1'], dims[1]['SubObject1']), (0, 1))
        self.assertIs(target(document, dims[1], 1), board.one('Nets/Net/Traces/Trace[1]/Points/Point[2]'))
        self.assertEqual((dims[1]['Object2'], dims[1]['SubObject2'], dims[1]['Point2']), (0, 0, 1))
        self.assertIs(target(document, dims[2]), result.drawings[23])
        self.assertIs(target(document, dims[2], 1), result.pours[37].one('Points/pt[3]'))
        self.assertIs(target(document, dims[3]), board.one('Components/Component/Pattern/Shapes/Shape/Points_New/pt[1]'))
        self.assertEqual((dims[2]['PointerMode'], dims[2]['PointerText']), (1, 'Note'))
        self.assertEqual((dims[0]['ArrowSize'], dims[0]['Y1'], dims[0]['YD']), (Decimal('2.4'), -6, -18))
        document.references.validate()

    def test_reordering_and_copying_retain_the_endpoint_identity(self):
        result = design(text())
        document = result.document
        dim = document.one('/Board/Dimensions/Dimension[1]')
        point = target(document, dim)
        point.move_to(point.parent, 0)
        self.assertIs(target(document, dim), point)
        self.assertEqual(dim['Point1'], 0)
        with self.assertRaises(ReferenceError):
            document.remove(point)
        clone = document.clone()
        copied = clone.one('/Board/Dimensions/Dimension[1]')
        self.assertIsNot(target(clone, copied), point)
        self.assertIs(target(clone, copied)._owner(), clone)
        clone.references.validate()

    def test_missing_target_keys_use_existing_loading_repairs_without_reinterpreting_positions(self):
        @import_diagnostics('dipxml')
        def read(value):
            return design(value).document
        # Key 0 happens to be a valid current component position, but it is not
        # the supplied component's XML key. It must not select that component.
        report = ConversionReport()
        altered = DIMENSIONS.replace('Object1="8" SubObject1="17"', 'Object1="0" SubObject1="17"')
        document = read(source().replace('</Board>', altered+'</Board>'), report=report)
        dim = document.one('/Board/Dimensions/Dimension[2]')
        self.assertEqual(dim['Connected1'], -1)
        self.assertFalse(document.references.outgoing(dim, role=BOARD_ROLES[0]))
        self.assertTrue(any(n.rule == 'dimension-attachment-normalization' for n in report.infos))

    def test_omitted_styles_and_earlier_arrow_units_have_distinct_loader_defaults(self):
        result = design(text())
        dim = result.document.one('/Board/Dimensions/Dimension[2]')
        self.assertEqual((dim['Type'], dim['Layer'], dim['ArrowSize']), (2, 13, 3))
        self.assertEqual((dim['FontSize'], dim['FontName'], dim['FontWidth']), (4, 'Tahoma', -2))
        self.assertFalse(dim['ShowUnits'])
        older = text().replace('Version="5.3.5.1"', 'Version="4.3.0.3"').replace('MinimumArea="4"', '')
        dim = design(older).document.one('/Board/Dimensions/Dimension[1]')
        self.assertEqual(dim['ArrowSize'], Decimal('.8'))


if __name__ == '__main__':
    unittest.main()
