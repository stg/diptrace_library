"""Visibility normalization uses explicit import context and current values."""
from types import SimpleNamespace
import unittest

from lib.common.model import Element
from lib.pcb.formats.assembly.graphic_colors import normalize_graphic_colors
from lib.pcb.formats.import_context import ImportContext
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.common.asc import dumps
from lib.pcb.tests.test_asc_graphics import fixture


def board(*, color=0, brush=0, font=0, enabled=True):
    root = Element('Board')
    shape = root.add('Shapes').add('Shape')
    for name, value in dict(Color=color, BrushColor=brush, FontColor=font, Enabled=enabled).items():
        shape.add(name, value)
    return SimpleNamespace(board=root), shape


class GraphicColorTests(unittest.TestCase):
    def test_default_black_canvas_has_visible_neutral_fallback(self):
        data, shape = board(brush=0x123456)
        normalize_graphic_colors(data, ImportContext())
        self.assertEqual((shape['Color'], shape['BrushColor'], shape['FontColor']), (0xC0C0C0, 0x123456, 0xC0C0C0))
        before = [(node.path, node.values) for node in data.board.walk(include_self=True)]
        normalize_graphic_colors(data, ImportContext())
        self.assertEqual([(node.path, node.values) for node in data.board.walk(include_self=True)], before)

    def test_other_backgrounds_use_complement_only_on_exact_matches(self):
        for background in (0xFFFFFF, 0x123456, 0xC0C0C0):
            with self.subTest(background=background):
                data, shape = board(color=background, brush=1, font=2)
                normalize_graphic_colors(data, ImportContext(background_color=background))
                self.assertEqual((shape['Color'], shape['BrushColor'], shape['FontColor']), (0xFFFFFF-background, 1, 2))

    def test_none_retains_authored_colors_and_inactive_records_are_ignored(self):
        data, shape = board()
        normalize_graphic_colors(data, ImportContext(background_color=None))
        self.assertEqual((shape['Color'], shape['BrushColor'], shape['FontColor']), (0, 0, 0))
        data, shape = board(enabled=False)
        normalize_graphic_colors(data, ImportContext())
        self.assertEqual((shape['Color'], shape['BrushColor'], shape['FontColor']), (0, 0, 0))

    def test_asc_uses_the_same_import_policy_before_binding(self):
        source = fixture()
        shape = source.one('/Board/Shapes/Shape')
        shape.add('Color', 0)
        shape.add('BrushColor', 1)
        shape.add('FontColor', 0)
        result = assemble_graphics(prepare_core(dumps(source, preserve=False)))
        shape = result.drawings[23]
        self.assertEqual((shape['Color'], shape['BrushColor'], shape['FontColor']), (0xC0C0C0, 1, 0xC0C0C0))

    def test_context_rejects_invalid_color_values(self):
        for value in (True, 'black', 0.0):
            with self.subTest(value=value), self.assertRaises(TypeError):
                ImportContext(background_color=value)
        for value in (-1, 0x1000000):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ImportContext(background_color=value)


if __name__ == '__main__':
    unittest.main()
