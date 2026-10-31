"""PCB ASC cache output preserves current definitions and local identities."""
from decimal import Decimal
import unittest
from pathlib import Path
from unittest.mock import patch

from lib.common.asc import dumps, loads
from lib.common.conversion import ConversionReport
from lib.common.model import Element
from lib.common.references import ReferenceError
from lib.common.schema import MISSING
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.asc.cache_projection import project_cache
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_asc_core import fixture
from lib.pcb.tests.test_dimension_projection import dimension
from lib.pcb.tests.test_dipxml_library import read, source


def design():
    document = read(source(),report=ConversionReport())
    # These are independent XML template defaults that ASC cannot represent.
    # The matching tests below cover the common representation; omissions get
    # their own test and structured diagnostics.
    pattern = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
    for name in ('RefDes','Value','Datasheet','Sided'):
        if pattern.child(name) is not None:
            del pattern[name]
    for pad in pattern.select('Pads/Pad'):
        if pad.child('Id') is not None:
            del pad['Id']
    for pin in document.select('/Board/CacheLib/Slots/Slot/Definition/Part/Pins/Pin'):
        if pin.child('SignalDelay') is not None:
            del pin['SignalDelay']
    return document


def syntax(document, *, report=None):
    data = loads(fixture())
    for section in tuple(project_cache(document.one('/Board'),report=report).children()):
        section.move_to(data.one('/Board'))
    return data


def reopen(document, *, report=None):
    return assemble_graphics(prepare_core(dumps(syntax(document,report=report),preserve=False))).document


def signature(root):
    def identities(value):
        if isinstance(value, Element):
            return value.path.removeprefix(root.path)
        if isinstance(value, (tuple, list)):
            return tuple(identities(item) for item in value)
        return value
    result = {}
    for node in root.walk(include_self=True):
        if node.schema is None:
            continue
        for name,field in node.schema.fields.items():
            if field.getter is None and node.child(name) is None and field.default is MISSING:
                continue
            try:
                current = node.get(name,None if field.default is MISSING else field.default)
            except ReferenceError:
                current = 'unresolved'
            current = identities(current)
            result[node.path.removeprefix(root.path)+'/'+name] = current
    return result


