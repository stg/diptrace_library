"""Owned constructors work without reference files or an installed application."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib import new_schematic, parse_dch, parse_dchxml, DchXmlExportContext
from lib.schematic.layout.markings import (MarkingStyle)
from lib.schematic.model.objects import (new_symbol, new_pin)
from lib.schematic.model.refs import (bind_schematic_references)


class NewSchematicTests(unittest.TestCase):
    def test_blank_and_component_data_reconstruct_from_owned_facts(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('fixture/template access')):
            document = new_schematic(sheet_name='Programmatic work')
            part = new_symbol('Connector', 'J1')
            part.one('Pins').append(new_pin())
            document.one('/Schematic/Components').append(part)
            bind_schematic_references(document)
            data = document.to_dch_bytes()
        result = parse_dch(data)
        self.assertTrue(result.complete)
        self.assertEqual(result.references.issues, [])
        self.assertEqual(result.to_dch_bytes(), data)
        self.assertEqual(result.one('/Schematic/Components/Part').values, ('Connector', 'J1'))

    def test_empty_schematic_supports_all_binary_targets_and_public_xml(self):
        document = new_schematic()
        for version in (46, 47, 48):
            data = document.to_dch_bytes(version=version)
            self.assertEqual(parse_dch(data).to_dch_bytes(version=version), data)
        context = DchXmlExportContext(units='mm', grid_snap=True, marking_style=MarkingStyle())
        self.assertEqual(parse_dchxml(document.to_dchxml_bytes(context=context)).references.issues, [])


if __name__ == '__main__':
    unittest.main()
