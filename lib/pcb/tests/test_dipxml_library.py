"""Whole XML input retains editable library definitions separately from placement."""
from decimal import Decimal
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.references import ReferenceError
from lib.pcb.formats.dipxml.read import prepare
from lib.pcb.formats import io
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.model.library_relations import PIN_PAD_ROLE
from lib.pcb.model import library_records
from lib.pcb.tests.test_dipxml_components import SOURCE
from lib.pcb.tests.test_dipxml_electrical import NETS


PART = '''<Part PartType="Normal" Type="Free" RefDes="U" SubFolderIndex="-1" Width="2" Height="3">
  <Name>Template</Name><LibPath><Path>parts.lib</Path><Var>relative/parts.lib</Var></LibPath>
  <Category Index="12"><CategoryTypes><CategoryType><Type Index="5"></Type><SubType Index="9"></SubType></CategoryType></CategoryTypes></Category>
  <Groups><Item Id="31" X="1" Y="2"/></Groups>
  <Pins><Pin Id="18" X="1" Y="2" PadId="17" Group="31" ShowName="Y" Length="3">
    <Name>A</Name><PadNumber>1</PadNumber><NameFont Size="6" Width="-1" Scale="1"/>
  </Pin></Pins>
  <Shapes><Shape Id="88" Type="Line" Group="31" LineWidth="0.1"><Points>
    <Item X="0" Y="0"/><Item X="1" Y="1"/></Points></Shape></Shapes>
  <Pattern Style="P"/><InternalConnections><IntCon X="17" Y="41"/></InternalConnections>
</Part>'''
CATEGORIES = '''<Categories><Category Index="12"><Name>Passives</Name><Types>
  <Type Index="5"><Name>Function</Name><SubTypes><SubType Index="9"><Name>General</Name></SubType></SubTypes></Type>
</Types></Category></Categories>'''


def source(*, component_units='mm', pattern_units='mm', components=1):
    start, end = SOURCE.index('<Library'), SOURCE.index('</Library>')+len('</Library>')
    pattern = SOURCE[start:end].replace('Units="mm"', f'Units="{pattern_units}"', 1)
    library = f'<Library Type="DipTrace-ComponentLibrary" Version="5.3.5.1" Units="{component_units}">{CATEGORIES}{pattern}<Components>'
    library += ''.join('<Component>'+PART.replace('Template', 'Template'+str(index))+'</Component>' for index in range(components))
    library += '</Components></Library>'
    return (SOURCE[:start]+library+SOURCE[end:]).replace('</Board>', NETS+'</Board>')


def with_unused_pattern(text):
    root = ElementTree.fromstring(text)
    patterns = root.find('Library/Library/Patterns')
    unused = ElementTree.fromstring(ElementTree.tostring(patterns.find('Pattern')))
    unused.set('PatternStyle', 'Unused')
    unused.find('Name').text = 'Unused package'
    patterns.append(unused)
    return ElementTree.tostring(root, encoding='unicode')


@import_diagnostics('dipxml')
def read(text):
    return assemble_graphics(prepare(text)).document


