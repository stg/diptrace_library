"""Supplied teardrop data shares layer and net identity through ordinary edits."""
import unittest
from unittest.mock import patch

from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.drawing_records import POINT
from lib.common.references import Property, ReferenceError
from lib.common.asc import dumps, loads
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.model import teardrops
from lib.pcb.model.objects import new_net, new_trace
from lib.pcb.tests.test_dipxml_classes import source as xml_source
from lib.pcb.tests.test_dipxml_electrical import prepared
from lib.pcb.tests.test_asc_graphics import fixture as asc_source
from lib.pcb.tests.test_asc_routing import TRACE as ASC_TRACE


def design(text=None):
    return assemble_graphics(prepared(text or xml_source()))


class TeardropTests(unittest.TestCase):
    def test_source_keys_are_consumed_into_typed_geometry_layer_and_trace_links(self):
        result = design()
        net = result.rules.routing.core.nets[7]
        polygon = net.one('Teardrops/Teardrop')
        member = net.one('Traces/Trace[1]/ConnectedTeardrops/Item')
        self.assertIs(polygon.schema, teardrops.TEARDROP)
        self.assertIs(member.schema, teardrops.MEMBER)
        self.assertIs(member['Teardrop'], polygon)
        self.assertEqual((member.values, polygon['Id']), ((0,), 0))
        self.assertIsNone(polygon.child('Lay'))
        self.assertIs(polygon['Layer'], result.rules.layers[0])
        vertex = polygon.one('Points/pt[1]')
        self.assertIs(vertex.schema, POINT)
        self.assertEqual(vertex.values, (3, -6))
        self.assertNotIn('Id', vertex.schema.fields)
        result.document.references.validate()

    def test_local_edits_reorder_and_shared_selections_need_no_rebuild_or_geometry_calculation(self):
        result = design()
        document = result.document
        polygon = document.one('/Board/Nets/Net/Teardrops/Teardrop')
        member = document.one('/Board/Nets/Net/Traces/Trace[1]/ConnectedTeardrops/Item')
        duplicate = document.copy(polygon)
        shared = document.copy(member)
        observed = document.root.add('ObservedLayer', -1)
        document.references.bind(observed, polygon, Property(observed, 'Lay'))
        document.copy(result.rules.layers[0], fields={'Name': 'Extra'}, index=0)
        with patch.object(document.root, 'walk', side_effect=AssertionError('global tree scan')), \
                patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
            duplicate.move_to(duplicate.parent, 0)
            polygon.one('Points/pt[1]')['X'] = 17
            self.assertEqual((member['Index'], shared['Index']), (1, 1))
            self.assertEqual(observed.values, (1,))
            self.assertEqual(member.parent.parent.one('Points/Point[1]')['X'], 3)
        document.references.validate()

    def test_foreign_targets_cross_net_edits_removal_copy_and_clone_keep_scope(self):
        result = design()
        document = result.document
        polygon = document.one('/Board/Nets/Net/Teardrops/Teardrop')
        member = document.one('/Board/Nets/Net/Traces/Trace[1]/ConnectedTeardrops/Item')
        other = document.one('/Board/Nets').append(new_net('Other'))
        collection = other.add('Teardrops')
        other_polygon = collection.add('Teardrop')
        with self.assertRaises(ReferenceError):
            member['Teardrop'] = other_polygon
        with self.assertRaises(ReferenceError):
            polygon.move_to(collection)
        with self.assertRaises(ReferenceError):
            document.remove(polygon)
        free_trace = polygon.parent.parent.one('Traces').append(new_trace())
        free_trace.add('ConnectedTeardrops').add('Item')['Teardrop'] = polygon
        with self.assertRaises(ReferenceError):
            free_trace.move_to(other.one('Traces'))
        self.assertIs(free_trace.parent.parent, polygon.parent.parent)
        free_trace.one('ConnectedTeardrops/Item')['Teardrop'] = None
        clone = document.clone()
        copied = clone.one('/Board/Nets/Net[1]/Traces/Trace[1]/ConnectedTeardrops/Item')
        self.assertIsNot(copied['Teardrop'], polygon)
        with self.assertRaises(ReferenceError):
            copied['Teardrop'] = polygon
        member['Teardrop'] = None
        polygon.move_to(collection)
        self.assertIs(polygon.parent, collection)
        document.references.validate()
        clone.references.validate()

    def test_stale_and_negative_link_entries_compact_and_valid_duplicates_remain(self):
        @import_diagnostics('dipxml')
        def read(text):
            return design(text).document
        text = xml_source().replace('<ConnectedTeardrops><Item>77</Item>',
            '<ConnectedTeardrops><Item>77</Item><Item>999</Item><Item>-1</Item><Item>77</Item>')
        report = ConversionReport()
        document = read(text, report=report)
        rows = document.select('/Board/Nets/Net/Traces/Trace[1]/ConnectedTeardrops/Item')
        self.assertEqual([row['Index'] for row in rows], [0, 0])
        self.assertIs(rows[0]['Teardrop'], rows[1]['Teardrop'])
        self.assertTrue(any(n.rule == 'stale-trace-teardrops' for n in report.infos))
        document.references.validate()

    def test_xml_missing_or_negative_counter_uses_current_input_position(self):
        for replacement in ('', 'Id="-1"'):
            text = xml_source().replace('Teardrop Id="77"', 'Teardrop '+replacement).replace('<Item>77</Item>', '<Item>0</Item>')
            row = design(text).document.one('/Board/Nets/Net/Traces/Trace[1]/ConnectedTeardrops/Item')
            self.assertEqual(row['Index'], 0)
            self.assertIsNotNone(row['Teardrop'])

    def test_ascii_net_parameters_and_polygon_coordinates_share_the_model(self):
        data = asc_source()
        net = data.one('/Board/Nets/Net')
        net.add('Teardrop_PadVia', 2)
        net.add('TearDrop_Trace', 2)
        polygon = net.add('Teardrops').add('Teardrop')
        polygon.add('Layer', 1)
        polygon.add('DrawX', 4)
        polygon.add('DrawY', 5)
        polygon.add('Points').add('Point', 1, 2).parent.add('Point', 3, 4)
        loads(ASC_TRACE.replace('(pt 3)', '(pt 0)')).one('Line').move_to(net.one('Lines'))
        result = assemble_graphics(prepare_core(dumps(data, preserve=False)))
        net = result.rules.routing.core.nets[73]
        polygon = net.one('Teardrops/Teardrop')
        self.assertEqual(net.one('TeardropParams')['PadVia'], 2)
        self.assertEqual(net.one('TeardropParams')['Trace'], 2)
        self.assertIsNone(net.child('Teardrop_PadVia'))
        self.assertIsNone(net.child('TearDrop_Trace'))
        self.assertEqual(polygon.one('Points/pt[2]').values, (3, 4))
        self.assertIs(polygon['Layer'], result.rules.layers[1])
        self.assertIs(net.one('Traces/Trace[1]/ConnectedTeardrops/Item')['Teardrop'], polygon)
        result.document.references.validate()

    def test_drc_teardrop_targets_share_the_same_polygon_identity(self):
        errors = '''<DesignErrors><DesignError ObjectType1="Teardrop" Object1="7" SubObject1="77"
            ObjectType2="-1" X="1" Y="2"/></DesignErrors>'''
        result = design(xml_source().replace('</Board>', errors+'</Board>'))
        document = result.document
        error = document.one('/Board/DesignErrors/DesignError')
        polygon = error['Target1']
        self.assertIs(polygon, document.one('/Board/Nets/Net/Teardrops/Teardrop'))
        duplicate = document.copy(polygon)
        duplicate.move_to(duplicate.parent, 0)
        self.assertEqual((error['Object1'], error['SubObject1']), (0, 1))
        self.assertEqual(error['X'], 3)
        document.references.validate()

        @import_diagnostics('dipxml')
        def read(text):
            return design(text).document
        report = ConversionReport()
        document = read(xml_source().replace('</Board>', errors.replace('SubObject1="77"',
            'SubObject1="999"')+'</Board>'), report=report)
        error = document.one('/Board/DesignErrors/DesignError')
        self.assertIsNone(error['Target1'])
        self.assertEqual((error['Object1'], error['SubObject1'], error['Point1']), (-1, -1, -1))
        self.assertEqual(error['X'], 3)
        self.assertTrue(any(n.rule == 'stale-design-error-targets' for n in report.infos))
        document.references.validate()

    def test_new_selection_indices_and_polygon_ids_are_readonly_and_failed_attachment_is_atomic(self):
        result = design()
        document = result.document
        collection = document.one('/Board/Nets/Net/Teardrops')
        members = document.one('/Board/Nets/Net/Traces/Trace[1]/ConnectedTeardrops')
        for parent, kind in ((collection, 'Teardrop'), (members, 'Item')):
            before = parent.children()
            with self.assertRaises(TypeError):
                parent.add(kind, 99)
            self.assertEqual(parent.children(), before)
        polygon = collection.add('Teardrop')
        self.assertIs(polygon.schema, teardrops.TEARDROP)
        self.assertEqual(polygon['Id'], 1)
        with self.assertRaises(TypeError):
            polygon['Id'] = 99
        document.references.validate()


if __name__ == '__main__':
    unittest.main()
