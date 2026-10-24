"""Dimension identities follow local edits; unresolved source facts survive."""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib import Element, new_schematic, parse_dch, parse_dchxml, ExportReport, ReferenceError
from lib.schematic.model.pads import (empty_pad)
from lib.schematic.model.new import (fields)
from lib.schematic.model.objects import (new_symbol, new_pattern, new_pattern_shape)
from lib.schematic.model.refs import (bind_schematic_references)


SELECTORS = dict(Connected1='Terminal', Object1='0', SubObject1='42', Point1='8',
                 Connected2='Pad', Object2='2', SubObject2='654', Point2='3')
VALUES = (3, 0, 42, 8, 0, 2, 654, 3)


def source_document(*, populated=False, selector_overrides=None):
    source = new_schematic()
    slot = source.one('/Schematic/CacheLib/Slots').add('Slot', 0, '')
    slot.add('VariablePath', '')
    definition = slot.add('Definition', 0)
    definition.append(new_symbol('Symbol', 'X', placed=False))
    footprint = definition.append(new_pattern('Footprint'))
    if populated:
        pads = footprint.one('Pads')
        for index, key in ((1, 42), (2, 7)):
            pad = empty_pad(index)
            pad.annotations.clear()
            pad.set_values(index, str(index), '', index, 0)
            pad.set_field('Number_New', index)
            pad.add('Id', key)
            for number, kind in enumerate((1, 3)):
                terminal = pad.add('PadTerminal', number)
                fields(terminal, Type=kind, X=0, Y=0, Angle=0, ShapeWidth=1, ShapeHeight=1, ShapeCorner=0)
                points = terminal.add('ShapePoints')
                if kind == 3:
                    for x, y in ((0, 0), (1, 0), (0, 1)):
                        points.add('pt', x, y)
            pads.insert(pad, index)
        pads.children('Pad')[-1].set_values(3, '', '', 0, 0)
        for index, kind in ((1, 8), (2, 9)):
            shape = new_pattern_shape(index, kind=kind)
            for x, y in ((0, 0), (1, 0), (0, 1)):
                shape.one('Points_New').add('pt', x, y)
            footprint.one('Shapes').insert(shape, index)
    bind_schematic_references(source)
    root = ET.fromstring(source.to_dchxml_bytes(report=ExportReport()))
    pattern = root.find('Library/Library/Patterns/Pattern')
    selectors = dict(SELECTORS)
    if populated:
        selectors.update(Object1='1', SubObject1='1', Point1='2', SubObject2='42')
    selectors.update({name: str(value) for name, value in (selector_overrides or {}).items()})
    ET.SubElement(ET.SubElement(pattern, 'Dimensions'), 'Dimension', selectors)
    return parse_dchxml(ET.tostring(root))


def dimension(document):
    return document.one('/Schematic/CacheLib/Slots/Slot/Definition/Pattern/Dimensions/Dimension')


def selectors(node):
    return tuple(node.scalar(name) for name in SELECTORS)


