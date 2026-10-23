"""Hierarchy data uses component identities, distinct pin names and page links."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lib.design import (new_schematic, parse_dch, parse_dchxml,
                             DchXmlExportContext)
from lib.design.dchxml import set_attribute
from lib.design.markings import MarkingStyle
from lib.design.schematic_objects import new_symbol, new_pin
from lib.design.schematic_refs import bind_schematic_references


class HierarchyTests(unittest.TestCase):
    def design(self):
        document = new_schematic()
        pages = document.one('/Schematic/Pages')
        target_page = pages.children()[0].clone()
        target_page.set_argument(0, 'Internal')
        target_page.set_field('PageType', 1)
        target_page.set_field('PageHiddenId', 77)
        pages.append(target_page)
        components = document.one('/Schematic/Components')
        target = components.append(new_symbol('Port', 'PORT'))
        target.set_field('Number', 12)
        target.set_field('PartType', 3)
        target.set_field('Page', 1)
        target.one('Pins').append(new_pin())
        block = components.append(new_symbol('Block', 'HB1'))
        for name, value in (('Number', 20), ('PartType', 4), ('Number1', 1), ('PageHiddenId', 77)):
            block.set_field(name, value)
        pin = block.one('Pins').append(new_pin())
        pin.set_field('Number', 12)
        pin.set_field('StringNumber', 'PORT')
        pin.set_field('ModelSig', 'independent spice signal')
        # A hierarchy connector may retain a group value without a group record.
        pin.set_field('Group', 0)
        bind_schematic_references(document)
        return document, target, block, pin, target_page

    def test_saved_keys_binary_identity_and_page_rename_reorder(self):
        document, target, block, pin, page = self.design()
        self.assertEqual(document.references.issues, [])
        original = document.to_dch_bytes()
        loaded = parse_dch(original)
        self.assertEqual(loaded.to_dch_bytes(), original)
        self.assertEqual(loaded.references.issues, [])
        self.assertEqual(pin.scalar('Number'), 12)
        target.set_argument(1, 'RENAMED')
        target.move_to(target.parent, 1)
        page.move_to(page.parent, 0)
        page.set_field('PageHiddenId', 123)
        document.rebuild()
        self.assertEqual((pin.scalar('Number'), pin.scalar('StringNumber')), (1, 'RENAMED'))
        self.assertEqual(pin.scalar('ModelSig'), 'independent spice signal')
        self.assertEqual((block.scalar('Number1'), block.scalar('PageHiddenId')), (0, 123))
        copied = document.clone()
        copied.one('/Schematic/Components/Part[@1="RENAMED"]').set_argument(1, 'COPY')
        copied.rebuild()
        self.assertEqual(copied.one('/Schematic/Components/Part[@1="HB1"]/Pins/Pin').scalar('StringNumber'), 'COPY')
        self.assertEqual(pin.scalar('StringNumber'), 'RENAMED')

    def test_xml_hierarchy_definitions_rekey_and_import_without_repairing_groups(self):
        document, target, block, pin, page = self.design()
        context = DchXmlExportContext(units='mil', grid_snap=True, marking_style=MarkingStyle(font_name='Arial'))
        raw = parse_dchxml(document.to_dchxml_bytes(context=context))
        refs = [r for r in raw.references if r.role == 'xml-hierarchy-connector']
        self.assertGreaterEqual(len(refs), 1)
        connector = raw.one('/Source/Schematic/Components/Part[RefDes="PORT"]')
        set_attribute(connector, 'Id', 999)
        connector.set_field('RefDes', 'PUBLIC_PORT')
        raw.rebuild()
        for ref in refs:
            self.assertEqual(ref.target, connector)
            self.assertEqual(ref.source.one('Pins/Pin').scalar('PadId'), 999)
            self.assertEqual(ref.source.one('Pins/Pin').scalar('PadNumber'), 'PUBLIC_PORT')
        normalized = raw.as_schematic()
        own = normalized.one('/Schematic/Components/Part[@1="HB1"]/Pins/Pin')
        self.assertEqual((own.scalar('Number'), own.scalar('StringNumber')), (0, 'PUBLIC_PORT'))
        self.assertEqual(own.scalar('ModelSig'), 'independent spice signal')
        self.assertEqual(own.scalar('Group'), -1)
        self.assertEqual(own.one('UnresolvedKeys/Key').values, ('Group', 0))
        self.assertTrue(any(issue.message.startswith('symbol-group:') for issue in normalized.references.issues))
        # XML keeps the missing public key without assigning a different group.
        emitted = parse_dchxml(normalized.to_dchxml_bytes(context=context))
        definitions = [r.source for r in emitted.references if r.role == 'xml-hierarchy-connector']
        self.assertTrue(definitions)
        self.assertTrue(all(p.one('Pins/Pin').scalar('Group') == 0 for p in definitions))
        self.assertEqual(pin.scalar('Number'), 12)
        self.assertEqual(target.values[1], 'PORT')
        self.assertEqual(pin.scalar('StringNumber'), 'PORT')


if __name__ == '__main__':
    unittest.main()
