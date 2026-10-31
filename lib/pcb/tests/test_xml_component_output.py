"""Current XML placements, layer overrides and pad groups survive editing."""
from decimal import Decimal
import unittest
from xml.etree import ElementTree

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.model import Document
from lib.common.units import XmlUnits
from lib.common.xml import set_attribute
from lib.common.xml_output import field
from lib.pcb.formats.dipxml.component_output import project_components
from lib.pcb.formats.dipxml.library_output import project_library
from lib.pcb.formats.dipxml.resource_output import (project_layers, project_vias, project_groups,
                                                  project_hierarchy_sheets, project_assembly_variants)
from lib.pcb.formats.dipxml.syntax import dumps
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dipxml_library import read, source
from lib.pcb.tests.test_dipxml_internal_connections import PAIRS, GROUP
from lib.pcb.tests.test_dipxml_hierarchy import SHEETS, PATH as HIERARCHY_PATH


COMPONENT = '/Board/Components/Component'


def context(document, *, units='mm', report=None):
    board, scale = document.one('/Board'), XmlUnits(units)
    report = ConversionReport() if report is None else report
    physical = board.select('Components/Component/Pattern')
    library = project_library(board, units=scale, physical=physical, report=report)
    output = Document(representation='xml')
    root = output.root.add('Source')
    for name, value in (('Type', 'DipTrace-PCB'), ('Version', '5.3.5.1'), ('Units', units)):
        set_attribute(root, name, value)
    root.append(library.element)
    target = root.add('Board')
    target.append(project_layers(board, units=scale))
    target.append(project_vias(board, units=scale, report=report))
    target.append(project_groups(board, report=report))
    target.append(project_assembly_variants(board))
    target.append(project_hierarchy_sheets(board))
    target.append(project_components(board, library=library, units=scale, report=report))
    # Only component membership is in scope here; routing and other net data
    # have their own output tests. This generated context retains no XML donor.
    nets = target.add('Nets')
    for net in board.select('Nets/Net'):
        row = nets.add('Net')
        set_attribute(row, 'Id', net['Number'])
        field(row, 'Name', net['Name'])
        members = row.add('Pads')
        for component in board.select('Components/Component'):
            keys = library.physical_styles[component.one('Pattern')].pad_keys
            for pad in component.select('Pattern/Pads/Pad'):
                if pad['Net'] is net:
                    member = members.add('Item')
                    set_attribute(member, 'Comp', component['Number'])
                    set_attribute(member, 'Pad', keys[pad])
    return output, library


def reopen(document, *, units='mm'):
    output, _ = context(document, units=units)
    return read(dumps(output), report=ConversionReport()), output


