"""Array edits produce current ASC counts in placed and cached records."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.schematic.formats.asc.projection import (project_pattern, project_component)
from lib.schematic.formats.asc.cache_projection import (project_cached_symbol, project_cached_pattern)
from lib.schematic.model.objects import (new_symbol, new_pattern)


def add_categories(owner, prefix):
    rows = owner.one(prefix+'_CategoryTypes')
    rows.set_values(0)
    rows.add(prefix+'_Type', 'Type', 'Subtype', 5, 6)


class CountedArraysTests(unittest.TestCase):
    def test_component_categories_use_current_rows_in_both_dialects(self):
        placed = new_symbol('Own', 'R1')
        cached = new_symbol('Own', 'R', placed=False)
        for part in (placed, cached):
            add_categories(part, 'Component')
        self.assertEqual(project_component(placed).one('Component_CategoryTypes').values, (1,))
        self.assertEqual(project_cached_symbol(cached).one('cl_CategoryTypes').values, (1,))
        self.assertEqual(placed.one('Component_CategoryTypes').values, (0,))
        self.assertEqual(cached.one('Component_CategoryTypes').values, (0,))

    def test_pattern_categories_names_and_segments_use_current_rows(self):
        pattern = new_pattern('Own footprint')
        add_categories(pattern, 'Pattern')
        pattern.one('PossibleNames').set_values(0)
        pattern.one('PossibleNames').add('PossibleName', 'Alternate')
        segments = pattern.one('PadMask_TopSegments')
        segments.set_values(0)
        segments.add('pt', 1, 2, 3, 4)
        placed, cached = project_pattern(pattern), project_cached_pattern(pattern)
        for name, cache_name in (('Pattern_CategoryTypes', 'cl_CategoryTypes'),
                                 ('PossibleNames', 'cl_PossibleNames'),
                                 ('PadMask_TopSegments', 'cl_PadMask_TopSegments')):
            self.assertEqual(placed.one(name).values, (1,))
            self.assertEqual(cached.one(cache_name).values, (1,))
            self.assertEqual(pattern.one(name).values, (0,))


if __name__ == '__main__':
    unittest.main()
