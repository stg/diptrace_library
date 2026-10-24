"""Export policies retain inactive ASC states and report requested omissions."""
import unittest

from lib import new_schematic,parse_dch,parse_asc,parse_dchxml,AscExportContext,ExportReport
from lib.schematic.model.objects import (new_symbol, new_pin, new_symbol_shape, new_pattern)
from lib.schematic.model.refs import (bind_schematic_references)
from lib.common.structural_edits import assembly


def source():
    document=new_schematic()
    parts=document.one('/Schematic/Components')
    first=parts.append(new_symbol('Buffer','U1'))
    first.one('Pins').append(new_pin())
    first.one('Shapes').append(new_symbol_shape())
    parts.append(new_symbol('Spare','U2'))
    bind_schematic_references(document)
    document=parse_dch(document.to_dch_bytes())
    document.one('/Schematic/Components/Part[2]').set_field('Enabled',False)
    document.one('/Schematic/Components/Part[1]/Pins/Pin').set_field('Enabled',False)
    document.one('/Schematic/Components/Part[1]/Shapes/Shape[1]').set_field('Enabled',False)
    return document


class InactiveExportTests(unittest.TestCase):
    def test_omitted_inactive_sources_can_discard_their_own_unresolved_links(self):
        document = new_schematic()
        part = document.one('/Schematic/Components').append(new_symbol('Unused', 'U1'))
        part.set_field('Enabled', False)
        pin = part.one('Pins').append(new_pin())
        bind_schematic_references(document)
        document = parse_dch(document.to_dch_bytes())
        pin = document.one('/Schematic/Components/Part/Pins/Pin')
        # Construct a malformed imported occurrence explicitly. A resolved
        # pin's NetNumber is calculated and ordinary editing uses pin['Net'].
        with assembly(document):
            pin.one('NetNumber').detach()
            pin.add('NetNumber', 99)
            bind_schematic_references(document)
        self.assertEqual(len(document.references.issues), 1)
        before = document.to_dch_bytes()
        for export in (document.as_asc, document.as_dchxml):
            report = ExportReport()
            public = export(report=report)
            self.assertEqual(public.references.issues, [])
            self.assertEqual(report.errors, [])
            self.assertEqual([notice.rule for notice in report.warnings], ['inactive-records'])
        self.assertEqual(document.to_dch_bytes(), before)
        self.assertEqual(len(document.references.issues), 1)
        self.assertEqual(pin.scalar('NetNumber'), 99)

    def test_empty_drawing_slots_are_info_but_saved_content_still_warns(self):
        document = new_schematic()
        document.one('/Schematic').set_field('ShowRefDes_Global', 2, 0, 7)
        document.one('/Schematic').set_field('ShowValue_Global', 2, 7)
        part = document.one('/Schematic/Components').append(new_symbol('Buffer', 'U1'))
        empty = part.one('Shapes').append(new_symbol_shape())
        empty.set_field('Enabled', False)
        empty.set_field('Type', 0)
        content = part.one('Shapes').append(empty.clone())
        content.one('TextLine').add('pt', 'Keep this saved note')
        slot = document.one('/Schematic/CacheLib/Slots').add('Slot', 0, '')
        slot.add('VariablePath', '')
        definition = slot.add('Definition', 0)
        cached = definition.append(new_symbol('Buffer', 'U', placed=False))
        cached.one('Shapes').append(empty.clone())
        definition.append(new_pattern())
        bind_schematic_references(document)
        before = document.to_dch_bytes()
        for export in (document.as_asc, document.as_dchxml):
            report = ExportReport()
            export(report=report)
            empty_paths = {path for notice in report.infos if notice.rule == 'inactive-empty-drawings'
                           for path in notice.paths}
            content_paths = {path for notice in report.warnings if notice.rule == 'inactive-records'
                             for path in notice.paths}
            self.assertIn(empty.path, empty_paths)
            self.assertIn(content.path, content_paths)
            self.assertNotIn(empty.path, content_paths)
            self.assertNotIn(content.path, empty_paths)
            self.assertEqual(document.to_dch_bytes(), before)
        self.assertEqual(content.one('TextLine/pt').values, ('Keep this saved note',))

    def test_xml_library_omissions_warn_without_changing_owned_definitions(self):
        document=new_schematic()
        definition=document.one('/Schematic/CacheLib/Slots').add('Slot',0,'').add('Definition',0)
        part=definition.append(new_symbol('Spare','U',placed=False))
        part.set_field('Enabled',False)
        pin=part.one('Pins').append(new_pin(placed=False))
        pin.set_field('Enabled',False)
        shape=part.one('Shapes').append(new_symbol_shape())
        shape.set_field('Enabled',False)
        definition.append(new_pattern())
        bind_schematic_references(document)
        report=ExportReport()
        public=document.as_dchxml(report=report)
        rules={notice.rule:notice for notice in report.warnings}
        self.assertEqual(len(rules['inactive-library-records'].paths),2)
        self.assertEqual(len(rules['inactive-library-state'].paths),1)
        self.assertFalse(part.scalar('Enabled'))
        self.assertFalse(pin.scalar('Enabled'))
        self.assertFalse(shape.scalar('Enabled'))
        projected=public.one('/Source/Library/Components/Component/Part')
        self.assertEqual(projected.select('Pins/Pin'),[])
        self.assertEqual(projected.select('Shapes/Shape'),[])

    def test_asc_can_keep_inactive_records_and_shared_import_preserves_them(self):
        document=source()
        before=document.to_dch_bytes()
        report=ExportReport()
        data=document.to_asc_bytes(context=AscExportContext(compact_inactive=False),report=report)
        self.assertEqual(report.warnings,[])
        for _ in range(3):
            imported=parse_asc(data.decode('cp1252')).as_schematic()
            self.assertEqual(len(imported.select('/Schematic/Components/Part')),2)
            self.assertFalse(imported.one('/Schematic/Components/Part[2]').scalar('Enabled'))
            self.assertFalse(imported.one('/Schematic/Components/Part[1]/Pins/Pin').scalar('Enabled'))
            self.assertFalse(imported.one('/Schematic/Components/Part[1]/Shapes/Shape[1]').scalar('Enabled'))
            actual=imported.to_asc_bytes(context=AscExportContext(compact_inactive=False),report=ExportReport())
            self.assertEqual(actual,data)
            data=actual
        self.assertEqual(document.to_dch_bytes(),before)

    def test_compaction_reports_paths_and_leaves_original_records_intact(self):
        document=source()
        before=document.to_dch_bytes()
        for destination in ('asc','dchxml'):
            report=ExportReport()
            if destination=='asc':
                public=document.as_asc(report=report)
                parts=public.select('/Schematic/Components/Part')
            else:
                public=document.as_dchxml(report=report)
                parts=public.select('/Source/Schematic/Components/Part')
            self.assertEqual(len(parts),1)
            notices=[notice for notice in report.warnings if notice.rule=='inactive-records']
            self.assertEqual(len(notices),1)
            self.assertEqual(notices[0].destination,destination)
            self.assertEqual(len(notices[0].paths),3)
            self.assertEqual(document.to_dch_bytes(),before)
        retained=document.as_asc(context=AscExportContext(compact_inactive=False)).as_schematic()
        report=ExportReport()
        compacted=retained.as_asc(context=AscExportContext(compact_inactive=True),report=report)
        self.assertEqual(len(compacted.select('/Schematic/Components/Part')),1)
        self.assertTrue(any(notice.rule=='inactive-records' for notice in report.warnings))


if __name__=='__main__':
    unittest.main()