class CacheProjectionTests(unittest.TestCase):
    def test_cached_drawing_output_preserves_order_with_linear_collection_work(self):
        document = design()
        pattern = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
        shapes = pattern.one('Shapes')
        original = shapes.one('Shape')
        for index in range(80):
            document.copy(original, parent=shapes)['Width'] = Decimal(index)+Decimal('.25')
        expected = [shape['Width'] for shape in shapes.children('Shape')]
        before = signature(pattern)
        scanned = 0
        lookup = Element._stored_child_sequence

        def tracked(node, kind=None):
            nonlocal scanned
            if node.kind in ('Shapes', 'cl_Shapes') and node.schema is None:
                scanned += len(node.items)
            return lookup(node, kind)

        with patch.object(Element, '_stored_child_sequence', tracked):
            projected = project_cache(document.one('/Board'), report=ConversionReport())
        flat = projected.one('CacheLib/cl_Components/cl_Component/cl_Pattern/cl_Shapes')
        self.assertEqual([row.values[16] for row in flat.children('cl_Shape')[1:-1]], expected)
        self.assertLessEqual(scanned, 4*len(flat.items))
        self.assertEqual(signature(pattern), before)

    def test_local_groups_use_the_public_symbol_and_pattern_row_names(self):
        document = design()
        definition = document.one('/Board/CacheLib/Slots/Slot/Definition')
        part, pattern = definition.one('Part'), definition.one('Pattern')
        group = document.copy(part.one('Groups/pt'), parent=pattern.one('Pattern_Groups'))
        pattern.one('Pads/Pad[1]')['Group'] = group
        projected = project_cache(document.one('/Board'), report=ConversionReport())
        self.assertTrue(projected.select('CacheLib/cl_Components/cl_Component/cl_Part/cl_Groups/cl_Group'))
        self.assertTrue(projected.select('CacheLib/cl_Components/cl_Component/cl_Pattern/cl_Pattern_Groups/cl_Pattern_Group'))
        rebuilt = reopen(document, report=ConversionReport())
        current = rebuilt.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
        self.assertIs(current.one('Pads/Pad[1]')['Group'], current.one('Pattern_Groups/pt'))

    def test_cached_holes_dimensions_terminals_and_paste_follow_current_geometry(self):
        document = design()
        pattern = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
        group = pattern.one('Pattern_Groups').add('pt')
        group['Enabled'],group['X'],group['Y'] = True,2,3
        hole = pattern.one('Holes').add('Hole',True,False,7,8,3,1)
        hole['Group'] = group
        document.copy(hole,parent=hole.parent)['X'] = 9
        pad = pattern.one('Pads/Pad[1]')
        pad['Group'] = group
        pad['PadShape_New'] = 3
        pad.one('PadPoints_New').add('pt',5,6)
        for owner in (pattern,pad):
            terminal = owner.add('PadTerminal',0)
            for name,current in dict(Type=3,X=1,Y=2,Angle=Decimal('.4'),ShapeWidth=3,
                                     ShapeHeight=4,ShapeCorner=5).items():
                terminal.add(name,current)
            terminal.add('ShapePoints').add('pt',1,2)
            owner.one('PadMask_TopSegments').add('pt',1,2,3,4)
        data = syntax(document)
        target = data.one('/Board/CacheLib/cl_Components/cl_Component/cl_Pattern')
        row = dimension(target.one('cl_Dimensions'),Connected1=0,Object1=0,SubObject1=1,Point1=0,
                        Connected2=2,Object2=0,SubObject2=1,Point2=0,Group=0)
        for name in ('NonSignal','PanelExclude'):
            row.one(name).detach()
        for child in row.walk(include_self=True):
            child.kind = 'cl_'+child.kind
        document = assemble_graphics(prepare_core(dumps(data,preserve=False))).document
        pattern = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
        pattern.one('Pads/Pad[1]').move_to(pattern.one('Pads'))
        pattern.one('Holes/Hole[1]').move_to(pattern.one('Holes'))
        current = pattern.one('Dimensions/Dimension')
        self.assertEqual((current['SubObject1'],current['SubObject2']),(2,2))
        expected,before,report = signature(pattern),dumps(document,preserve=False),ConversionReport()
        rebuilt = reopen(document,report=report)
        self.assertEqual(signature(rebuilt.one(pattern.path)),expected)
        self.assertEqual(signature(reopen(rebuilt).one(pattern.path)),expected)
        self.assertEqual(report.notices,[])
        self.assertEqual(dumps(document,preserve=False),before)

    def test_unresolved_pin_keeps_its_physical_scope_after_definition_reorder(self):
        data = loads(fixture())
        for section in tuple(project_cache(design().one('/Board')).children()):
            section.move_to(data.one('/Board'))
        data.one('/Board/CacheLib/cl_Components/cl_Component[1]/cl_Part/cl_Pins/cl_Pin/cl_Number').set_values(999)
        document = assemble_graphics(prepare_core(dumps(data,preserve=False))).document
        slot = document.one('/Board/CacheLib/Slots/Slot[1]')
        original = slot.one('Definition')
        original.one('Pattern')['Name'] = 'Assigned footprint'
        second = slot.add('Definition',0)
        document.copy(original.one('Part'),parent=second)
        document.copy(original.one('Pattern'),parent=second)['Name'] = 'Independent footprint'
        original.move_to(slot)
        before,report = dumps(document,preserve=False),ConversionReport()
        output = project_cache(document.one('/Board'),report=report)
        component = output.one('CacheLib/cl_Components/cl_Component[1]')
        self.assertEqual(component.one('cl_Pattern').values,('Assigned footprint',))
        self.assertEqual([row.one('cl_Pins/cl_Pin')['cl_Number']
                          for row in component.children('cl_Part')],[999,999])
        self.assertIn('unresolved-cached-pin',[notice.rule for notice in report.warnings])
        rebuilt = reopen(document,report=ConversionReport())
        part = rebuilt.one('/Board/CacheLib/Slots/Slot[1]/Definition[1]/Part')
        issue, = rebuilt.references._source_issues(part)
        self.assertEqual(issue.collections[0].parent['Name'],'Assigned footprint')
        self.assertEqual(dumps(document,preserve=False),before)

    def test_multipart_reorder_keeps_shared_footprint_and_pin_assignment_meaning(self):
        document = design()
        slot = document.one('/Board/CacheLib/Slots/Slot')
        original = slot.one('Definition')
        second = slot.add('Definition',0)
        part = document.copy(original.one('Part'),parent=second)
        part['Name'] = 'Second section'
        if part.child('Datasheet') is not None:
            del part['Datasheet']
        original.move_to(slot)
        report = ConversionReport()
        output = project_cache(document.one('/Board'),report=report)
        component = output.one('CacheLib/cl_Components/cl_Component')
        self.assertEqual([row.values[0] for row in component.children('cl_Part')],['Second section','Template0'])
        self.assertEqual(len(component.children('cl_Pattern')),1)
        self.assertIn('cached-footprint-position',[notice.rule for notice in report.infos])
        rebuilt = reopen(document,report=ConversionReport())
        definitions = rebuilt.select('/Board/CacheLib/Slots/Slot/Definition')
        self.assertIsNotNone(definitions[0].child('Pattern'))
        self.assertIsNone(definitions[1].child('Pattern'))
        pattern = definitions[0].one('Pattern')
        for definition in definitions:
            part = definition.one('Part')
            link = rebuilt.references.outgoing(part,role='symbol-pin-pad')[0]
            self.assertIs(link.target,pattern.one('Pads/Pad[1]'))

    def test_pin_assignments_to_independent_physical_domains_cannot_be_silently_combined(self):
        document = design()
        slot = document.one('/Board/CacheLib/Slots/Slot')
        document.copy(slot.one('Definition'),parent=slot)
        before = dumps(document,preserve=False)
        with self.assertRaisesRegex(PcbError,'multiple physical definitions'):
            project_cache(document.one('/Board'))
        self.assertEqual(dumps(document,preserve=False),before)

    def test_unavailable_active_link_warns_while_inactive_capacity_rows_stay_literal(self):
        document = design()
        board = document.one('/Board')
        board.one('DesignCache_Links').add('Link',999)
        report = ConversionReport()
        output = project_cache(board,report=report)
        self.assertEqual(output.one('DesignCache_Links/Link[2]').values,(999,))
        self.assertEqual(report.warnings,[])
        board['DesignCache_Count'] = 1
        project_cache(board,report=report)
        self.assertEqual([notice.rule for notice in report.warnings],['unresolved-design-cache-slot'])
        rebuilt = reopen(document,report=ConversionReport())
        member = rebuilt.one('/Board/DesignCache_Links/Link[2]')
        self.assertTrue(rebuilt.references.unresolved_slot(member))

    def test_external_paths_and_unavailable_slots_are_data_without_resource_io(self):
        document = design()
        slot = document.one('/Board/CacheLib/Slots').add('Slot',0,'unavailable.eli')
        slot['VariablePath'] = '${LIB}/unavailable.eli'
        slot['Model3DFile_Variable'] = '${MODELS}/unavailable.step'
        report = ConversionReport()
        with patch.object(Path,'read_bytes',side_effect=AssertionError('external resource read')):
            output = project_cache(document.one('/Board'),report=report)
        self.assertEqual(output.one('CacheLib/Design_Cache_Specific/cl_pt[2]').values,
                         ('unavailable.eli','${LIB}/unavailable.eli'))
        self.assertEqual([notice.rule for notice in report.warnings],['empty-slot-model-path'])

    def test_independent_unused_templates_and_styles_have_explicit_loss_diagnostics(self):
        text = source().replace('</PadStyles>', '''<PadStyle Name="Unused" Type="Surface" Side="Top">
          <MainStack Shape="Ellipse" Width="1" Height="1"/></PadStyle></PadStyles>''')
        document = read(text,report=ConversionReport())
        cache = document.one('/Board/CacheLib')
        document.copy(cache.one('Slots/Slot/Definition/Pattern'),parent=cache.add('Patterns'))
        before,report = dumps(document,preserve=False),ConversionReport()
        project_cache(document.one('/Board'),report=report)
        losses = [notice for notice in report.warnings if notice.rule=='independent-library-definitions']
        self.assertEqual(len(losses),2)
        self.assertEqual(dumps(document,preserve=False),before)

    def test_symbol_footprint_catalogue_and_paths_round_trip_without_source_changes(self):
        document = design()
        root = document.one('/Board/CacheLib')
        expected,before,report = signature(root),dumps(document,preserve=False),ConversionReport()
        rebuilt = reopen(document,report=report)
        self.assertEqual(signature(rebuilt.one('/Board/CacheLib')),expected)
        self.assertEqual(signature(reopen(rebuilt).one('/Board/CacheLib')),expected)
        self.assertEqual(dumps(document,preserve=False),before)
        self.assertEqual(report.notices,[])
        self.assertEqual(rebuilt.one('/Board/DesignCache_Count').values,(0,))
        self.assertEqual(rebuilt.one('/Board/DesignCache_Links/Link').values,(0,))

    def test_reordered_pads_groups_and_slots_generate_current_selectors(self):
        document = design()
        board = document.one('/Board')
        slot = board.one('CacheLib/Slots/Slot')
        pattern = slot.one('Definition/Pattern')
        pattern.one('Pads/Pad[1]').move_to(pattern.one('Pads'))
        group = slot.one('Definition/Part/Groups/pt')
        document.copy(group,index=0)
        empty = slot.parent.add('Slot',0,'empty.eli')
        empty['VariablePath'] = ''
        empty.move_to(slot.parent,0)
        output = project_cache(board)
        part = output.one('CacheLib/cl_Components/cl_Component[2]/cl_Part')
        self.assertEqual(part.one('cl_Pins/cl_Pin')['cl_Number'],2)
        self.assertEqual(part.one('cl_Pins/cl_Pin')['cl_Group'],1)
        self.assertEqual(output.one('DesignCache_Links/Link').values,(1,))
        rebuilt = reopen(document)
        self.assertEqual(signature(rebuilt.one('/Board/CacheLib')),signature(board.one('CacheLib')))
        pin = rebuilt.one('/Board/CacheLib/Slots/Slot[2]/Definition/Part/Pins/Pin')
        self.assertEqual(pin['Number'],2)

    def test_full_angles_multiline_text_and_model_placement_are_data(self):
        document = design()
        definition = document.one('/Board/CacheLib/Slots/Slot/Definition')
        drawing = definition.one('Part/Shapes/Shape')
        drawing['TextAngle'],drawing['FontSize'] = Decimal('8.25'),Decimal('1.375')
        drawing.one('TextLine').add('pt','')
        drawing.one('TextLine').add('pt','Second line')
        model = definition.one('Pattern/Model3D')
        model.one('Rotate')['Z'] = Decimal('38.25')
        model.one('Offset')['X'] = Decimal('1.25')
        output = project_cache(document.one('/Board'))
        shape = output.one('CacheLib/cl_Components/cl_Component/cl_Part/cl_Shapes/cl_Shape')
        self.assertEqual((shape['cl_Orientation'],shape['cl_FontSize']),(Decimal('8.25'),Decimal('1.375')))
        self.assertEqual(signature(reopen(document).one('/Board/CacheLib')),signature(document.one('/Board/CacheLib')))

    def test_known_template_and_font_omissions_warn_on_the_output_view(self):
        document = design()
        definition = document.one('/Board/CacheLib/Slots/Slot/Definition')
        definition.one('Pattern')['RefDes'] = 'U'
        definition.one('Part/Pins/Pin')['NameFontMono'] = True
        definition.one('Part/Shapes/Shape')['FontMono'] = True
        definition.one('Pattern/Shapes/Shape')['ShieldGroup'] = 0
        before,report = dumps(document,preserve=False),ConversionReport()
        project_cache(document.one('/Board'),report=report)
        self.assertEqual({notice.rule for notice in report.warnings},
                         {'cached-pattern-metadata','cached-pin-options','cached-symbol-drawing-options',
                          'cached-footprint-drawing-options'})
        self.assertEqual(dumps(document,preserve=False),before)

    def test_persistent_pad_keys_and_pin_timing_warn_and_leave_source_values_intact(self):
        document = design()
        definition = document.one('/Board/CacheLib/Slots/Slot/Definition')
        pad = definition.one('Pattern/Pads/Pad[1]')
        pin = definition.one('Part/Pins/Pin')
        pad['Id'],pin['SignalDelay'] = 17,2
        report = ConversionReport()
        output = project_cache(document.one('/Board'),report=report)
        self.assertEqual({notice.rule for notice in report.warnings},{'pad-persistent-key','cached-pin-options'})
        self.assertEqual((pad['Id'],pin['SignalDelay']),(17,2))
        target = output.one('CacheLib/cl_Components/cl_Component/cl_Part/cl_Pins/cl_Pin')
        self.assertIsNone(target.child('cl_SignalDelay'))

    def test_unmapped_definition_content_fails_instead_of_disappearing(self):
        document = design()
        document.one('/Board/CacheLib/Slots/Slot/Definition/Part').add('UnmappedField',17)
        with self.assertRaises(PcbError):
            project_cache(document.one('/Board'))


if __name__ == '__main__':
    unittest.main()
