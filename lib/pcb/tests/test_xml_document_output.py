"""Whole PCB XML assembly covers current facts without donor syntax or I/O."""
from collections import Counter
from decimal import Decimal
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.pcb.formats.dipxml.coverage import FIELD_OWNERS, CHILD_OWNERS
from lib.pcb.formats.dipxml.project_options import PROJECT_LIBRARY_DEFAULTS, ASSEMBLY_CHOICES
from lib.pcb.formats.dipxml.syntax import dumps
from lib.pcb.formats.dipxml.write import project_document
from lib.pcb.formats.errors import PcbError
from lib.pcb.model.definitions import BOARD
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dipxml_library import read, source as library_source
from lib.pcb.tests.test_dipxml_dimensions import text as dimension_source
from lib.pcb.tests.test_dipxml_design_rules import DRC, CLASS_CLEARANCES
from lib.pcb.tests.test_dipxml_tables import TABLES
from lib.pcb.tests.test_drc_result_inputs import XML as RESULTS
from lib.pcb.tests.test_ratline_inputs import XML as RATLINES
from lib.pcb.tests.test_title_relations import source as title_source
from lib.pcb.tests.test_xml_routing_output import with_component_library


def rich_source():
    root = ElementTree.fromstring(dimension_source())
    root.set('Version', '5.3.5.1')
    board = root.find('Board')
    settings = ElementTree.fromstring(title_source()).find('Board')
    for name in ('Settings', 'SheetSettings', 'Panel', 'ConnectivityCheck'):
        board.append(settings.find(name))
    for section in (DRC, CLASS_CLEARANCES, TABLES, RESULTS, RATLINES):
        board.append(ElementTree.fromstring(section))
    return with_component_library(ElementTree.tostring(root, encoding='unicode'))


def design(text=None):
    return read(rich_source() if text is None else text, report=ConversionReport())