class DimensionSelectorTests(unittest.TestCase):
    def test_shared_import_and_all_exports_retain_unresolved_selectors(self):
        raw = source_document()
        original = raw.to_dchxml_bytes()
        shared = raw.as_schematic()
        self.assertEqual(selectors(dimension(shared)), VALUES)
        self.assertEqual(len(shared.references.issues), 2)
        self.assertTrue(all(issue.message.startswith('pattern-dimension-')
                            for issue in shared.references.issues))
        outputs = (parse_dch(shared.to_dch_bytes(report=ExportReport())),
                   shared.as_asc(report=ExportReport()).as_schematic(),
                   shared.as_dchxml(report=ExportReport()).as_schematic())
        for output in outputs:
            self.assertEqual(selectors(dimension(output)), VALUES)
            self.assertEqual(len(output.references.issues), 2)
        self.assertEqual(raw.to_dchxml_bytes(), original)
        self.assertFalse(shared.root.changed)

    def test_scalar_edits_keep_the_literal_attachment_state(self):
        shared = source_document().as_schematic()
        dimension(shared).set_field('PointerText', 'Investigate attachment')
        output = shared.as_dchxml(report=ExportReport()).as_schematic()
        self.assertEqual(dimension(output).scalar('PointerText'), 'Investigate attachment')
        self.assertEqual(selectors(dimension(output)), VALUES)

    def test_unresolved_local_attachment_guards_only_its_own_collection(self):
        shared = source_document().as_schematic()
        pattern = dimension(shared).parent.parent
        pattern.one('Shapes').append(new_pattern_shape(0))
        shared.rebuild()
        with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
            pattern.select('Pads/Pad')[1].detach()
        shared.validate()
        self.assertEqual(selectors(dimension(shared)), VALUES)

    def test_terminal_and_polygon_point_follow_nested_reordering(self):
        shared = source_document(populated=True).as_schematic()
        attached = dimension(shared)
        pattern = attached.parent.parent
        pad = pattern.select('Pads/Pad')[1]
        terminal = pad.children('PadTerminal')[1]
        point = terminal.select('ShapePoints/pt')[1]
        self.assertEqual(shared.references.issues, [])
        first = shared.references.outgoing(attached, role='pattern-dimension-1')[0]
        second = shared.references.outgoing(attached, role='pattern-dimension-2')[0]
        self.assertIs(first.target, point)
        self.assertIs(second.target, pad)
        pad.move_to(pad.parent, 2)
        terminal.move_to(pad, pad.children().index(pad.children('PadTerminal')[0]))
        point.move_to(point.parent, 2)
        shared.rebuild()
        self.assertEqual(selectors(attached), (3, 2, 0, 3, 0, 2, 2, 3))
        before = shared.to_dch_bytes(report=ExportReport())
        for output in (parse_dch(before), shared.as_asc(report=ExportReport()).as_schematic(),
                       shared.as_dchxml(report=ExportReport()).as_schematic()):
            copied = dimension(output)
            self.assertEqual(selectors(copied), selectors(attached))
            self.assertEqual(output.references.issues, [])
            linked = output.references.outgoing(copied, role='pattern-dimension-1')[0].target
            self.assertEqual(linked.values, point.values)
            self.assertEqual(linked.parent.parent.scalar('Type'), 3)
        self.assertEqual(shared.to_dch_bytes(report=ExportReport()), before)

    def test_center_and_nonpolygon_anchors_bind_the_terminal(self):
        for terminal, point in ((0, 7), (1, 0), (1, -1)):
            with self.subTest(terminal=terminal, point=point):
                shared = source_document(populated=True, selector_overrides={
                    'SubObject1': terminal, 'Point1': point}).as_schematic()
                attached = dimension(shared)
                link = shared.references.outgoing(attached, role='pattern-dimension-1')[0]
                self.assertEqual(link.target.kind, 'PadTerminal')
                self.assertEqual(shared.references.issues, [])

    def test_reserved_pad_and_missing_polygon_point_stay_unresolved(self):
        for owner, point in ((0, 1), (3, 1), (1, 4)):
            with self.subTest(owner=owner, point=point):
                shared = source_document(populated=True, selector_overrides={
                    'Object1': owner, 'Point1': point}).as_schematic()
                self.assertEqual(len(shared.references.issues), 1)
                self.assertEqual(dimension(shared).scalar('Object1'), owner)
                self.assertEqual(dimension(shared).scalar('Point1'), point)
                self.assertFalse(shared.root.changed)

    def test_terminal_reference_cannot_move_to_another_pattern(self):
        shared = source_document(populated=True).as_schematic()
        attached = dimension(shared)
        pattern = attached.parent.parent
        other = pattern.clone()
        shared.one('/Schematic/CacheLib').add('Patterns').append(other)
        bind_schematic_references(shared)
        target = other.select('Pads/Pad')[1].children('PadTerminal')[1].select('ShapePoints/pt')[0]
        link = shared.references.outgoing(attached, role='pattern-dimension-1')[0]
        with self.assertRaisesRegex(ReferenceError, 'outside its local footprint'):
            shared.references.retarget(link, target)
        shared.validate()

    def test_polyline_anchors_follow_zero_based_point_identities(self):
        shared = source_document(populated=True, selector_overrides={
            'Connected2': 'Shape', 'SubObject2': 1, 'Point2': 0}).as_schematic()
        attached = dimension(shared)
        link = shared.references.outgoing(attached, role='pattern-dimension-2')[0]
        point, shape = link.target, link.target.parent.parent
        self.assertEqual(point.kind, 'pt')
        point.move_to(point.parent, 2)
        shape.move_to(shape.parent, 2)
        shared.rebuild()
        self.assertEqual((attached.scalar('SubObject2'), attached.scalar('Point2')), (2, 2))
        for output in (parse_dch(shared.to_dch_bytes(report=ExportReport())),
                       shared.as_asc(report=ExportReport()).as_schematic(),
                       shared.as_dchxml(report=ExportReport()).as_schematic()):
            copied = dimension(output)
            self.assertEqual(output.references.issues, [])
            target = output.references.outgoing(copied, role='pattern-dimension-2')[0].target
            for actual, expected in zip(target.values, point.values):
                self.assertAlmostEqual(actual, expected, places=12)
            self.assertEqual(copied.scalar('Point2'), 2)

    def test_source_view_reorders_points_and_scopes_unresolved_terminals(self):
        raw = source_document(populated=True, selector_overrides={
            'Connected2': 'Shape', 'SubObject2': 1, 'Point2': 0})
        attached = raw.select('//Dimension')[0]
        link = raw.references.outgoing(attached, role='xml-dimension-2')[0]
        point = link.target
        self.assertEqual(point.kind, 'Item')
        point.move_to(point.parent, 2)
        raw.rebuild()
        self.assertEqual(attached.scalar('Point2'), 2)
        self.assertEqual(len(raw.references.issues), 1)
        self.assertEqual(dimension(raw.as_schematic()).scalar('Point2'), 2)
        style = raw.references.issues[0].collections[1]
        terminals = style.one('Terminals')
        with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
            terminals.children('Terminal')[0].move_to(terminals, 1)
        raw.validate()

    def test_source_point_vocabulary_accepts_both_supported_xml_versions(self):
        raw = source_document(populated=True, selector_overrides={
            'Connected2': 'Shape', 'SubObject2': 1, 'Point2': 0})
        shared = raw.as_schematic()
        for version, kind in ((46, 'Item'), (48, 'Point')):
            with self.subTest(version=version):
                source = shared.as_dchxml(version=version, report=ExportReport())
                attached = source.select('//Dimension')[0]
                link = source.references.outgoing(attached, role='xml-dimension-2')[0]
                self.assertEqual(link.target.kind, kind)
                link.target.move_to(link.target.parent, 1)
                source.rebuild()
                self.assertEqual(attached.scalar('Point2'), 1)

    def test_unattached_source_selector_has_no_reference_issue(self):
        raw = source_document(populated=True, selector_overrides={
            'Connected1': '-1', 'Connected2': '-1'})
        self.assertEqual(raw.references.issues, [])
        self.assertEqual(raw.as_schematic().references.issues, [])


if __name__ == '__main__':
    unittest.main()