class XmlComponentOutputTests(unittest.TestCase):
    def test_independent_component_layer_omission_warns_and_keeps_the_source(self):
        document = read(source(), report=ConversionReport())
        component = document.one(COMPONENT)
        layer = document.one('/Board/Layers/Layer[1]')
        component['Layer'] = layer
        before, report = model_text(document, preserve=False), ConversionReport()
        output, _ = context(document, report=report)
        rebuilt = read(dumps(output), report=ConversionReport())
        self.assertIs(component['Layer'], layer)
        self.assertIsNone(rebuilt.one(COMPONENT)['Layer'])
        self.assertIn('component-connected-layer', {n.rule for n in report.warnings})
        self.assertEqual(model_text(document, preserve=False), before)

    def test_static_vias_use_the_reconstructible_style_without_adding_patterns(self):
        root = ElementTree.fromstring(source())
        board = root.find('Board')
        via = ElementTree.SubElement(ElementTree.SubElement(board, 'ViaStyles'), 'ViaStyle',
                                     Id='5', Size='0.6', HoleSize='0.3', Lay1='0', Lay2='-1')
        ElementTree.SubElement(via, 'Name').text = 'Through'
        component = board.find('Components/Component')
        component.attrib.pop('PatternStyle')
        component.set('Type', 'Via')
        component.set('ViaStyle', '5')
        component.find('Pads').clear()
        ElementTree.SubElement(component.find('Pads'), 'Pad', Id='1', NetId='-1')
        board.find('Nets').clear()
        document = read(ElementTree.tostring(root, encoding='unicode'), report=ConversionReport())
        expected, cache = signature(document.one(COMPONENT)), signature(document.one('/Board/CacheLib'))
        for _ in range(3):
            document, output = reopen(document)
            self.assertFalse(output.one('/Source/Board/Components/Component').child('PatternStyle'))
            self.assertEqual(signature(document.one(COMPONENT)), expected)
            self.assertEqual(signature(document.one('/Board/CacheLib')), cache)
        # An explicit physical style cannot prevent via-pad initialization.
        # Report the omitted local geometry and retain the authoring model.
        document.one(COMPONENT+'/Pattern/Pads/Pad')['X'] = 1
        report = ConversionReport()
        output, _ = context(document, report=report)
        rebuilt = read(dumps(output), report=ConversionReport())
        self.assertIsNotNone(output.one('/Source/Board/Components/Component').child('PatternStyle'))
        self.assertEqual(rebuilt.one(COMPONENT+'/Pattern/Pads/Pad')['X'], 0)
        self.assertEqual(document.one(COMPONENT+'/Pattern/Pads/Pad')['X'], 1)
        self.assertTrue(any(notice.rule == 'xml-via-pad-data' for notice in report.warnings))

    def test_via_spans_hierarchy_and_assembly_exclusions_follow_current_resources(self):
        text = source().replace('<Board>', '<Board>'+SHEETS, 1).replace(
            '<Name>Device</Name>', '<Name>Device</Name>'+HIERARCHY_PATH+
            '<AssemblyExclude><Item>1</Item></AssemblyExclude>')
        root = ElementTree.fromstring(text)
        board = root.find('Board')
        variants = ElementTree.SubElement(board, 'AssemblyVariants')
        for name in ('Base', 'Option'):
            ElementTree.SubElement(variants, 'AssemblyVariant').text = name
        layers = board.find('CopperLayers')
        for key, name in ((2, 'Inner A'), (3, 'Inner B')):
            row = ElementTree.Element('Lay', Id=str(key))
            ElementTree.SubElement(row, 'Name').text = name
            layers.insert(len(layers)-1, row)
        via = ElementTree.SubElement(ElementTree.SubElement(board, 'ViaStyles'), 'ViaStyle',
                                     Id='5', Size='0.6', HoleSize='0.3', Lay1='1', Lay2='2')
        ElementTree.SubElement(via, 'Name').text = 'Buried'
        board.find('Components/Component').set('ViaStyle', '5')
        document = read(ElementTree.tostring(root, encoding='unicode'), report=ConversionReport())
        option = document.one('/Board/AssemblyVariants/AssemblyVariant[2]')
        option.move_to(option.parent, 0)
        document.one('/Board/HierarchySheets/HSheet[1]/UpdateIds/UId')['Id'] = 400
        expected = signature(document.one(COMPONENT))
        rebuilt, output = reopen(document)
        self.assertEqual(signature(rebuilt.one(COMPONENT)), expected)
        for path in ('ViaStyles', 'Layers', 'HierarchySheets', 'AssemblyVariants'):
            self.assertEqual(signature(rebuilt.one('/Board/'+path)), signature(document.one('/Board/'+path)))
        exclusion = rebuilt.one(COMPONENT+'/AssemblyExclude/Item')
        self.assertEqual(exclusion['Index'], 0)
        self.assertEqual(exclusion['Variant']['Name'], 'Option')
        self.assertEqual([item.values[0] for item in output.select('/Source/Board/Components/Component/HierarchyPath/Item')],
                         [400, 700, 77])
        rebuilt.references.validate()

    def test_placement_markings_and_metadata_round_trip_without_new_cache_definitions(self):
        text = source().replace('<Value>10K</Value>', '''<Value>10K</Value>
          <AddFields><AddField Type="Text"><Name>Revision</Name><Text>A</Text>
            <Silk Show="Show" Align="Position" X="2" Y="3" Angle="0.5"/>
            <Assy Show="Hide" Align="Center"/></AddField></AddFields>''')
        # Template defaults and the component's current fields have distinct
        # ownership. Reusing a style must not overwrite either of them.
        text = text.replace('<Name>Package</Name>', '''<Name>Package</Name>
          <Value>Template value</Value><Manufacturer>Template maker</Manufacturer><Datasheet>Template sheet</Datasheet>
          <AddFields><AddField Type="Text"><Name>Template only</Name><Text>Default</Text></AddField></AddFields>''')
        document = read(text, report=ConversionReport())
        component = document.one(COMPONENT)
        component['Angle'], component['X'], component['MarkingFontSize'] = Decimal('8.125'), 123, Decimal('5.375')
        component['LibPath_Variable'] = ''
        for name in ('Value', 'Manufacturer', 'Datasheet'):
            component[name] = ''
        expected, cache = signature(component), signature(document.one('/Board/CacheLib'))
        before = model_text(document, preserve=False)
        current = document
        for _ in range(3):
            current, _ = reopen(current)
            self.assertEqual(signature(current.one(COMPONENT)), expected)
            self.assertEqual(signature(current.one('/Board/CacheLib')), cache)
        self.assertEqual(model_text(document, preserve=False), before)

    def test_internal_pairs_and_policies_keep_pad_identities_after_reorder(self):
        text = source().replace('<Name>Device</Name>', '<Name>Device</Name>'+PAIRS+GROUP)
        document = read(text, report=ConversionReport())
        component = document.one(COMPONENT)
        component.one('Pattern/Pads/Pad[2]').move_to(component.one('Pattern/Pads'), 0)
        expected = signature(component)
        cache = signature(document.one('/Board/CacheLib'))
        # The policy selects a group through one representative member. Its
        # schema explicitly permits import to canonicalize that representative;
        # group membership, authored pairs and ConnectAll retain their meaning.
        policy_path = '/InternalConnections[1]/IntCon[1]'
        expected[policy_path+'/Pad'] = expected[policy_path+'/Members'][0]
        rebuilt, output = reopen(document)
        self.assertEqual(signature(rebuilt.one(COMPONENT)), expected)
        self.assertEqual(signature(rebuilt.one('/Board/CacheLib')), cache)
        pair = output.one('/Source/Board/Components/Component/IntConRecords/Item')
        self.assertEqual((pair['X'], pair['Y']), (17, 41))
        policy = rebuilt.one(COMPONENT+'/InternalConnections/IntCon')
        self.assertTrue(policy['ConnectAll'])
        self.assertEqual({pad['Id'] for pad in policy['Members']}, {17, 41})
        rebuilt.references.validate()

    def test_hidden_blind_and_thermal_layers_use_current_reordered_layer_identities(self):
        root = ElementTree.fromstring(source())
        layers = root.find('Board/CopperLayers')
        for key, name in ((2, 'Inner A'), (3, 'Inner B')):
            row = ElementTree.Element('Lay', Id=str(key))
            ElementTree.SubElement(row, 'Name').text = name
            layers.insert(len(layers)-1, row)
        pad = root.find('Board/Components/Component/Pads/Pad')
        pad.set('ShieldGroup', '0')
        pad.set('DefStyle', 'N')
        for name, key in (('HideRingLay', 2), ('BlindLay', 3)):
            ElementTree.SubElement(ElementTree.SubElement(pad, name), 'Item').text = str(key)
        spokes = ElementTree.SubElement(pad, 'CustomSpokes')
        ElementTree.SubElement(spokes, 'CustomSpoke', Lay='2', Type='1', Spoke='2', Width='0.2')
        document = read(ElementTree.tostring(root, encoding='unicode'), report=ConversionReport())
        members = document.one(COMPONENT+'/Pattern/Pads/Pad[1]')
        first, second = document.select('/Board/Layers/Layer')[1:3]
        self.assertIs(members.one('HideLayer/Item')['Layer'], first)
        self.assertIs(members.one('BlindLayer/Item')['Layer'], second)
        second.move_to(second.parent, 1)
        self.assertEqual(members.one('HideLayer/Item')['Lay'], 2)
        expected = signature(document.one(COMPONENT))
        rebuilt, _ = reopen(document)
        self.assertEqual(signature(rebuilt.one(COMPONENT)), expected)
        self.assertFalse(rebuilt.one(COMPONENT+'/Pattern/Pads/Pad[1]')['Standard'])
        self.assertEqual(rebuilt.one(COMPONENT+'/Pattern/Pads/Pad[1]')['ShieldGroup'], 0)

    def test_component_units_keep_placement_and_marking_angles_unquantized(self):
        document = read(source(), report=ConversionReport())
        document.one(COMPONENT)['PlacementClearance'] = Decimal('.4572')
        expected = signature(document.one(COMPONENT))
        for units in ('mm', 'mil', 'inch'):
            with self.subTest(units=units):
                current = document
                for _ in range(3):
                    current, _ = reopen(current, units=units)
                    actual = signature(current.one(COMPONENT))
                    self.assertEqual(actual.keys(), expected.keys())
                    for path, value in expected.items():
                        if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                            self.assertLessEqual(abs(Decimal(str(actual[path]))-Decimal(str(value))), Decimal('1e-28'), path)
                        else:
                            self.assertEqual(actual[path], value, path)

    def test_unmapped_data_is_rejected_without_mutating_current_placement(self):
        document = read(source(), report=ConversionReport())
        document.one(COMPONENT).add('Unmapped', 1)
        before = model_text(document, preserve=False)
        with self.assertRaisesRegex(PcbError, 'no PCB DIPXML projection'):
            reopen(document)
        self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
