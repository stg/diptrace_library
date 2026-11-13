"""Export compaction preserves source records and follows hole identities."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib import AscExportContext, Element, ExportReport, ReferenceError, new_schematic
from lib.schematic.formats.export_view import (prepare_export)
from lib.schematic.model.pads import (empty_pad)
from lib.schematic.model.new import (fields)
from lib.schematic.model.objects import (new_symbol, new_pattern_shape, new_pin)
from lib.schematic.model.refs import (bind_schematic_references)


def design(*, cached=False, unresolved=False):
    source = new_schematic()
    part = source.one('/Schematic/Components').append(new_symbol('Symbol', 'U1'))
    pattern = part.one('Pattern')
    pattern.set_values('Footprint')
    holes = pattern.one('Holes')
    for index, active in ((1, False), (2, True), (3, True)):
        holes.insert(Element('Hole', active, False, index*3, 0, 3, 3, -1), index)
    for index, active in enumerate((False, True)):
        dimension = pattern.one('Dimensions').add('Dimension', index)
        fields(dimension, Enabled=active, Locked=False, Type=0,
               Connected1=2, Object1=0, SubObject1=1 if unresolved else 3, Point1=0,
               Connected2=-1, Object2=-1, SubObject2=-1, Point2=-1, Layer=0,
               X1=0, Y1=0, X2=1, Y2=0, XD=0, YD=1, ArrowSize=1, Units=0,
               VectorFont=True, FontName='', FontSize=6, FontScale=1, FontWidth=-1,
               ShowUnits=True, Angle=0, ExternalRadius=0, PointerMode=0,
               PointerText='active' if active else 'retained inactive content', Group=-1)
    if cached:
        slot = source.one('/Schematic/CacheLib/Slots').add('Slot', 0, '')
        slot.add('VariablePath', '')
        definition = slot.add('Definition', 0)
        definition.append(new_symbol('Cached symbol', '', placed=False))
        definition.append(pattern.clone())
    bind_schematic_references(source)
    return source, pattern


class PatternCompactionTests(unittest.TestCase):
    def test_xml_keeps_an_assignment_to_an_omitted_pad_unresolved(self):
        from lib.schematic.model.local_keys import missing_key
        for cached in (False, True):
            for declared_key in (None, 70):
                with self.subTest(cached=cached, declared_key=declared_key):
                    source = new_schematic()
                    part = source.one('/Schematic/Components').append(new_symbol('Device', 'U1'))
                    if cached:
                        slot = source.one('/Schematic/CacheLib/Slots').add('Slot', 0, '')
                        slot.add('VariablePath', '')
                        definition = slot.add('Definition', 0)
                        definition.append(new_symbol('Definition', '', placed=False))
                        definition.append(part.one('Pattern').clone())
                        source.remove(part)
                        part = definition.one('Part')
                        pattern = definition.one('Pattern')
                    else:
                        pattern = part.one('Pattern')
                    for index in (1, 2):
                        pad = empty_pad(index)
                        pad.set_values(index, 'same-label', '', index, 0)
                        pad['Number_New'] = -1 if index == 1 else index
                        pad['PadWidth_New'] = pad['PadHeight_New'] = 1
                        if declared_key is not None and index == 1:
                            pad.add('Id', declared_key)
                        pattern.one('Pads').insert(pad, index)
                    pins = part.one('Pins')
                    first, second = pins.append(new_pin(placed=not cached)), pins.append(new_pin(placed=not cached))
                    first['Number'], second['Number'] = 1, 2
                    bind_schematic_references(source)
                    before = source.to_dch_bytes(report=ExportReport())
                    report = ExportReport()
                    output = source.as_dchxml(report=report)
                    expected_key = 1 if declared_key is None else declared_key
                    pin_keys = [p['PadId'] for p in output.select('/Source/Library/Components/Component/Part/Pins/Pin')]
                    self.assertIn(expected_key, pin_keys)
                    self.assertTrue(any(n.rule == 'inactive-pad-assignment' for n in report.warnings))
                    rebuilt = output.as_schematic(report=ExportReport())
                    owner = (rebuilt.one('/Schematic/CacheLib/Slots/Slot/Definition/Part') if cached
                             else rebuilt.one('/Schematic/Components/Part'))
                    current = owner.select('Pins/Pin')
                    self.assertEqual(missing_key(current[0], 'PadId').values[1], expected_key)
                    self.assertEqual(current[0]['Number'], -1)
                    links = rebuilt.references.outgoing(owner, role='symbol-pin-pad')
                    self.assertEqual(len(links), 1)
                    self.assertEqual(links[0].target['StringNumber'], 'same-label')
                    self.assertIsNone(missing_key(current[1], 'PadId'))
                    self.assertEqual(source.to_dch_bytes(report=ExportReport()), before)
                    self.assertEqual(first['Number'], 1)
                    self.assertIsNone(missing_key(first, 'PadId'))
                    rebuilt.validate()
                    # Direct serialization uses the lazy projection rather
                    # than the editable syntax view exercised above.
                    from lib import parse, serialize
                    data = serialize(source, format='dchxml', report=ExportReport())
                    cycle = parse(data, report=ExportReport())
                    again = parse(serialize(cycle, format='dchxml', report=ExportReport()),
                                  report=ExportReport())
                    for current_document in (cycle, again):
                        owner = (current_document.one('/Schematic/CacheLib/Slots/Slot/Definition/Part') if cached
                                 else current_document.one('/Schematic/Components/Part'))
                        first_pin = owner.one('Pins/Pin[1]')
                        self.assertEqual(missing_key(first_pin, 'PadId').values[1], expected_key)
                        self.assertEqual(len(current_document.references.outgoing(owner, role='symbol-pin-pad')), 1)
                        current_document.validate()

    def test_cached_xml_pad_activity_is_independent_of_its_ordinal(self):
        source, placed = design(cached=True)
        source.remove(placed.parent)
        pattern = source.one('/Schematic/CacheLib/Slots/Slot/Definition/Pattern')
        pad = empty_pad(1)
        pad.annotations.clear()
        pad.set_values(1, 'retained', '', 0, 0)
        pad.set_field('Number_New', 0)
        pad.set_field('PadWidth_New', 1)
        pad.set_field('PadHeight_New', 1)
        pattern.one('Pads').insert(pad, 1)
        bind_schematic_references(source)
        output = source.as_dchxml(report=ExportReport())
        self.assertEqual([node.values[0] for node in output.select(
            '/Source/Library/Library/Patterns/Pattern/Pads/Pad/Number')], ['retained'])
        self.assertEqual(pad['Number_New'], 0)

    def test_xml_compacts_cached_pads_without_reactivating_them_on_import(self):
        source, placed = design(cached=True)
        source.remove(placed.parent)
        pattern = source.one('/Schematic/CacheLib/Slots/Slot/Definition/Pattern')
        pads = pattern.one('Pads')
        for index in (1, 2):
            pad = empty_pad(index)
            pad.annotations.clear()
            pad.set_values(index, 'inactive' if index == 1 else 'kept', '', index*3, 0)
            for name, value in dict(Number_New=-1 if index == 1 else index,
                                    PadShape_New=2, PadWidth_New=1, PadHeight_New=1, SurfacePad=True).items():
                pad.set_field(name, value)
            pads.insert(pad, index)
        dimension = pattern.one('Dimensions/Dimension[2]')
        for reference in source.references.outgoing(dimension, role='pattern-dimension-1'):
            source.references.discard(reference)
        dimension.set_field('Connected1', 0)
        dimension.set_field('SubObject1', 2)
        bind_schematic_references(source)
        before, report = source.to_dch_bytes(report=ExportReport()), ExportReport()
        rebuilt = source.as_dchxml(report=report).as_schematic()
        current = rebuilt.one('/Schematic/CacheLib/Slots/Slot/Definition/Pattern')
        kept = current.select('Pads/Pad')[1:-1]
        self.assertEqual([pad.values[1] for pad in kept], ['kept'])
        attached = current.one('Dimensions/Dimension')
        self.assertEqual(attached['SubObject1'], 1)
        self.assertIs(rebuilt.references.outgoing(attached, role='pattern-dimension-1')[0].target, kept[0])
        self.assertTrue(any(pattern.one('Pads/Pad[2]').path in notice.paths for notice in report.warnings))
        self.assertEqual(source.to_dch_bytes(report=ExportReport()), before)
        self.assertEqual([pad['Number_New'] for pad in pads.children('Pad')[1:-1]], [-1, 2])

    def test_xml_rejects_a_cached_attachment_to_an_omitted_inactive_hole(self):
        source, placed = design(cached=True, unresolved=True)
        source.remove(placed.parent)
        pattern = source.one('/Schematic/CacheLib/Slots/Slot/Definition/Pattern')
        original = [node.values for node in pattern.select('Holes/Hole')]
        with self.assertRaises(ReferenceError):
            source.as_dchxml(report=ExportReport())
        self.assertEqual([node.values for node in pattern.select('Holes/Hole')], original)

    def test_pad_and_drawing_compaction_follows_retained_dimension_targets(self):
        for mode in (0, 1):
            with self.subTest(mode=mode):
                source, pattern = design()
                pattern.set_field('Width', 30)
                pattern.set_field('Height', 30)
                pads = pattern.one('Pads')
                for index in (1, 2):
                    pad = empty_pad(index)
                    pad.annotations.clear()
                    pad.set_values(index, 'pad-'+str(index), '', index, 0)
                    pad.set_field('Number_New', -1 if index == 1 else index)
                    pads.insert(pad, index)
                shapes = pattern.one('Shapes')
                for index, kind in ((1, -1), (2, 0), (3, 1)):
                    shape = new_pattern_shape(index, kind=kind)
                    if kind == 1:
                        shape.one('Points_New').add('pt', 0, 0)
                        shape.one('Points_New').add('pt', 3, 0)
                    shapes.insert(shape, index)
                dimension = pattern.one('Dimensions/Dimension[2]')
                reference = source.references.outgoing(dimension, role='pattern-dimension-1')[0]
                source.references.discard(reference)
                dimension.set_field('Connected1', mode)
                dimension.set_field('SubObject1', 2 if mode == 0 else 3)
                bind_schematic_references(source)
                source.rebuild()
                before = source.to_dch_bytes(report=ExportReport())
                projected = source.as_asc(report=ExportReport()).as_schematic()
                pattern_view = projected.one('/Schematic/Components/Part/Pattern')
                self.assertEqual(len(pattern_view.select('Pads/Pad')), 3)
                self.assertEqual(len(pattern_view.select('Shapes/Shape')), 3)
                attached = pattern_view.one('Dimensions/Dimension')
                self.assertEqual(attached.scalar('SubObject1'), 1)
                target = projected.references.outgoing(attached, role='pattern-dimension-1')[0].target
                self.assertEqual(target.kind, 'Pad' if mode == 0 else 'Shape')
                if mode == 0:
                    self.assertEqual(target.values[1], 'pad-2')
                else:
                    self.assertEqual(target.scalar('Type'), 1)
                self.assertEqual(projected.references.issues, [])
                self.assertEqual(source.to_dch_bytes(report=ExportReport()), before)

    def test_compaction_rebuilds_attachments_without_changing_source_content(self):
        source, pattern = design()
        before = source.to_dch_bytes(report=ExportReport())
        report = ExportReport()
        output = source.as_asc(report=report)
        projected = output.one('/Schematic/Components/Part/Pattern')
        self.assertEqual(len(projected.select('Holes/Hole')), 4)
        self.assertEqual([node.values[0] for node in projected.select('Holes/Hole')], ['N', 'Y', 'Y', 'N'])
        attached = projected.one('Dimensions/Dimension')
        self.assertEqual(attached.scalar('SubObject1'), 2)
        self.assertEqual(attached.scalar('PointerText'), 'active')
        self.assertEqual([notice.rule for notice in report.warnings], ['inactive-records'])
        self.assertEqual(len(report.warnings[0].paths), 2)
        shared = output.as_schematic()
        self.assertEqual(shared.references.issues, [])
        dimension = shared.one('/Schematic/Components/Part/Pattern/Dimensions/Dimension')
        target = shared.references.outgoing(dimension, role='pattern-dimension-1')[0].target
        self.assertEqual(target.values[2:6], projected.select('Holes/Hole')[2].values[2:6])
        self.assertEqual(len(pattern.select('Holes/Hole')), 5)
        self.assertEqual(len(pattern.select('Dimensions/Dimension')), 2)
        self.assertEqual(pattern.one('Dimensions/Dimension[2]').scalar('SubObject1'), 3)
        self.assertEqual(source.to_dch_bytes(report=ExportReport()), before)

    def test_explicit_override_retains_inactive_records_across_asc_cycles(self):
        source, pattern = design()
        report = ExportReport()
        output = source.as_asc(context=AscExportContext(compact_inactive=False), report=report)
        self.assertEqual(report.warnings, [])
        for document in (output, output.as_schematic().as_asc(context=AscExportContext(compact_inactive=False), report=ExportReport())):
            projected = document.one('/Schematic/Components/Part/Pattern')
            self.assertEqual(len(projected.select('Holes/Hole')), 5)
            self.assertEqual(len(projected.select('Dimensions/Dimension')), 2)
            self.assertEqual(projected.one('Dimensions/Dimension[2]').scalar('SubObject1'), 3)

    def test_cached_definition_records_are_independent_of_placed_compaction(self):
        source, pattern = design(cached=True)
        view = prepare_export(source, materialize_markings=False, report=ExportReport())
        placed = view.one('/Schematic/Components/Part/Pattern')
        cached = view.one('/Schematic/CacheLib/Slots/Slot/Definition/Pattern')
        self.assertEqual((len(placed.select('Holes/Hole')), len(placed.select('Dimensions/Dimension'))), (4, 1))
        self.assertEqual((len(cached.select('Holes/Hole')), len(cached.select('Dimensions/Dimension'))), (5, 2))
        self.assertEqual(cached.one('Dimensions/Dimension[2]').scalar('SubObject1'), 3)

    def test_unresolved_retained_attachment_prevents_unsafe_hole_removal(self):
        source, pattern = design(unresolved=True)
        before = [node.values for node in pattern.select('Holes/Hole')]
        self.assertEqual(len(source.references.issues), 1)
        with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
            source.as_asc(report=ExportReport())
        self.assertEqual([node.values for node in pattern.select('Holes/Hole')], before)
        self.assertEqual(len(pattern.select('Dimensions/Dimension')), 2)


if __name__ == '__main__':
    unittest.main()
