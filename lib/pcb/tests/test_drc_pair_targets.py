"""Differential check snapshots reference current center-point identities."""
import unittest
from unittest.mock import patch

from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.references import Property, ReferenceError
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.tests.test_dipxml_electrical import prepared
from lib.pcb.tests.test_dipxml_pairs import source


ERRORS = '''<DesignErrors><DesignError Type="PhaseTolerance" X="1" Y="2" Value="0.3" Rule="0.4"
  ObjectType1="DiffPair" Object1="0" SubObject1="0" Point1="0" ObjectType2="-1"/>
</DesignErrors>'''


@import_diagnostics('dipxml')
def read(text):
    return assemble_graphics(prepared(text)).document


class DrcPairTargetTests(unittest.TestCase):
    def test_pair_segment_and_center_positions_select_current_identity_not_xml_pair_key(self):
        document = read(source().replace('</Board>', ERRORS+'</Board>'), report=ConversionReport())
        row = document.one('/Board/DesignErrors/DesignError')
        center = document.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint')
        self.assertIs(row['Target1'], center)
        self.assertEqual((row['Object1'], row['SubObject1'], row['Point1']), (0, 0, 0))
        for name in ('Object1', 'SubObject1', 'Point1'):
            self.assertIsNone(row.child(name))
        self.assertEqual((row['X'], row['Y']), (3, -6))
        document.references.validate()

    def test_reordering_retargeting_and_cloning_follow_center_identity_without_recalculation(self):
        document = read(source().replace('</Board>', ERRORS+'</Board>'), report=ConversionReport())
        row = document.one('/Board/DesignErrors/DesignError')
        center = row['Target1']
        observer = document.root.add('CenterIndex', -1)
        document.references.bind(observer, row, Property(observer, 'Point1'))
        with patch.object(document.root, 'walk', side_effect=AssertionError('global tree scan')), \
                patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
            copy = document.copy(center, index=0)
            self.assertEqual((row['Point1'], observer.values), (1, (1,)))
            row['Target1'] = copy
            self.assertEqual((row['Point1'], observer.values), (0, (0,)))
            copy['X'] = 90
            self.assertEqual((row['X'], row['Y']), (3, -6))
        clone = document.clone()
        cloned = clone.one('/Board/DesignErrors/DesignError')
        self.assertIsNot(cloned['Target1'], copy)
        with self.assertRaises(ReferenceError):
            cloned['Target1'] = copy
        document.references.validate()
        clone.references.validate()

    def test_unavailable_pair_positions_stay_explicit_until_repaired_or_cleared(self):
        text = source().replace('</Board>', ERRORS.replace(' Object1="0"', ' Object1="100"')+'</Board>')
        report = ConversionReport()
        document = read(text, report=report)
        row = document.one('/Board/DesignErrors/DesignError')
        self.assertEqual(row.one('UnresolvedTarget1').values, (100, 0, 0, -1))
        self.assertTrue(report.warnings)
        with self.assertRaises(ReferenceError):
            row['Target1']
        center = document.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint')
        row['Target1'] = center
        self.assertFalse(document.references.issues)
        with self.assertRaises(ReferenceError):
            row['ObjectType1'] = 4
        self.assertIs(row['Target1'], center)
        row['Target1'] = None
        self.assertEqual((row['Object1'], row['SubObject1'], row['Point1']), (-1, -1, -1))
        document.references.validate()


if __name__ == '__main__':
    unittest.main()
