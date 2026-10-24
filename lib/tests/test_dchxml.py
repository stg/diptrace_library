"""XML data fidelity, ordinary edits and identity-safe key/position links."""
from decimal import Decimal
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib import parse_dchxml, Key, ReferenceError, Value, ExportReport
from lib.schematic.formats.dchxml.syntax import (set_attribute)


TEXT = """<?xml version="1.0" encoding="utf-8"?>
<Source Type="DipTrace-Schematic" Version="4.3.0.5" Units="mil">
<Library Type="DipTrace-ComponentLibrary">
<Library Type="DipTrace-PatternLibrary">
<PadStyles><PadStyle Name="PadT0" Type="Surface"><MainStack Shape="Rectangle" Width="10" Height="20"/></PadStyle></PadStyles>
<Patterns><Pattern PatternStyle="PatType0"><Name>Footprint</Name><DefPad Style="PadT0"/><Pads><Pad Id="1" Style="PadT0" X="0" Y="0"><Number>001</Number></Pad></Pads></Pattern></Patterns>
</Library>
<Components><Component ComponentStyle="CompType0"><Part><Name>Symbol</Name><Pins><Pin PadId="1"/></Pins><Pattern Style="PatType0"/></Part></Component></Components>
</Library>
<Schematic>
<SheetSettings><Sheets><Sheet><Id>7</Id><Name>Sheet 1</Name></Sheet></Sheets></SheetSettings>
<NetClasses><NetClass Id="5"><Name>Default</Name></NetClass></NetClasses>
<Components>
<Part Id="12" ComponentStyle="CompType0" ComponentPart="0" Sheet="7" X="1.2500" Y="-2" Locked="N"><RefDes>R1</RefDes><Value>1k</Value><Pins><Pin NetId="90"/><Pin NetId="-1"/></Pins></Part>
<Part Id="35" ComponentStyle="CompType0" ComponentPart="0" Sheet="7" X="5" Y="-2"><RefDes>R2</RefDes><Pins><Pin NetId="90"/></Pins></Part>
</Components>
<Nets><Net Id="90" NetClass="5"><Name>Signal</Name>
<Pins><Item Part="12" Pin="0"/><Item Part="35" Pin="0"/></Pins>
<Wires>
<Wire Id="3" Sheet="7" Connected1="Pin" Object1="12" SubObject1="0" Connected2="Pin" Object2="35" SubObject2="0"><Points><Point X="1.25" Y="-2" Dir="0"/><Point X="5" Y="-2" Dir="0"/></Points></Wire>
<Wire Id="8" Sheet="7" Connected1="Wire" Bus1="90" Object1="3" SubObject1="1" Connected2="Free"><Points><Point X="3" Y="-2" Dir="0"/><Point X="3" Y="5" Dir="1"/></Points></Wire>
</Wires></Net></Nets>
</Schematic>
</Source>"""


def signature(node):
    return node.tag, tuple(node.attrib.items()), node.text or '', tuple(
        (signature(child), child.tail or '') for child in node)


def remove_layout(node):
    if len(node) and not (node.text or '').strip():
        node.text = None
    for child in node:
        if not (child.tail or '').strip():
            child.tail = None
        remove_layout(child)
    return node