class XmlDocumentOutputTests(unittest.TestCase):
    def test_unnamed_title_grids_retain_data_and_local_field_relationships(self):
        document = design()
        block = document.one('/Board/SheetSettings/TitleBlocks/TitleBlock[1]')
        block['Name'] = ''
        before = model_text(document, preserve=False)
        for version in (54, 58, 60, 62):
            with self.subTest(version=version):
                output = project_document(document, version=version, report=ConversionReport())
                self.assertIsNotNone(output.one('/Source/Board/SheetSettings').child('BottomRightBlock'))
                rebuilt = design(dumps(output))
                current = rebuilt.one('/Board/SheetSettings/TitleBlocks/TitleBlock[1]')
                self.assertEqual((current['Name'], current['Width'], current['Height']), ('', 60, 18))
                fields = current.select('Contents/Content')
                self.assertEqual([field['Text'] for field in fields], ['Revision\nA', 'Sheet'])
                self.assertEqual([cell['Field'] for cell in current.select('Cells/Cell')], fields)
                rebuilt.references.validate()
        self.assertEqual(model_text(document, preserve=False), before)

    def assert_facts(self, actual, expected):
        self.assertEqual(actual.keys(), expected.keys())
        for name, value in expected.items():
            if isinstance(value, tuple):
                self.assert_facts(dict(enumerate(actual[name])), dict(enumerate(value)))
            elif isinstance(value, (int, Decimal)) and not isinstance(value, bool):
                self.assertLessEqual(abs(actual[name]-value), Decimal('1e-23'), name)
            else:
                self.assertEqual(actual[name], value, name)

    def test_current_document_sections_survive_units_and_repeated_output_without_source_changes(self):
        document = design()
        before, expected = model_text(document, preserve=False), signature(document.root)
        for units in ('mm', 'mil', 'inch'):
            current = document
            for _ in range(3):
                syntax = project_document(current, units=units, report=ConversionReport())
                current = design(dumps(syntax))
                actual = signature(current.root)
                actual['/Units'] = expected['/Units']  # Selected display unit; physical facts are compared below.
                self.assert_facts(actual, expected)
                current.references.validate()
        self.assertEqual(model_text(document, preserve=False), before)

    def test_owned_cached_library_and_literal_picture_paths_need_no_external_files(self):
        document = design(library_source())
        before, expected = model_text(document, preserve=False), signature(document.root)
        with patch('pathlib.Path.open', side_effect=AssertionError('external file access')):
            syntax = project_document(document, report=ConversionReport())
            current = design(dumps(syntax))
        self.assert_facts(signature(current.root), expected)
        self.assertEqual(model_text(document, preserve=False), before)

    def test_edits_and_reference_reorders_are_projected_from_the_current_model(self):
        document = design()
        component = document.one('/Board/Components/Component')
        component['RefDes'], component['Value'], component['X'] = 'U17', 'Edited', Decimal('31.25')
        net = document.one('/Board/Nets/Net')
        net['Name'] = 'Edited net'
        point = document.one('/Board/Nets/Net/Traces/Trace[1]/Points/Point[2]')
        point.move_to(point.parent, 0)
        expected = signature(document.root)
        current = design(dumps(project_document(document, report=ConversionReport())))
        self.assert_facts(signature(current.root), expected)
        current.references.validate()

    def test_unknown_content_fails_atomically_with_report_errors(self):
        for name in ('UnknownField', 'UnknownSection'):
            with self.subTest(name=name):
                document = design(library_source())
                board = document.one('/Board')
                board.add(name)
                before, report = model_text(document, preserve=False), ConversionReport()
                with self.assertRaises(PcbError):
                    project_document(document, report=report)
                self.assertEqual(len(report.errors), 1)
                self.assertEqual(model_text(document, preserve=False), before)

    def test_every_declared_root_fact_has_one_explicit_owner(self):
        names = [name for group in FIELD_OWNERS.values() for name in group]
        self.assertEqual([name for name,count in Counter(names).items() if count != 1], [])
        self.assertEqual(frozenset(names), BOARD.fields.keys())
        self.assertEqual(CHILD_OWNERS.keys(), BOARD.children.keys())

    def test_absent_optional_sections_do_not_invent_settings_or_project_paths(self):
        document = design(library_source())
        self.assertEqual([row.kind for row in document.one('/Board/Settings').children()], ['ShowCompFiducials'])
        current = design(dumps(project_document(document, report=ConversionReport())))
        self.assertEqual(current.one('/Board/Settings')['ShowCompFiducials'], True)
        for name in ('SheetSettings', 'ProjectLibs_Folders', 'ProjectLibs_Libs'):
            self.assertIsNone(current.one('/Board').child(name))
        self.assertNotIn('ProjectLibs_Sorted', current.one('/Board'))

    def test_project_headers_initialize_canonical_defaults_and_report_custom_values_on_export(self):
        text = library_source().replace('<Board>', '<Board><ProjectLibs Sorted="N"/>', 1)
        document = design(text)
        board = document.one('/Board')
        self.assertEqual({name: board[name] for name in PROJECT_LIBRARY_DEFAULTS}, PROJECT_LIBRARY_DEFAULTS)
        report = ConversionReport()
        current = design(dumps(project_document(document, report=report)))
        self.assert_facts(signature(current.root), signature(document.root))
        self.assertFalse(report.warnings)
        self.assertIn('project-library-header-default', {notice.rule for notice in report.infos})
        board['ProjectLibs_Name'], board['ProjectLibs_Type'], board['ProjectLibs_Content'] = 'My parts', 7, 9
        for index, name in enumerate(ASSEMBLY_CHOICES):
            board[name] = bool(index % 2)
        board['UserField1'], board['UserField2'] = 'Document note', ''
        before, report = model_text(document, preserve=False), ConversionReport()
        current = design(dumps(project_document(document, report=report)))
        self.assertEqual({name: current.one('/Board')[name] for name in PROJECT_LIBRARY_DEFAULTS}, PROJECT_LIBRARY_DEFAULTS)
        self.assertTrue({'project-library-header', 'assembly-object-choices', 'document-fields'} <=
                        {notice.rule for notice in report.warnings})
        self.assertIn('empty-document-fields', {notice.rule for notice in report.infos})
        self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