class PcbXmlLibraryTests(unittest.TestCase):
    def test_inactive_xml_groups_clear_only_their_known_assignments(self):
        root = ElementTree.fromstring(source())
        part = root.find('Library/Components/Component/Part')
        part.find('Groups/Item').set('Enabled', 'N')
        ElementTree.SubElement(part.find('Groups'), 'Item', dict(Id='41', Enabled='Y', X='3', Y='4'))
        part.find('Shapes/Shape').set('Group', '41')
        pattern = root.find('Library/Library/Patterns/Pattern')
        groups = ElementTree.SubElement(pattern, 'Groups')
        ElementTree.SubElement(groups, 'Item', dict(Number='31', Enabled='N', X='1', Y='2'))
        ElementTree.SubElement(groups, 'Item', dict(Number='41', X='3', Y='4'))
        pads = pattern.findall('Pads/Pad')
        pads[0].set('Group', '31')
        pads[1].set('Group', '41')
        report = ConversionReport()
        document = read(ElementTree.tostring(root, encoding='unicode'), report=report)
        definition = document.one('/Board/CacheLib/Slots/Slot/Definition')
        symbol, footprint = definition.one('Part'), definition.one('Pattern')
        self.assertEqual(symbol.one('Groups/pt').values, (True, 0, 9, -12))
        self.assertIsNone(symbol.one('Pins/Pin')['Group'])
        self.assertIs(symbol.one('Shapes/Shape')['Group'], symbol.one('Groups/pt'))
        self.assertIsNone(footprint.one('Pads/Pad[1]')['Group'])
        self.assertIs(footprint.one('Pads/Pad[2]')['Group'], footprint.one('Pattern_Groups/pt'))
        self.assertFalse(document.select('//UnresolvedKeys'))
        self.assertEqual(len([n for n in report.infos if n.rule == 'local-group-normalization']), 2)
        self.assertEqual(report.errors, [])
        document.references.validate()

    def test_footprint_groups_belong_to_the_template_without_copies_in_placements(self):
        root = ElementTree.fromstring(source())
        pattern = root.find('Library/Library/Patterns/Pattern')
        groups = pattern.find('Groups')
        if groups is None:
            groups = ElementTree.SubElement(pattern, 'Groups')
        groups.clear()
        ElementTree.SubElement(groups, 'Item', dict(Number='41', X='1', Y='2'))
        pattern.find('Pads/Pad').set('Group', '41')
        document = read(ElementTree.tostring(root, encoding='unicode'), report=ConversionReport())
        self.assertIsNone(document.one('/Board/Components/Component/Pattern').child('Pattern_Groups'))
        current = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
        group = current.one('Pattern_Groups/pt')
        self.assertIs(current.one('Pads/Pad[1]')['Group'], group)
        self.assertEqual((group['Id'], group['X'], group['Y']), (0, 3, -6))
        group['X'] = 12
        self.assertEqual(group.values, (True, 0, 12, -6))
        self.assertIs(document.clone().one(group.path).schema, group.schema)
        document.references.validate()

    def test_placement_only_grouped_style_keeps_one_independent_template_owner(self):
        root = ElementTree.fromstring(source())
        patterns = root.find('Library/Library/Patterns')
        pattern = ElementTree.fromstring(ElementTree.tostring(patterns.find('Pattern')))
        pattern.set('PatternStyle', 'Grouped')
        groups = ElementTree.SubElement(pattern, 'Groups')
        ElementTree.SubElement(groups, 'Item', dict(Number='41', X='1', Y='2'))
        pattern.find('Pads/Pad').set('Group', '41')
        patterns.append(pattern)
        root.find('Board/Components/Component').set('PatternStyle', 'Grouped')
        document = read(ElementTree.tostring(root, encoding='unicode'), report=ConversionReport())
        self.assertIsNone(document.one('/Board/Components/Component/Pattern').child('Pattern_Groups'))
        template = document.one('/Board/CacheLib/Patterns/Pattern')
        self.assertIs(template.one('Pads/Pad[1]')['Group'], template.one('Pattern_Groups/pt'))
        self.assertEqual(template.one('Pattern_Groups/pt')['X'], 3)
        self.assertEqual(len(document.select('/Board/CacheLib/Patterns/Pattern')), 1)
        document.references.validate()
        for format in ('dip', 'asc', 'dipxml'):
            with self.subTest(output=format):
                report = ConversionReport()
                rebuilt = io.parse(io.serialize(document, format=format, report=report),
                                   report=ConversionReport())
                self.assertIsNone(rebuilt.one('/Board/Components/Component/Pattern').child('Pattern_Groups'))
                if format == 'dipxml':
                    current = rebuilt.one('/Board/CacheLib/Patterns/Pattern')
                    self.assertIs(current.one('Pads/Pad[1]')['Group'], current.one('Pattern_Groups/pt'))
                else:
                    self.assertFalse(rebuilt.select('/Board/CacheLib/Patterns/Pattern'))
                    self.assertIn('independent-library-definitions', [notice.rule for notice in report.warnings])
                self.assertIs(document.one('/Board/CacheLib/Patterns/Pattern'), template)
                document.references.validate()

    def test_missing_positive_pin_pad_key_becomes_unassigned_without_positional_fallback(self):
        for key in (1, 5, 999):
            with self.subTest(key=key):
                root = ElementTree.fromstring(source())
                root.find('Library/Components/Component/Part/Pins/Pin').set('PadId', str(key))
                report = ConversionReport()
                document = read(ElementTree.tostring(root, encoding='unicode'), report=report)
                definition = document.one('/Board/CacheLib/Slots/Slot/Definition')
                part, pattern = definition.one('Part'), definition.one('Pattern')
                pin = part.one('Pins/Pin')
                self.assertEqual(pin['Number'], -1)
                self.assertEqual((pin['Name'], pin['StringNumber']), ('A', '1'))
                self.assertEqual(len(pattern.select('Pads/Pad')), 2)
                self.assertFalse(document.references.outgoing(part, role=PIN_PAD_ROLE))
                notices = [n for n in report.notices if n.rule == 'unavailable-symbol-pin-pad']
                self.assertEqual(len(notices), 1)
                self.assertEqual(notices[0].severity, 'warning')
                document.references.validate()

    def test_placement_styles_are_consumed_without_creating_duplicate_cache_definitions(self):
        root = ElementTree.fromstring(source())
        patterns = root.find('Library/Library/Patterns')
        placed = ElementTree.fromstring(ElementTree.tostring(patterns.find('Pattern')))
        placed.set('PatternStyle', 'Placed')
        placed.find('Name').text = 'Placed geometry'
        ElementTree.SubElement(placed, 'Value').text = 'Current default'
        patterns.append(placed)
        component = root.find('Board/Components/Component')
        component.set('PatternStyle', 'Placed')
        component.remove(component.find('Value'))
        document = read(ElementTree.tostring(root, encoding='unicode'), report=ConversionReport())
        self.assertEqual(document.one('/Board/Components/Component/Pattern')['Name'], 'Placed geometry')
        self.assertEqual(document.one('/Board/Components/Component')['Value'], 'Current default')
        self.assertFalse(document.select('/Board/CacheLib/Patterns/Pattern'))
        self.assertEqual(len(document.select('/Board/CacheLib/Slots/Slot/Definition')), 1)
        self.assertEqual(document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')['Name'], 'Package')

    def test_all_multipart_pins_use_the_primary_public_pad_domain(self):
        for linked in (False, True):
            with self.subTest(secondary_pattern=linked):
                root = ElementTree.fromstring(source())
                component = root.find('Library/Components/Component')
                secondary = ElementTree.fromstring(ElementTree.tostring(component.find('Part')))
                secondary.find('Name').text = 'Second section'
                secondary.find('Pins/Pin').set('PadId', '41')
                secondary.find('InternalConnections').clear()
                if linked:
                    patterns = root.find('Library/Library/Patterns')
                    other = ElementTree.fromstring(ElementTree.tostring(patterns.find('Pattern')))
                    other.set('PatternStyle', 'Q')
                    for pad in other.findall('Pads/Pad'):
                        pad.set('Id', str(int(pad.get('Id'))+100))
                    patterns.append(other)
                    secondary.find('Pattern').set('Style', 'Q')
                else:
                    secondary.remove(secondary.find('Pattern'))
                component.append(secondary)
                document = read(ElementTree.tostring(root, encoding='unicode'), report=ConversionReport())
                slot = document.one('/Board/CacheLib/Slots/Slot')
                first, second = slot.children('Definition')
                part = second.one('Part')
                self.assertEqual(part.one('Pins/Pin')['Number'], 2)
                assignment = document.references.outgoing(part, role=PIN_PAD_ROLE)[0]
                self.assertIs(assignment.target, first.one('Pattern/Pads/Pad[2]'))
                if linked:
                    self.assertEqual(second.one('Pattern/Pads/Pad[2]')['Id'], 141)
                else:
                    self.assertIsNone(second.child('Pattern'))
                document.references.validate()

    def test_symbol_without_a_pattern_does_not_acquire_a_synthetic_definition(self):
        root = ElementTree.fromstring(with_unused_pattern(source()))
        part = root.find('Library/Components/Component/Part')
        part.remove(part.find('Pattern'))
        part.find('Pins/Pin').set('PadId','-1')
        part.find('InternalConnections').clear()
        document = read(ElementTree.tostring(root,encoding='unicode'),report=ConversionReport())
        definition = document.one('/Board/CacheLib/Slots/Slot/Definition')
        self.assertIsNone(definition.child('Pattern'))
        self.assertEqual(definition.one('Part/Pins/Pin')['Number'],-1)
        # The unused library template is independent authored content.
        self.assertEqual(document.one('/Board/CacheLib/Patterns/Pattern')['Name'],'Unused package')
        document.references.validate()

    def test_library_font_widths_use_their_own_header_versions_and_units(self):
        for version in ('5.3.4.9','5.3.5.0'):
            with self.subTest(version=version):
                root = ElementTree.fromstring(source(component_units='mil',pattern_units='mm'))
                # Source and library versions deliberately differ. Each nested
                # library owns its own scale and compatibility convention.
                root.set('Version','4.3.0.5')
                library = root.find('Library')
                library.set('Version',version)
                library.find('Library').set('Version',version)
                part = library.find('Components/Component/Part')
                part.find('Pins/Pin/NameFont').set('Width','0.2')
                part.find('Shapes/Shape').set('Type','Text')
                part.find('Shapes/Shape').set('FontWidth','0.2')
                pattern = library.find('Library/Patterns/Pattern')
                pattern.find('Shapes/Shape').set('Type','Text')
                pattern.find('Shapes/Shape').set('FontWidth','0.2')
                dimensions = ElementTree.SubElement(pattern,'Dimensions')
                ElementTree.SubElement(dimensions,'Dimension',dict(Connected1='None',Connected2='None',FontWidth='0.2'))
                document = read(ElementTree.tostring(root,encoding='unicode'),report=ConversionReport())
                definition = document.one('/Board/CacheLib/Slots/Slot/Definition')
                symbol_width,physical_width = ((Decimal('.2'),Decimal('.2')) if version == '5.3.4.9'
                                               else (Decimal('.01524'),Decimal('.6')))
                self.assertEqual(definition.one('Part/Pins/Pin')['NameFontWidth'],symbol_width)
                self.assertEqual(definition.one('Part/Shapes/Shape')['FontWidth'],symbol_width)
                self.assertEqual(definition.one('Pattern/Shapes/Shape')['FontWidth'],physical_width)
                self.assertEqual(definition.one('Pattern/Dimensions/Dimension')['FontWidth'],physical_width)

    def test_template_custom_fields_do_not_become_a_second_placed_field_namespace(self):
        template = '''<AddFields><AddField Name="Order" Text="Template default" Type="Text"/>
          <AddField Name="Template only" Text="Keep in library" Type="Text"/></AddFields>'''
        text = source().replace('<Name>Package</Name>','<Name>Package</Name>'+template)
        for explicit in (False,True):
            with self.subTest(placed_fields=explicit):
                current = text.replace('<Value>10K</Value>','''<Value>10K</Value><AddFields>
                  <AddField Name="Order" Text="Placed value" Type="Text"><Silk Show="Hide"/></AddField>
                  </AddFields>''') if explicit else text
                document = read(current,report=ConversionReport())
                cached = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
                component = document.one('/Board/Components/Component')
                self.assertEqual([(row['Name'],row['Value']) for row in cached.select('UserFields/UserField')],
                                 [('Order','Template default'),('Template only','Keep in library')])
                self.assertIsNone(component.one('Pattern').child('UserFields'))
                fields = component.select('UserFields/UserField')
                self.assertEqual([(row['Name'],row['Value']) for row in fields],
                                 [('Order','Placed value')] if explicit else [])
                if explicit:
                    self.assertEqual(fields[0]['SilkShow'],2)
                    fields[0]['Value'] = 'Edited value'
                    self.assertEqual(cached.one('UserFields/UserField[1]')['Value'],'Template default')
                document.references.validate()

    def test_cache_symbols_geometry_catalogues_and_paths_are_editable_model_data(self):
        document = read(source(), report=ConversionReport())
        board = document.one('/Board')
        slot = board.one('CacheLib/Slots/Slot')
        part = slot.one('Definition/Part')
        pattern = slot.one('Definition/Pattern')
        pin = part.one('Pins/Pin')
        self.assertEqual((slot['LibPath'], slot['VariablePath']), ('parts.lib', 'relative/parts.lib'))
        self.assertEqual((part['Name'], part['RefDes'], part['Width'], part['Height']), ('Template0', 'U', 6, 9))
        self.assertEqual((part['Component_CategoryName'], part.one('Component_CategoryTypes/CategoryType')['Type']),
                         ('Passives', 'Function'))
        self.assertEqual(part.one('Component_CategoryTypes/CategoryType')['SubType'], 'General')
        self.assertEqual((pin['X'], pin['Y'], pin['Number']), (3, -6, 1))
        self.assertEqual(board['DesignCache_Count'], 0)
        self.assertIsNone(part.child('ModelNote'))
        self.assertIs(pin['Group'], part.one('Groups/pt'))
        self.assertIs(part.one('Shapes/Shape')['Group'], pin['Group'])
        links = document.references.outgoing(part, role=PIN_PAD_ROLE)
        self.assertEqual(len(links), 1)
        self.assertIs(links[0].target, pattern.one('Pads/Pad[1]'))
        pair = pattern.one('InternalConnections/IntCon')
        self.assertIs(pair['Pad1'], pattern.one('Pads/Pad[1]'))
        self.assertIs(pair['Pad2'], pattern.one('Pads/Pad[2]'))
        document.references.validate()

    def test_nested_component_pattern_and_board_units_are_independent(self):
        document = read(source(component_units='mil', pattern_units='inch'), report=ConversionReport())
        definition = document.one('/Board/CacheLib/Slots/Slot/Definition')
        self.assertEqual(definition.one('Part/Pins/Pin')['X'], Decimal('.0762'))
        self.assertEqual(definition.one('Part/Pins/Pin')['Y'], Decimal('-.1524'))
        self.assertEqual(definition.one('Pattern/Pads/Pad[1]')['X'], Decimal('76.2'))
        placed = document.one('/Board/Components/Component')
        self.assertEqual(placed['X'], 30)
        self.assertEqual(placed.one('Pattern/Pads/Pad[1]')['X'], Decimal('-60.96'))

    def test_cache_and_placed_geometry_are_independent_and_pin_links_follow_pad_reordering(self):
        document = read(source(), report=ConversionReport())
        part = document.one('/Board/CacheLib/Slots/Slot/Definition/Part')
        pattern = part.parent.one('Pattern')
        first, second = pattern.select('Pads/Pad')
        placed = document.one('/Board/Components/Component/Pattern/Pads/Pad[1]')
        with patch.object(document.root, 'walk', side_effect=AssertionError('global tree scan')), \
                patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
            second.move_to(second.parent, 0)
            self.assertEqual(part.one('Pins/Pin')['Number'], 2)
            first['X'] = 99
            self.assertEqual(placed['X'], Decimal('-2.4'))
        with self.assertRaises(ReferenceError):
            document.remove(first)
        clone = document.clone()
        link = clone.references.outgoing(clone.one('/Board/CacheLib/Slots/Slot/Definition/Part'), role=PIN_PAD_ROLE)[0]
        self.assertIsNot(link.target, first)
        self.assertIs(link.target._owner(), clone)
        document.references.validate()
        clone.references.validate()

    def test_all_component_entries_become_active_slots_without_placed_style_inference(self):
        document = read(source(components=2), report=ConversionReport())
        board = document.one('/Board')
        slots = board.one('CacheLib/Slots').children('Slot')
        self.assertEqual(board['DesignCache_Count'], 1)
        self.assertEqual([node['SlotIndex'] for node in board.select('DesignCache_Links/Link')], [0, 1])
        slots[1].move_to(slots[1].parent, 0)
        self.assertEqual([node['SlotIndex'] for node in board.select('DesignCache_Links/Link')], [1, 0])
        self.assertEqual(len(board.select('Components/Component')), 1)
        document.references.validate()

    def test_unused_pad_style_is_retained_and_typed(self):
        text = source().replace('</PadStyles>', '''<PadStyle Name="Unused" Type="Surface" Side="Top">
          <MainStack Shape="Ellipse" Width="2" Height="4"/></PadStyle></PadStyles>''')
        document = read(text, report=ConversionReport())
        style = document.one('/Board/CacheLib/PadStyles/PadStyle')
        self.assertEqual((style['Name'], style['PadWidth'], style['PadHeight']), ('Unused', 6, 12))
        style['PadWidth'] = 9
        self.assertEqual(style['PadWidth'], 9)

    def test_footprint_template_metadata_survives_separately_from_instance_overrides(self):
        text = source().replace('<Name>Package</Name>', '''<Name>Package</Name>
          <Value>Template value</Value><Manufacturer>Template maker</Manufacturer><Datasheet>template.pdf</Datasheet>''')
        document = read(text, report=ConversionReport())
        pattern = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
        component = document.one('/Board/Components/Component')
        self.assertEqual((pattern['RefDes'], pattern['Value'], pattern['Pattern_Manufacturer'], pattern['Datasheet']),
                         ('U', 'Template value', 'Template maker', 'template.pdf'))
        self.assertEqual((component['Value'], component['Manufacturer']), ('10K', 'Template maker'))
        self.assertIsNone(component.one('Pattern').child('Value'))
        pattern['Value'] = 'New template value'
        self.assertEqual(component['Value'], '10K')

    def test_standalone_templates_have_the_same_editable_geometry_and_local_references(self):
        text = source(components=0).replace('<Pads><Pad Id="17"', '''<Groups><Item Id="31" X="1" Y="2"/></Groups>
          <Pads><Pad Group="31" Id="17"''', 1)
        text = text.replace('</Shapes>', '''</Shapes><Dimensions>
          <Dimension Id="4" Type="Horizontal" Connected1="Pad" SubObject1="17" Point1="0"
              Connected2="None"/></Dimensions>''', 1)
        document = read(with_unused_pattern(text), report=ConversionReport())
        board = document.one('/Board')
        self.assertEqual({item['Name'] for item in board.select('CacheLib/Patterns/Pattern')},
                         {'Package', 'Unused package'})
        pattern = board.one('CacheLib/Patterns/Pattern', where=lambda item: item['Name'] == 'Unused package')
        first, second = pattern.select('Pads/Pad')
        dimension = pattern.one('Dimensions/Dimension')
        self.assertIs(pattern.schema, library_records.PATTERN)
        self.assertIs(first.schema, library_records.PAD)
        self.assertIs(first['Group'], pattern.one('Pattern_Groups/pt'))
        link = document.references.outgoing(dimension, role='pattern-dimension-1')[0]
        self.assertIs(link.target, first)
        self.assertEqual(board['DesignCache_Count'], -1)
        self.assertEqual(board.select('CacheLib/Slots/Slot'), [])
        with patch.object(document.root, 'walk', side_effect=AssertionError('global tree scan')), \
                patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
            second.move_to(second.parent, 0)
            self.assertEqual(dimension['SubObject1'], 2)
            first['X'] = 44
        self.assertEqual(board.one('Components/Component/Pattern/Pads/Pad[1]')['X'], Decimal('-2.4'))
        with self.assertRaises(ReferenceError):
            first.detach()
        copied = document.copy(pattern, parent=pattern.parent)
        copied_link = document.references.outgoing(copied.one('Dimensions/Dimension'), role='pattern-dimension-1')[0]
        self.assertIs(copied_link.target, copied.one('Pads/Pad[2]'))
        self.assertIs(copied.one('Pads/Pad[2]')['Group'], copied.one('Pattern_Groups/pt'))
        with self.assertRaises(ReferenceError):
            copied.one('Pads/Pad[2]')['Group'] = first['Group']
        clone = document.clone()
        cloned_pattern = clone.one(pattern.path)
        self.assertIs(clone.references.outgoing(cloned_pattern.one('Dimensions/Dimension'),
            role='pattern-dimension-1')[0].target, cloned_pattern.one('Pads/Pad[2]'))
        document.references.validate()
        clone.references.validate()

    def test_unreferenced_template_is_kept_alongside_component_definitions(self):
        text = source().replace('</Patterns>', '''<Pattern PatternStyle="Unused" Type="Free" RefDes="J">
          <Name>Spare package</Name><Value>Socket</Value><DefPad Style="S"/>
          <Pads><Pad Id="55" Style="S" X="7" Y="8"><Number>A</Number></Pad></Pads>
          </Pattern></Patterns>''')
        document = read(text, report=ConversionReport())
        standalone = document.one('/Board/CacheLib/Patterns/Pattern')
        self.assertEqual((standalone['Name'], standalone['RefDes'], standalone['Value']), ('Spare package', 'J', 'Socket'))
        self.assertEqual(standalone.one('Pads/Pad')['StringNumber'], 'A')
        self.assertEqual(len(document.select('/Board/CacheLib/Slots/Slot')), 1)
        standalone.one('Pads/Pad')['StringNumber'] = 'B'
        document.references.validate()

    def test_internal_connections_can_be_authored_on_standalone_templates(self):
        document = read(with_unused_pattern(source(components=0)), report=ConversionReport())
        pattern = document.one('/Board/CacheLib/Patterns/Pattern')
        first, second = pattern.select('Pads/Pad')
        pair = pattern.one('InternalConnections').add('IntCon')
        pair['Pad1'], pair['Pad2'] = first, second
        second.move_to(second.parent, 0)
        self.assertEqual((pair['X'], pair['Y']), (2, 1))
        cached = document.one('/Board/Components/Component/Pattern/Pads/Pad[1]')
        with self.assertRaises(ReferenceError):
            pair['Pad1'] = cached
        self.assertIs(pair['Pad1'], first)
        copied = document.copy(pattern, parent=pattern.parent)
        self.assertIs(copied.one('InternalConnections/IntCon')['Pad1'], copied.one('Pads/Pad[2]'))
        document.references.validate()

    def test_missing_references_and_unmapped_root_data_do_not_silently_disappear(self):
        for text in (source().replace('<Pattern Style="P"/>', '<Pattern Style="missing"/>'),
                     source().replace('</Source>', '<UnknownSection/></Source>'),
                     source().replace('Type="DipTrace-ComponentLibrary"', 'Type="OtherLibrary"')):
            with self.assertRaises(ValueError):
                read(text, report=ConversionReport())


if __name__ == '__main__':
    unittest.main()