class DchXmlTests(unittest.TestCase):
    def test_comment_and_instruction_edits_validate_xml_characters(self):
        for kind in ('Comment', 'ProcessingInstruction'):
            for text in ('bad\x00value', 'bad\ud800value', 'bad\ufffevalue'):
                with self.subTest(kind=kind, text=repr(text)):
                    document = parse_dchxml('<Source Type="DipTrace-Schematic"><!--keep--><?record keep?></Source>')
                    node = document.one('/Source/'+kind)
                    values = ('record', text) if kind == 'ProcessingInstruction' else (text,)
                    node.set_values(*values)
                    report = ExportReport()
                    with self.assertRaisesRegex(ValueError, 'outside XML 1.0'):
                        document.to_dchxml_bytes(report=report)
                    self.assertEqual(len(report.errors), 1)
                    self.assertEqual(node.values, values)
                    node.set_values(*(('record', 'valid \U0001f600\ttext') if kind == 'ProcessingInstruction'
                                      else ('valid \U0001f600\ttext',)))
                    reloaded = parse_dchxml(document.to_dchxml_bytes())
                    self.assertEqual(reloaded.one('/Source/'+kind).values, node.values)

    def test_comment_and_instruction_edits_validate_structure(self):
        cases = (('Comment', ()), ('Comment', ('one', 'two')), ('Comment', (12,)),
                 ('ProcessingInstruction', ('target',)), ('ProcessingInstruction', ('target', False)))
        for kind, values in cases:
            with self.subTest(kind=kind, values=values):
                document = parse_dchxml('<Source Type="DipTrace-Schematic"><!--keep--><?record keep?></Source>')
                document.one('/Source/'+kind).set_values(*values)
                with self.assertRaisesRegex(ValueError, 'string values and no children'):
                    document.to_dchxml_bytes()
        for kind in ('Comment', 'ProcessingInstruction'):
            document = parse_dchxml('<Source Type="DipTrace-Schematic"><!--keep--><?record keep?></Source>')
            document.one('/Source/'+kind).add('Unexpected')
            with self.assertRaisesRegex(ValueError, 'string values and no children'):
                document.to_dchxml_bytes()

    def test_xml_document_edits_require_one_root_with_surrounding_markup(self):
        text = '<?before keep?><Source Type="DipTrace-Schematic"/><!--after-->'
        original = parse_dchxml(text)
        reloaded = parse_dchxml(original.to_dchxml_bytes())
        self.assertEqual(reloaded.one('/ProcessingInstruction').values, ('before', 'keep'))
        self.assertEqual(reloaded.one('/Comment').values, ('after',))
        for edit in ('duplicate-source', 'sibling', 'outside-text'):
            with self.subTest(edit=edit):
                document = original.clone()
                if edit == 'duplicate-source':
                    document.root.append(document.one('/Source').clone())
                elif edit == 'sibling':
                    document.root.add('Other')
                else:
                    document.root.set_values('outside')
                report = ExportReport()
                with self.assertRaisesRegex(ValueError, 'one Source element'):
                    document.to_dchxml_bytes(report=report)
                self.assertEqual(len(report.errors), 1)
        self.assertEqual(original.to_dchxml_bytes(), reloaded.to_dchxml_bytes())

    def test_unused_style_keys_are_unique_even_without_incoming_references(self):
        document = parse_dchxml('''<Source Type="DipTrace-Schematic"><Library><Library>
        <PadStyles><PadStyle Name="Own"/></PadStyles></Library></Library><Schematic/></Source>''')
        styles = document.one('/Source/Library/Library/PadStyles')
        copied = styles.append(styles.children()[0].clone())
        with self.assertRaisesRegex(ReferenceError, 'duplicate XML Name key'):
            document.to_dchxml_bytes()
        set_attribute(copied, 'Name', 'Other')
        self.assertEqual(parse_dchxml(document.to_dchxml_bytes()).references.issues, [])
        set_attribute(copied, 'Name', 123)
        with self.assertRaisesRegex(ReferenceError, 'Name requires a string'):
            document.to_dchxml_bytes()

    def test_pad_keys_are_unique_within_each_footprint(self):
        document = parse_dchxml('''<Source Type="DipTrace-Schematic"><Library><Library><Patterns>
        <Pattern PatternStyle="P1"><Pads><Pad Id="1"/></Pads></Pattern>
        <Pattern PatternStyle="P2"><Pads><Pad Id="1"/></Pads></Pattern>
        </Patterns></Library></Library><Schematic/></Source>''')
        document.to_dchxml_bytes()
        pads = document.one('/Source/Library/Library/Patterns/Pattern[1]/Pads')
        pads.append(pads.children()[0].clone())
        with self.assertRaisesRegex(ReferenceError, 'duplicate XML Id key'):
            document.to_dchxml_bytes()

    def test_known_numeric_and_boolean_edits_cannot_emit_unreadable_xml(self):
        cases = (
            ('<Schematic><Shapes><Shape X="1"/></Shapes></Schematic>', '//Shape/X', 'wrong', 'number'),
            ('<Schematic><Shapes><Shape Locked="N"/></Shapes></Schematic>', '//Shape/Locked', 'N', 'boolean'),
            ('<Schematic><SheetSettings><Sheets><Sheet><Scale>1</Scale></Sheet></Sheets></SheetSettings></Schematic>', '//Sheet/Scale', '1', 'number'),
            ('<Schematic><SheetSettings><DisplaySheet>Y</DisplaySheet></SheetSettings></Schematic>', '//DisplaySheet', 1, 'boolean'),
        )
        for content, path, value, kind in cases:
            with self.subTest(path=path):
                document = parse_dchxml('<Source Type="DipTrace-Schematic">'+content+'</Source>')
                document.one(path).set_values(value)
                with self.assertRaisesRegex(ValueError, 'expected an XML '+kind):
                    document.to_dchxml_bytes()

    def test_active_sheet_follows_position_while_sheet_links_follow_public_keys(self):
        document = parse_dchxml('''<Source Type="DipTrace-Schematic"><Schematic>
        <SheetSettings><ActiveSheet>0</ActiveSheet><Sheets>
        <Sheet><Id>12</Id><Name>A</Name></Sheet><Sheet><Id>20</Id><Name>B</Name></Sheet>
        </Sheets></SheetSettings><Shapes><Shape Id="0" Sheet="12"/></Shapes>
        </Schematic></Source>''')
        self.assertEqual(document.references.issues, [])
        settings = document.one('/Source/Schematic/SheetSettings')
        sheets = settings.one('Sheets')
        sheets.children('Sheet')[0].move_to(sheets, 1)
        document.rebuild()
        self.assertEqual(settings.scalar('ActiveSheet'), 1)
        self.assertEqual(document.one('/Source/Schematic/Shapes/Shape').scalar('Sheet'), 12)
        sheets.children('Sheet')[1].set_field('Id', 121)
        document.rebuild()
        self.assertEqual(settings.scalar('ActiveSheet'), 1)
        self.assertEqual(document.one('/Source/Schematic/Shapes/Shape').scalar('Sheet'), 121)

    def test_library_group_keys_follow_identity_with_local_scope(self):
        source = TEXT.replace('<Pads><Pad Id="1"', '<Groups><Item Id="5" X="0" Y="0"/></Groups><Pads><Pad Group="5" Id="1"', 1)
        document = parse_dchxml(source)
        pattern = document.one('/Source/Library/Library/Patterns/Pattern')
        group = pattern.one('Groups/Item')
        group.set_field('Id', 51)
        document.rebuild()
        self.assertEqual(pattern.one('Pads/Pad').scalar('Group'), 51)
        other = pattern.parent.add('Pattern')
        set_attribute(other, 'PatternStyle', 'Other')
        target = other.add('Groups').add('Item')
        set_attribute(target, 'Id', 52)
        reference = document.references.outgoing(pattern.one('Pads/Pad'), role='xml-pattern-group')[0]
        document.references.retarget(reference, target)
        with self.assertRaisesRegex(ReferenceError, 'outside its local footprint'):
            document.rebuild()

    def test_shape_pad_key_follows_identity_and_rejects_another_footprint(self):
        document = parse_dchxml(TEXT.replace('</Pads></Pattern>',
            '</Pads><Shapes><Shape Id="4" PadId="1"/></Shapes></Pattern>'))
        pattern = document.one('/Source/Library/Library/Patterns/Pattern')
        pad = pattern.one('Pads/Pad')
        shape = pattern.one('Shapes/Shape')
        reference = document.references.outgoing(shape, role='xml-pattern-shape-pad')[0]
        set_attribute(pad, 'Id', 41)
        document.rebuild()
        self.assertEqual(shape.scalar('PadId'), 41)
        other = pattern.parent.add('Pattern')
        set_attribute(other, 'PatternStyle', 'Other')
        target = other.add('Pads').add('Pad')
        set_attribute(target, 'Id', 42)
        document.references.retarget(reference, target)
        with self.assertRaisesRegex(ReferenceError, 'outside its local footprint'):
            document.rebuild()

    def test_dimension_attachments_follow_public_ids_and_keep_anchor_choices(self):
        source = TEXT.replace('</Pads>', '</Pads><Shapes><Shape Id="9"/></Shapes><Dimensions><Dimension Connected1="Pad" Object1="0" SubObject1="1" Point1="8" Connected2="Shape" Object2="0" SubObject2="9" Point2="2"/></Dimensions>', 1)
        document = parse_dchxml(source)
        self.assertEqual(document.references.issues, [])
        pattern = document.one('/Source/Library/Library/Patterns/Pattern')
        pattern.one('Pads/Pad/Id').set_values(42)
        pattern.one('Shapes/Shape/Id').set_values(91)
        document.rebuild()
        dimension = pattern.one('Dimensions/Dimension')
        self.assertEqual(tuple(dimension.scalar(name) for name in ('SubObject1', 'Point1', 'SubObject2', 'Point2')), (42, 8, 91, 2))
        reloaded = parse_dchxml(document.to_dchxml_bytes())
        self.assertEqual(reloaded.references.issues, [])
        with self.assertRaises(ReferenceError):
            pattern.one('Pads/Pad').detach()
        document.validate()

    def test_extension_names_remain_searchable_and_editable(self):
        document = parse_dchxml('<Source Type="DipTrace-Schematic"><Vendor.Extension custom-name="raw"><Extra-Value>01</Extra-Value></Vendor.Extension></Source>')
        field = document.one('/Source/Vendor.Extension[custom-name="raw"]/Extra-Value')
        self.assertEqual(field.values, ('01',))
        field.set_values('02')
        set_attribute(field.parent, 'custom-name', 'edited')
        reloaded = parse_dchxml(document.to_dchxml_bytes())
        self.assertEqual(reloaded.one('/Source/Vendor.Extension[custom-name="edited"]/Extra-Value').values, ('02',))
        with self.assertRaises(ValueError):
            Value.of('bad-name', symbol=True)

    def test_all_data_is_owned_typed_and_regenerated(self):
        document = parse_dchxml(TEXT)
        self.assertEqual(document.references.issues, [])
        part = document.one('/Source/Schematic/Components/Part[RefDes="R1"]')
        self.assertEqual(part.scalar('X'), Decimal('1.2500'))
        self.assertIs(part.scalar('Locked'), False)
        self.assertEqual(document.one('//Number').values, ('001',))
        self.assertIsNone(document._source_bytes)
        self.assertIsNone(document._source_text)
        self.assertFalse(document.root.changed)
        self.assertEqual(
            signature(remove_layout(ET.fromstring(TEXT))),
            signature(remove_layout(ET.fromstring(document.to_dchxml_bytes()))))

    def test_edits_reorder_and_key_changes_keep_targets(self):
        document = parse_dchxml(TEXT)
        part = document.one('/Source/Schematic/Components/Part[RefDes="R1"]')
        original_pin = part.one('Pins/Pin[1]')
        part.move_to(part.parent, 1)
        original_pin.move_to(original_pin.parent, 1)
        part.set_field('Id', 99)
        part.set_field('Value', '220 Ω & <sample>')
        set_attribute(part, 'Angle', Decimal('1.5708'))
        document.one('/Source/Schematic/Nets/Net/Id').set_values(100)
        document.one('/Source/Schematic/Nets/Net/Wires/Wire[1]/Id').set_values(13)
        document.one('/Source/Library/Components/Component/ComponentStyle').set_values('RenamedStyle')
        document.rebuild()
        member = document.one('/Source/Schematic/Nets/Net/Pins/Item[1]')
        wire = document.one('/Source/Schematic/Nets/Net/Wires/Wire[1]')
        branch = document.one('/Source/Schematic/Nets/Net/Wires/Wire[2]')
        self.assertEqual(member.values, ())
        self.assertEqual((member.scalar('Part'), member.scalar('Pin')), (99, 1))
        self.assertEqual((wire.scalar('Object1'), wire.scalar('SubObject1')), (99, 1))
        self.assertEqual((branch.scalar('Bus1'), branch.scalar('Object1')), (100, 13))
        self.assertEqual(original_pin.scalar('NetId'), 100)
        reread = parse_dchxml(document.to_dchxml_bytes())
        edited = reread.one('/Source/Schematic/Components/Part[RefDes="R1"]')
        self.assertEqual(edited.scalar('Value'), '220 Ω & <sample>')
        self.assertEqual(edited.scalar('ComponentStyle'), 'RenamedStyle')
        self.assertEqual(edited.scalar('Angle'), Decimal('1.5708'))
        self.assertEqual(reread.references.issues, [])

    def test_unknown_fields_mixed_text_whitespace_and_comments_survive(self):
        text = """<Source Type="DipTrace-Schematic" Version="future" Units="mm">
<!--keep--><?record sample?>
<Extension Code="001"><Name>N</Name><Value> </Value><Note>A <Emphasis X="1"> B </Emphasis> C</Note></Extension>
</Source>"""
        document = parse_dchxml(text)
        extension = document.one('/Source/Extension')
        self.assertEqual(extension.scalar('Code'), '001')
        self.assertEqual(extension.scalar('Value'), ' ')
        self.assertEqual(extension.scalar('Name'), 'N')
        extension.set_field('Code', '002')
        data = document.to_dchxml_bytes()
        self.assertIn(b'<!--keep-->', data)
        self.assertIn(b'<?record sample?>', data)
        reread = parse_dchxml(data)
        self.assertEqual(reread.one('/Source/Extension/Code').values, ('002',))
        self.assertEqual(reread.one('/Source/Extension/Note').values, ('A ', ' C'))
        self.assertEqual(reread.one('//Emphasis').values, (' B ',))

    def test_clone_keeps_key_graph_independent(self):
        document = parse_dchxml(TEXT)
        copied = document.clone()
        copied.one('/Source/Schematic/Components/Part[1]/Id').set_values(101)
        copied.rebuild()
        self.assertEqual(copied.one('/Source/Schematic/Nets/Net/Pins/Item[1]/Part').values, (101,))
        self.assertEqual(document.one('/Source/Schematic/Nets/Net/Pins/Item[1]/Part').values, (12,))

    def test_definition_pin_pad_keys_follow_pad_identifier_edits(self):
        document=parse_dchxml(TEXT)
        document.one('/Source/Library/Library/Patterns/Pattern/Pads/Pad/Id').set_values(41)
        document.rebuild()
        pin=document.one('/Source/Library/Components/Component/Part/Pins/Pin')
        self.assertEqual(pin.scalar('PadId'),41)
        self.assertEqual(parse_dchxml(document.to_dchxml_bytes()).references.issues,[])

    def test_stale_pad_identifiers_are_preserved_until_explicitly_bound(self):
        document = parse_dchxml(TEXT.replace('PadId="1"', 'PadId="999"'))
        pin = document.one('/Source/Library/Components/Component/Part/Pins/Pin')
        pad = document.one('/Source/Library/Library/Patterns/Pattern/Pads/Pad')
        self.assertEqual(len(document.references.issues), 1)
        self.assertIn('PadId="999"', document.to_dchxml())
        document.one('/Source/Schematic/Components/Part[1]').set_field('Value', 'changed')
        self.assertIn('PadId="999"', document.to_dchxml())
        part = document.one('/Source/Schematic/Components/Part[1]')
        part.move_to(part.parent, 1)
        document.rebuild()
        copied = document.clone()
        self.assertEqual(copied.references.issues[0].collections,
                         (copied.one('/Source/Library/Library/Patterns/Pattern/Pads'),))
        self.assertIn('PadId="999"', copied.to_dchxml())
        pin.one('PadId').set_values(888)
        with self.assertRaisesRegex(ReferenceError, 'unresolved reference was edited'):
            document.to_dchxml()
        document.references.bind(pin, pad, Key(pin.one('PadId')), role='xml-definition-pin-pad')
        self.assertEqual(document.references.issues, [])
        document.rebuild()
        self.assertEqual(pin.scalar('PadId'), 1)
        reloaded = parse_dchxml(document.to_dchxml_bytes())
        self.assertEqual(reloaded.references.issues, [])

    def test_invalid_inputs_and_explicit_normalization_boundary(self):
        for text in [
            '<Source Type="other"/>',
            '<Source Type="DipTrace-Schematic"><Item X="invalid"/></Source>',
            '<Source Type="DipTrace-Schematic"><Item Locked="maybe"/></Source>',
            '<!DOCTYPE Source [<!ENTITY a "x">]><Source Type="DipTrace-Schematic"/>',
            '<Source Type="DipTrace-Schematic">',
        ]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_dchxml(text)
        document = parse_dchxml(TEXT)
        with self.assertRaisesRegex(ValueError, 'as_schematic'):
            document.to_asc()
        with self.assertRaisesRegex(ValueError, 'complete shared schematic'):
            document.to_dch_bytes()


if __name__ == '__main__':
    unittest.main()
