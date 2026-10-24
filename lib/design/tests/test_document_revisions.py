"""Recent version gates preserve one editable fact per setting across adapters."""
from decimal import Decimal
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.design import new_schematic, parse_dch, parse_dchxml, ConversionReport, Element
from lib.design.schematic_new import fields
from lib.design.schematic_objects import (new_symbol, new_pin, new_pattern,
    new_symbol_shape, new_pattern_shape, new_schematic_shape)
from lib.design.schematic_refs import bind_schematic_references
from lib.design.schematic_fonts import all_fonts
from lib.design.simulation import OPTION_FIELDS
from lib.design.vector_text import builtin_vector_metrics


def text(shape, kind):
    shape.set_field('Type', kind)
    shape.one('TextLine').add('pt', 'Wi~de~~')
    shape.one('Points_New').add('pt', 0, 0)
    return shape


def font(node, prefix=''):
    for name, value in dict(FontSize=6, VectorFont=True, FontWidth=-1,
            FontScale=1, FontColor=0, FontName='', LineSpacing=1.2).items():
        node.set_field(prefix+name, value)


def revision_document():
    doc = new_schematic()
    root = doc.one('/Schematic')
    part = root.one('Components').append(new_symbol('Example', 'U1'))
    part.one('Pins').append(new_pin())
    part.one('Shapes').append(text(new_symbol_shape(), 10))
    pattern = part.one('Pattern')
    pattern.set_field('Width', 30)
    pattern.set_field('Height', 30)
    pattern.one('Shapes').insert(text(new_pattern_shape(1), 7), 1)
    dimension = pattern.one('Dimensions').add('Dimension', 0)
    fields(dimension, Enabled=True, Locked=False, Type=0, Connected1=-1, Object1=-1,
        SubObject1=-1, Point1=-1, Connected2=-1, Object2=-1, SubObject2=-1, Point2=-1,
        Layer=0, X1=0, Y1=0, X2=3, Y2=0, XD=0, YD=3, ArrowSize=1, Units=0,
        ShowUnits=True, Angle=0, ExternalRadius=0, PointerMode=0, PointerText='', Group=-1)
    font(dimension)
    for name in ('FontColor', 'LineSpacing'):
        dimension.one(name).detach()
    slot = root.one('CacheLib/Slots').add('Slot', 0, '')
    slot.add('VariablePath', '')
    definition = slot.add('Definition', 0)
    symbol = definition.append(new_symbol('Cached', 'X', placed=False))
    symbol.one('Pins').append(new_pin(placed=False))
    symbol.one('Shapes').append(text(new_symbol_shape(), 10))
    definition.append(pattern.clone())
    root.set_field('DesignCache_Count', 0)
    root.one('DesignCache_Links').add('Link', 0)
    root.one('Shapes').append(text(new_schematic_shape(), 10))
    picture = root.one('Shapes').append(new_schematic_shape(1))
    for name, value in dict(Type=11, Picture_Width=3, Picture_Height=3, PictureFlipped=True).items():
        picture.set_field(name, value)
    picture.one('Points_New').add('pt', 0, 0)
    table = root.one('Tables').add('Table')
    fields(table, Enabled=True, Selected=False, Locked=False, HideBorder=False,
        Layer=0, DefAlign=0, Orientation=0, Group=-1, Page=0, DefCellWidth=3,
        DefCellHeight=3, X1=0, Y1=0, X2=3, Y2=3, Name='Values')
    font(table, 'Def')
    table.add('ColWidths').add('pt', 3)
    table.add('RowHeights').add('pt', 3)
    cell = table.add('Cells').add('Cell', 0, 0, 3, 3)
    font(cell)
    fields(cell, FOrientation=False, FontType=0, Align=0, Text='Editable')
    grid = root.one('Pages/Page/TitleBlocks/TitleBlock[1]')
    grid.set_argument(1, 'Title')
    grid.set_field('Width', 3)
    grid.set_field('Height', 3)
    grid.one('ColWidths').add('pt', 3)
    grid.one('RowHeights').add('pt', 3)
    grid.one('Cells').add('Cell', 0, 0, 0).add('Edges', True, True, True, True)
    content = grid.one('Contents').add('Content', 0)
    font(content)
    fields(content, FOrientation=False, FontType=0, Align=0, Text='Title')
    content.add('Placement', 0, 0, 3, 3)
    for index, (node, size, mono) in enumerate(all_fonts(root)):
        node.set_field(size, Decimal('4.125') + Decimal(index)/8)
        if mono:
            node.set_field(mono, True)
    simulator = root.one('ssimulator')
    simulator.set_field('tp', 10)
    for row, value in zip(simulator.select('sim_digital/pt'), ('0', '1u', '10m', '+')):
        row.set_values(value)
    for group, name, kind, default in OPTION_FIELDS:
        value = not default if kind == 'boolean' else default+1 if kind == 'integer' else '2.75'
        simulator.one(group).set_field(name, value)
    simulator.one('OptionsTransient').set_field('Method', 2)
    bind_schematic_references(doc)
    return doc


