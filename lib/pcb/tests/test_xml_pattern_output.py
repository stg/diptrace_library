"""Physical PCB XML output preserves editable local geometry and identities."""
from decimal import Decimal
import unittest
from xml.etree import ElementTree

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.units import XmlUnits
from lib.common.xml import set_attribute
from lib.pcb.formats.dipxml.pattern_output import project_pattern
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import DIPXML
from lib.pcb.formats.dipxml.syntax import dumps, loads
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dipxml_library import read, source


PATH = '/Board/CacheLib/Slots/Slot/Definition/Pattern'


def design():
    text = source().replace('<Name>Package</Name>','''<Name>Package</Name>
      <Groups><Item Id="31" X="1" Y="2"/></Groups>
      <Holes><Hole Id="92" Group="31" X="3" Y="4" Diam="2" HoleDiam="1"/></Holes>
      <Dimensions><Dimension Id="8" Type="Horizontal" Connected1="Pad" SubObject1="17" Point1="0"
          Connected2="Hole" SubObject2="92" Point2="0" Group="31"/></Dimensions>''')
    text = text.replace('<Pad Id="17" Style="S"','<Pad Id="17" Group="31" Style="S"')
    return read(text,report=ConversionReport())


def reopen(document, *, units='mm', report=None):
    projected = project_pattern(document.one(PATH),style='P',units=XmlUnits(units),report=report)
    data = loads(source())
    library = data.one('/Source/Library/Library')
    set_attribute(library,'Units',units)
    set_attribute(library,'Version','5.3.5.1')
    library.one('PadStyles').detach()
    library.one('Patterns').detach()
    library.append(projected.styles)
    library.add('Patterns').append(projected.element)
    # XML owns these physical pad pairs in the enclosing symbol definition.
    pairs = data.one('/Source/Library/Components/Component/Part/InternalConnections')
    for child in tuple(pairs.children()):
        child.detach()
    for first,second in projected.connections:
        row = pairs.add('IntCon')
        set_attribute(row,'X',first)
        set_attribute(row,'Y',second)
    return read(dumps(data),report=ConversionReport())


