"""One editable mode per pad mask/paste face across all schematic adapters."""
import unittest

from lib import ExportReport,parse,parse_asc
from lib.schematic.model.pad_data import (MASK_FIELDS)
from lib.tests.test_pad_orientation import sample,placed_pad


class PadMaskStateTests(unittest.TestCase):
    def test_all_formats_keep_current_modes_after_edits(self):
        source,pad=sample(0)
        for state in range(4):
            for name in MASK_FIELDS:pad.set_field(name,state)
            pad.set_field('CustomSwell_New',.25)
            for format in ('dch','asc','dchxml'):
                with self.subTest(state=state,format=format):
                    loaded=parse(getattr(source,'to_'+format+'_bytes')(report=ExportReport()),format=format)
                    current=placed_pad(loaded)
                    for name in MASK_FIELDS:
                        self.assertEqual(current.one(name).values,(state,))
                        self.assertFalse(current.select('StoredData/'+name))
                    self.assertEqual(float(current.scalar('CustomSwell_New')),.25)
                    for name in MASK_FIELDS:self.assertEqual(pad.scalar(name),state)

    def test_ascii_compatibility_prefix_is_generated_from_the_current_mode(self):
        source,pad=sample(0)
        for state,expected in ((0,('N',0,0)),(1,('N',1,1)),(2,('Y',2)),(3,('N',0,3))):
            with self.subTest(state=state):
                pad.set_field('DisableTopMask',state)
                raw=parse_asc(source.to_asc_bytes().decode('cp1252'))
                field=raw.one('/Schematic/Components/Part/Pattern/Pads/Pad/DisableTopMask')
                self.assertEqual(field.values,expected)
                self.assertEqual(pad.one('DisableTopMask').values,(state,))

    def test_latest_ascii_mode_replaces_a_contradictory_earlier_prefix(self):
        source,_=sample(0)
        raw=parse_asc(source.to_asc_bytes().decode('cp1252'))
        raw.one('/Schematic/Components/Part/Pattern/Pads/Pad/DisableTopMask').set_values('Y',2,3)
        current=raw.as_schematic()
        self.assertEqual(placed_pad(current).one('DisableTopMask').values,(3,))
        loaded=parse(current.to_dch_bytes(),format='dch')
        self.assertEqual(placed_pad(loaded).one('DisableTopMask').values,(3,))

    def test_writers_reject_competing_modes_in_one_current_property(self):
        source,pad=sample(0)
        pad.set_field('DisableTopMask',False,0,3)
        for format in ('dch','asc','dchxml'):
            with self.subTest(format=format):
                with self.assertRaisesRegex(ValueError,'DisableTopMask requires one scalar value'):
                    getattr(source,'to_'+format+'_bytes')()


if __name__=='__main__':
    unittest.main()