class DocumentRevisionTests(unittest.TestCase):
    def test_every_binary_boundary_is_readable_and_stable(self):
        source = revision_document()
        original = source.one('/Schematic/Settings').scalar('PartFontSize')
        for version in range(46, 53):
            with self.subTest(version=version):
                report = ConversionReport()
                data = source.to_dch_bytes(version=version, report=report)
                loaded = parse_dch(data)
                self.assertTrue(loaded.complete)
                self.assertEqual(loaded.metadata['source_version'], version)
                self.assertEqual(loaded.to_dch_bytes(version=version, report=ConversionReport()), data)
                root = loaded.one('/Schematic')
                self.assertEqual(root.one('ssimulator').scalar('tp'), 10 if version >= 50 else 0)
                self.assertEqual(root.one('ssimulator/OptionsGeneral').scalar('Temp'), '2.75' if version >= 50 else '27.0')
                self.assertEqual(root.one('Shapes/Shape[2]').scalar('PictureFlipped'), version >= 51)
                self.assertEqual(root.one('Settings').scalar('PartFontMono'), version >= 52)
                self.assertEqual(root.one('Settings').scalar('PartFontSize'), original if version >= 52 else round(original))
                if version == 52:
                    for node, size, mono in all_fonts(source.one('/Schematic')):
                        restored = loaded.one(node.path)
                        self.assertEqual(restored.scalar(size), node.scalar(size))
                        if mono:
                            self.assertEqual(restored.scalar(mono), node.scalar(mono))
                self.assertEqual(source.one('/Schematic/Settings').scalar('PartFontSize'), original)
        for node, size, mono in all_fonts(source.one('/Schematic')):
            self.assertIsNone(node.child('FontSizeFloat'))

    def test_xml_and_binary_share_font_and_simulator_facts(self):
        source = revision_document()
        xml = source.to_dchxml_bytes(version=52, report=ConversionReport())
        public = ET.fromstring(xml)
        marking = public.find('./Schematic/Settings/Markings')
        self.assertEqual(marking.findtext('FontMono'), 'Y')
        self.assertNotEqual(marking.findtext('FontSize'), marking.findtext('FontSizeFloat'))
        loaded = parse_dchxml(xml).as_schematic()
        binary = parse_dch(loaded.to_dch_bytes(version=52, report=ConversionReport()))
        for doc in (loaded, binary):
            self.assertEqual(doc.one('/Schematic/Settings').scalar('PartFontSize'), source.one('/Schematic/Settings').scalar('PartFontSize'))
            self.assertTrue(doc.one('/Schematic/Settings').scalar('PartFontMono'))
            self.assertEqual(doc.one('/Schematic/ssimulator/OptionsTransient').scalar('Method'), 2)
            self.assertEqual([r.values[0] for r in doc.select('/Schematic/ssimulator/sim_digital/pt')], ['0', '1u', '10m', '+'])
            self.assertTrue(doc.one('/Schematic/Tables/Table').scalar('DefFontMono'))
            self.assertTrue(doc.one('/Schematic/Tables/Table/Cells/Cell').scalar('FontMono'))
            self.assertTrue(doc.one('/Schematic/Pages/Page/TitleBlocks/TitleBlock[1]/Contents/Content').scalar('FontMono'))
        old_report = ConversionReport()
        source.to_dchxml_bytes(version=51, report=old_report)
        self.assertIn('fractional-font-size', {notice.rule for notice in old_report.warnings})
        self.assertIn('monospaced-font', {notice.rule for notice in old_report.warnings})
        self.assertIn('dchxml-reader-digital-arguments', {notice.rule for notice in old_report.warnings})
        self.assertIn('picture-flipped', {notice.rule for notice in old_report.warnings})
        self.assertIsNone(source.as_dchxml(version=51, report=ConversionReport()).one('/Source/Schematic/Shapes/Shape[2]').child('PictureFlipped'))

    def test_ascii_keeps_fractional_sizes_and_reports_omitted_features(self):
        source = revision_document()
        report = ConversionReport()
        output = source.as_asc(report=report).as_schematic()
        self.assertEqual(output.one('/Schematic/Settings').scalar('PartFontSize'), source.one('/Schematic/Settings').scalar('PartFontSize'))
        self.assertFalse(output.one('/Schematic/Settings').scalar('PartFontMono'))
        self.assertTrue({'monospaced-font', 'simulator-options', 'picture-flipped'}.issubset({n.rule for n in report.warnings}))
        self.assertTrue(source.one('/Schematic/Settings').scalar('PartFontMono'))

    def test_xml_float_size_is_authoritative_over_compatibility_integer(self):
        source = new_schematic()
        tree = ET.fromstring(source.to_dchxml_bytes(version=52))
        font = tree.find('./Schematic/Settings/Markings')
        font.find('FontSize').text = '99'
        font.find('FontSizeFloat').text = '6.5'
        loaded = parse_dchxml(ET.tostring(tree)).as_schematic()
        self.assertEqual(loaded.one('/Schematic/Settings').scalar('PartFontSize'), Decimal('6.5'))
        rebuilt = loaded.as_dchxml(version=52)
        self.assertEqual(rebuilt.one('/Source/Schematic/Settings/Markings').scalar('FontSize'), 6)

    def test_monospaced_measurement_respects_visible_characters(self):
        font = builtin_vector_metrics()
        self.assertEqual(font.measure('iiii', monospaced=True), font.measure('WWWW', monospaced=True))
        self.assertEqual(font.measure('W~i~~', monospaced=True), font.measure('WiX', monospaced=True))
        self.assertNotEqual(font.measure('iiii'), font.measure('WWWW'))

    def test_xml_dependencies_and_integral_compatibility_syntax(self):
        source = revision_document()
        for version in (49, 50, 51, 52):
            output = ET.fromstring(source.to_dchxml_bytes(version=version, report=ConversionReport()))
            library = output.find('Library')
            self.assertLess(list(library).index(library.find('Library')), list(library).index(library.find('Components')))
            text_shape = output.find('./Schematic/Shapes/Shape')
            self.assertNotIn('.', text_shape.get('FontSize'))
            simulator = output.find('./Schematic/Simulator')
            if version >= 50:
                self.assertEqual(simulator.get('Type'), 'Digital' if version >= 52 else '10')

    def test_explicit_default_pad_choice_does_not_duplicate_equal_geometry(self):
        from lib.design.asc_import_graphics import empty_pad
        source = new_schematic()
        part = source.one('/Schematic/Components').append(new_symbol('Pads', 'U1'))
        pads = part.one('Pattern/Pads')
        for index, standard in ((1, True), (2, False)):
            pad = empty_pad(index)
            pad.annotations.clear()
            pad.set_values(index, str(index), '', index, 0)
            pad.set_field('Number_New', index)
            pad.set_field('Standard', standard)
            pads.insert(pad, index)
        pads.children('Pad')[-1].set_values(3, '', '', 0, 0)
        bind_schematic_references(source)
        public = source.as_dchxml(version=52, report=ConversionReport())
        self.assertEqual(len(public.select('/Source/Library/Library/PadStyles/PadStyle')), 1)
        self.assertEqual([p.scalar('DefStyle') for p in public.select('/Source/Library/Library/Patterns/Pattern/Pads/Pad')], [True, False])
        restored = public.as_schematic().select('/Schematic/Components/Part/Pattern/Pads/Pad')[1:-1]
        self.assertEqual([p.scalar('Standard') for p in restored], [True, False])

    def test_future_schemas_still_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, '29..52'):
            parse_dch(b'\x07DTSCHEM' + (1000053).to_bytes(3, 'big'))
        with self.assertRaisesRegex(ValueError, '46 through 52'):
            new_schematic().to_dch_bytes(version=53)


if __name__ == '__main__':
    unittest.main()