class XmlPatternOutputTests(unittest.TestCase):
    def test_terminal_positions_and_public_object_keys_survive_reordering(self):
        root = ElementTree.fromstring(source())
        style = root.find('Library/Library/PadStyles/PadStyle')
        terminals = ElementTree.SubElement(style, 'Terminals')
        terminal = ElementTree.SubElement(terminals, 'Terminal',
            dict(Shape='Polygon', X='0', Y='0', Angle='0', Width='2', Height='3'))
        points = ElementTree.SubElement(terminal, 'Points')
        for x, y in ((0, 0), (1, 0), (1, 1), (0, 1)):
            ElementTree.SubElement(points, 'Item', dict(X=str(x), Y=str(y)))
        pattern = root.find('Library/Library/Patterns/Pattern')
        dimensions = ElementTree.SubElement(pattern, 'Dimensions')
        ElementTree.SubElement(dimensions, 'Dimension',
            dict(Connected1='Terminal', Object1='2', SubObject1='0', Point1='2',
                 Connected2='Shape', SubObject2='9', Point2='1'))
        document = read(ElementTree.tostring(root), report=ConversionReport())
        pattern = document.one(PATH)
        pad = pattern.one('Pads/Pad[2]')
        terminal = pad.one('PadTerminal')
        vertex = terminal.one('ShapePoints/pt[2]')
        dimension = pattern.one('Dimensions/Dimension')
        pad.move_to(pattern.one('Pads'), 0)
        document.copy(terminal, index=0)
        vertex.move_to(terminal.one('ShapePoints'), 0)
        self.assertEqual((dimension['Object1'], dimension['SubObject1'], dimension['Point1']), (1, 1, 1))
        before = model_text(document, preserve=False)
        for version in DIPXML.write_versions:
            with self.subTest(version=version):
                report = ConversionReport()
                data = io.serialize(document, format='dipxml', version=version, report=report)
                xml = ElementTree.fromstring(data)
                style_key = xml.find('Library/Components/Component/Part/Pattern').get('Style')
                physical = next(row for row in xml.findall('Library/Library/Patterns/Pattern')
                                if row.get('PatternStyle') == style_key)
                row = physical.find('Dimensions/Dimension')
                self.assertEqual((row.get('Object1'), row.get('SubObject1'), row.get('Point1')), ('1', '1', '1'))
                self.assertEqual(physical.find('Pads/Pad').get('Id'), '41')
                current = io.parse(data, report=ConversionReport())
                output = current.one(PATH)
                links = {link.role: link.target for link in current.references.outgoing(output.one('Dimensions/Dimension'))}
                self.assertIs(links['pattern-dimension-1'], output.one('Pads/Pad[1]/PadTerminal[2]/ShapePoints/pt[1]'))
                self.assertEqual(links['pattern-dimension-1'].values, (3, 0))
                self.assertIs(links['pattern-dimension-2'], output.one('Shapes/Shape/Points_New/pt[2]'))
                self.assertEqual(report.errors, [])
                self.assertEqual(model_text(document, preserve=False), before)

    def test_inactive_unreferenced_group_is_normalized_without_changing_the_model(self):
        document = design()
        pattern = document.one(PATH)
        inactive = document.copy(pattern.one('Pattern_Groups/pt'), index=0)
        inactive['Enabled'] = False
        before = model_text(document, preserve=False)
        report = ConversionReport()
        rebuilt = reopen(document, report=report)
        output = rebuilt.one(PATH)
        self.assertEqual(len(output.select('Pattern_Groups/pt')), 1)
        self.assertIs(output.one('Pads/Pad[1]')['Group'], output.one('Pattern_Groups/pt'))
        self.assertIn('local-group-normalization', [notice.rule for notice in report.infos])
        self.assertEqual(report.errors, [])
        self.assertEqual(model_text(document, preserve=False), before)

    def test_single_member_placement_group_is_normalized_without_changing_the_model(self):
        from lib.pcb.tests.test_dip_output import configured_document
        document = configured_document()
        pattern = document.one('/Board/Components/Component/Pattern')
        hole = pattern.one('Holes').add('Hole', True, False, 3, 6, 2, 1, 99)
        before, report = model_text(document, preserve=False), ConversionReport()
        output = project_pattern(pattern, style='Physical', units=XmlUnits('mm'), report=report)
        row = output.element.one('Holes/Hole')
        self.assertIsNone(row.child('Group'))
        self.assertIsNone(output.element.child('Groups'))
        self.assertEqual((row['X'], row['Y']), (-1, -2))
        self.assertNotIn('unresolved-footprint-group', {n.rule for n in report.warnings})
        self.assertIn('placement-group-normalization', {n.rule for n in report.infos})
        self.assertEqual(hole['Group'], 99)
        self.assertEqual(model_text(document, preserve=False), before)

    def test_all_xml_profiles_project_placement_membership_separately_from_template_groups(self):
        document = design()
        path = '/Board/Components/Component/Pattern'
        pattern = document.one(path)
        members = ('Pads/Pad[1]', 'Shapes/Shape[1]', 'Holes/Hole[1]', 'Dimensions/Dimension[1]')
        source_groups, output_groups = (1000000000, 17, 17, 1000000000), (1, 0, 0, 1)
        for member, value in zip(members, source_groups):
            pattern.one(member)['Group'] = value
        self.assertIsNone(pattern.child('Pattern_Groups'))
        cached = document.one(PATH)
        cached_group = cached.one('Pattern_Groups/pt')
        self.assertIs(cached.one('Pads/Pad[1]')['Group'], cached_group)
        before = model_text(document, preserve=False)
        for version in DIPXML.write_versions:
            with self.subTest(version=version):
                current = document
                for _ in range(2):
                    report = ConversionReport()
                    data = io.serialize(current, format='dipxml', version=version, report=report)
                    xml = ElementTree.fromstring(data)
                    style = xml.find('Board/Components/Component').get('PatternStyle')
                    physical = next(p for p in xml.findall('Library/Library/Patterns/Pattern')
                                    if p.get('PatternStyle') == style)
                    groups = physical.findall('Groups/Item')
                    self.assertEqual([row.get('Number') for row in groups], ['0', '1'])
                    self.assertTrue(all(Decimal(row.get(axis)) == 0 for row in groups for axis in ('X', 'Y')))
                    self.assertEqual(tuple(int(physical.find(member).get('Group')) for member in members), output_groups)
                    current = io.parse(data, report=report)
                    placed = current.one(path)
                    self.assertIsNone(placed.child('Pattern_Groups'))
                    self.assertEqual(tuple(placed.one(member)['Group'] for member in members), output_groups)
                    definition = current.one(PATH)
                    self.assertIs(definition.one('Pads/Pad[1]')['Group'], definition.one('Pattern_Groups/pt'))
                    self.assertNotIn('unresolved-footprint-group', {n.rule for n in report.warnings})
                    current.references.validate()
        self.assertEqual(model_text(document, preserve=False), before)

    def test_surface_and_round_styles_keep_their_independent_hole_settings(self):
        document = design()
        pattern, pad = document.one(PATH), document.one(PATH+'/Pads/Pad[1]')
        for surface, hole_type in ((True, 0), (True, 1), (False, 0)):
            with self.subTest(surface=surface, hole_type=hole_type):
                for target in (pattern, pad):
                    target['SurfacePad'], target['PadHoleType'] = surface, hole_type
                    target['PadHole'], target['PadHoleH'] = Decimal('1.75'), Decimal('2.25')
                pad['Standard'] = False
                before = model_text(document, preserve=False)
                for units in ('mm', 'mil', 'inch'):
                    rebuilt = reopen(document, units=units)
                    for path in (PATH, PATH+'/Pads/Pad[1]'):
                        current = rebuilt.one(path)
                        self.assertEqual((current['SurfacePad'], current['PadHoleType']), (surface, hole_type))
                        self.assertLessEqual(abs(current['PadHole']-Decimal('1.75')), Decimal('1e-23'))
                        self.assertLessEqual(abs(current['PadHoleH']-Decimal('2.25')), Decimal('1e-23'))
                self.assertEqual(model_text(document, preserve=False), before)

    def test_all_xml_profiles_retain_inactive_style_geometry_without_drift(self):
        document = design()
        pattern, pad = document.one(PATH), document.one(PATH+'/Pads/Pad[1]')
        points = ((0, 0), (3, 0), (3, 6))
        for target, shape, collection in ((pattern, 'PadShape', 'PadPoints'),
                                          (pad, 'PadShape_New', 'PadPoints_New')):
            target[shape], target['SurfacePad'] = 0, True
            target['PadCorner'] = Decimal('12.5')
            target['PadShape_X'], target['PadShape_Y'] = 3, -6
            for point in points:
                target.one(collection).add('pt', *point)
        pad['Standard'] = False
        before = model_text(document, preserve=False)
        for version in DIPXML.write_versions:
            with self.subTest(version=version):
                current = document
                for cycle in range(2):
                    current = io.parse(io.serialize(current, format='dipxml', version=version,
                        report=ConversionReport()), report=ConversionReport())
                    for path, collection in ((PATH, 'PadPoints'),
                                              (PATH+'/Pads/Pad[1]', 'PadPoints_New')):
                        target = current.one(path)
                        self.assertEqual((target['PadCorner'], target['PadShape_X'], target['PadShape_Y']),
                                         (Decimal('12.5'), 3, -6))
                        self.assertEqual(tuple(row.values for row in target.select(collection+'/pt')), points)
        self.assertEqual(model_text(document, preserve=False), before)

    def test_cached_geometry_groups_dimension_and_pairs_survive_reordering(self):
        document = design()
        pattern = document.one(PATH)
        pattern.one('Pads/Pad[1]').move_to(pattern.one('Pads'))
        group = pattern.one('Pattern_Groups/pt')
        document.copy(group,index=0)
        expected,before,report = signature(pattern),model_text(document,preserve=False),ConversionReport()
        projected = project_pattern(pattern,style='P',units=XmlUnits('mm'),report=report)
        self.assertEqual([pad['Id'] for pad in projected.element.select('Pads/Pad')],[41,17])
        self.assertEqual(projected.element.one('Pads/Pad[2]')['Group'],1)
        self.assertEqual([group['Number'] for group in projected.element.select('Groups/Item')], [0, 1])
        self.assertTrue(all(group.child('Id') is None for group in projected.element.select('Groups/Item')))
        self.assertEqual(projected.element.one('Dimensions/Dimension')['SubObject1'],17)
        self.assertEqual(projected.connections,((17,41),))
        rebuilt = reopen(document)
        self.assertEqual(signature(rebuilt.one(PATH)),expected)
        self.assertEqual(signature(reopen(rebuilt).one(PATH)),expected)
        self.assertEqual(model_text(document,preserve=False),before)
        self.assertEqual(report.notices,[])

    def test_text_strokes_full_angles_multiline_and_3d_placement_use_output_units(self):
        document = design()
        pattern = document.one(PATH)
        shape = pattern.one('Shapes/Shape')
        shape['Type'],shape['FontSize'],shape['FontWidth'] = 7,Decimal('1.375'),Decimal('.4572')
        shape['TextAngle'] = Decimal('8.25')
        shape.one('TextLine').add('pt','First line')
        shape.one('TextLine').add('pt','')
        shape.one('TextLine').add('pt','Last line')
        pattern.one('Dimensions/Dimension')['FontWidth'] = Decimal('.4572')
        model = pattern.one('Model3D')
        model['Model3DFile'],model['Model3DFile_Variable'] = 'models/package.step',''
        model.one('Rotate')['Z'] = Decimal('38.25')
        model.one('Offset')['Y'] = Decimal('1.524')
        expected,before = signature(pattern),model_text(document,preserve=False)
        for units in ('mm','mil','inch'):
            with self.subTest(units=units):
                output = project_pattern(pattern,style='P',units=XmlUnits(units),report=ConversionReport())
                self.assertEqual(output.element.one('Shapes/Shape')['Angle'],Decimal('8.25'))
                self.assertEqual(output.element.one('Shapes/Shape')['FontSizeFloat'],Decimal('1.375'))
                self.assertEqual(output.element.one('Model3D/Filename/Var').values,())
                current = document
                for _ in range(3):
                    current = reopen(current,units=units)
                    actual = signature(current.one(PATH))
                    self.assertEqual(actual.keys(),expected.keys())
                    for path,value in expected.items():
                        if isinstance(value,(int,float,Decimal)) and not isinstance(value,bool):
                            self.assertLessEqual(abs(Decimal(str(actual[path]))-Decimal(str(value))),Decimal('1e-28'),path)
                        else:
                            self.assertEqual(actual[path],value,path)
        self.assertEqual(model_text(document,preserve=False),before)

    def test_reconstructed_style_choices_do_not_rewrite_pad_geometry(self):
        document = design()
        pattern = document.one(PATH)
        pad = pattern.one('Pads/Pad[1]')
        pad['Standard'] = False
        terminal = pad.add('PadTerminal',0)
        for name,current in dict(Type=3,X=1,Y=2,Angle=Decimal('.4'),ShapeWidth=3,
                                 ShapeHeight=4,ShapeCorner=0).items():
            terminal.add(name,current)
        terminal.add('ShapePoints').add('pt',1,2)
        pad.one('PadMask_TopSegments').add('pt',1,2,3,4)
        pad['DisableTopPaste'] = 3
        expected = signature(pattern)
        rebuilt = reopen(document)
        self.assertEqual(signature(rebuilt.one(PATH)),expected)
        self.assertFalse(rebuilt.one(PATH+'/Pads/Pad[1]')['Standard'])

    def test_unmapped_content_remains_an_explicit_error(self):
        document = design()
        pattern = document.one(PATH)
        pattern.add('Unmapped',17)
        before = model_text(document,preserve=False)
        with self.assertRaises(PcbError):
            project_pattern(pattern,style='P',units=XmlUnits('mm'))
        self.assertEqual(model_text(document,preserve=False),before)


if __name__ == '__main__':
    unittest.main()
