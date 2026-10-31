"""The PCB catalogue describes the same records used by imported and new data."""
import unittest

from lib.common.conversion import ConversionReport
from lib.common.local_keys import map_key, UNRESOLVED_KEY, UNRESOLVED_KEYS
from lib.pcb.formats import io
from lib.pcb.model.catalogue import pcb_schema
from lib.pcb.model.definitions import DOCUMENT, establish_records
from lib.pcb.model.objects import new_component, new_pattern_drawing
from lib.pcb.model import table_records
from lib.pcb.tests.test_dip_output import configured_document
from lib.pcb.tests.test_dipxml_library import source as library_source
from lib.pcb.tests.test_dipxml_pairs import source as pair_source
from lib.pcb.tests.test_xml_routing_output import with_component_library


class PcbCatalogueTests(unittest.TestCase):
    def test_catalogue_is_cached_immutable_and_closed_over_child_types(self):
        catalogue = pcb_schema()
        self.assertIs(catalogue, pcb_schema())
        self.assertIs(catalogue[DOCUMENT.name], DOCUMENT)
        self.assertIs(catalogue['PcbTable'], table_records.TABLE)
        with self.assertRaises(TypeError):
            catalogue['Extra'] = DOCUMENT
        for record in catalogue.values():
            for child in record.children.values():
                for name in child.record.split('|'):
                    self.assertIn(name, catalogue, (record.name, child.name))

    def test_imported_records_and_owned_children_match_the_catalogue(self):
        catalogue = pcb_schema()
        documents = (configured_document(), io.parse(library_source(), report=ConversionReport()),
                     io.parse(with_component_library(pair_source()), report=ConversionReport()))
        for document in documents:
            for node in document.root.walk(include_self=True):
                if node.schema is None:
                    continue
                with self.subTest(record=node.schema.name, path=node.path):
                    self.assertIs(catalogue[node.schema.name], node.schema)
                    if node.parent is not None and node.parent.schema is not None:
                        child = node.parent.schema.children.get(node.kind)
                        if child is not None:
                            self.assertIn(node.schema.name, child.record.split('|'))

    def test_shared_missing_key_data_is_named_and_editable_in_pcb(self):
        component = new_component('Example', 'U1')
        shape = component.one('Pattern/Shapes').append(new_pattern_drawing(kind=1))
        self.assertEqual(map_key(shape, 'PadId', 404, {}), -1)
        establish_records(component)
        keys = shape.one('UnresolvedKeys')
        key = keys.one('Key')
        self.assertIs(keys.schema, UNRESOLVED_KEYS)
        self.assertIs(key.schema, UNRESOLVED_KEY)
        self.assertEqual((key['Field'], key['Id']), ('PadId', 404))
        key['Id'] = 405
        self.assertEqual(key['Id'], 405)

    def test_placed_internal_pairs_have_one_documented_owner(self):
        component = new_component('Example', 'U1')
        pattern = component.one('Pattern')
        self.assertIsNone(pattern.child('InternalConnections'))
        self.assertNotIn('InternalConnections', pattern.schema.children)
        self.assertIn('IntConRecords', component.schema.children)
