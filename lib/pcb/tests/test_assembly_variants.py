"""Named assembly variants maintain exclusion and table identities while editing."""
import unittest
from unittest.mock import patch

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.common.references import Property, ReferenceError
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.asc.table_projection import project_table
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.model import assembly_variants as model
from lib.pcb.tests.test_core_assembly import fixture as decoded_fixture
from lib.pcb.tests.test_dipxml_tables import source, TABLES, read
from lib.pcb.tests.test_table_model import fixture as asc_fixture


NAMES = '<AssemblyVariants><AssemblyVariant>Full</AssemblyVariant><AssemblyVariant>Reduced</AssemblyVariant></AssemblyVariants>'
EXCLUDE = '<AssemblyExclude><Item>0</Item></AssemblyExclude>'


def xml(*, exclusion=0, selected=1):
    return source(TABLES.replace('AssemblyVariant="0"', f'AssemblyVariant="{selected}"')).replace(
        '</Board>', NAMES+'</Board>').replace('</Component>', EXCLUDE.replace('<Item>0', f'<Item>{exclusion}')+'</Component>')


class AssemblyVariantTests(unittest.TestCase):
    def test_xml_names_and_zero_based_selections_become_current_references(self):
        document = read(xml(), report=ConversionReport())
        full, reduced = document.select('/Board/AssemblyVariants/AssemblyVariant')
        member = document.one('/Board/Components/Component/AssemblyExclude/Item')
        update = document.one('/Board/Tables/Table/AutoUpdate')
        self.assertIs(full.schema, model.VARIANT)
        self.assertEqual((full['Name'], reduced['Name'], full['Id']), ('Full', 'Reduced', 0))
        self.assertIs(member['Variant'], full)
        self.assertIs(update['Variant'], reduced)
        self.assertEqual((member['Index'], update['AssemblyVariant']), (0, 1))
        self.assertIsNone(member.child('Index'))
        self.assertIsNone(update.child('AssemblyVariant'))
        self.assertIsNone(document.one('/Board').child('Settings/AssemblyVariants'))
        document.references.validate()

    def test_reordering_and_renaming_follow_both_consumers_without_rebuilding_or_generating_tables(self):
        document = read(xml(), report=ConversionReport())
        full, reduced = document.select('/Board/AssemblyVariants/AssemblyVariant')
        member = document.one('/Board/Components/Component/AssemblyExclude/Item')
        table = document.one('/Board/Tables/Table')
        update = table.one('AutoUpdate')
        observer = document.root.add('Positions', -1, -1)
        document.references.bind(observer, member, Property(observer, 'Index', 0))
        document.references.bind(observer, update, Property(observer, 'AssemblyVariant', 1))
        with patch.object(document.root, 'walk', side_effect=AssertionError('global tree scan')), \
                patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
            full.move_to(full.parent, 1)
            self.assertEqual(observer.values, (1, 0))
            reduced['Name'] = 'Economy'
            self.assertEqual(update['Variant']['Name'], 'Economy')
            update['Variant'] = full
            self.assertEqual(observer.values, (1, 1))
            member['Variant'] = reduced
            self.assertEqual(observer.values, (0, 1))
            self.assertEqual(table.one('Cells/Cell[1]')['Text'], 'first\n\nlast')
            output = project_table(table, report=ConversionReport())
            self.assertEqual(output['DocSettings_AssemblyVariant'], 1)
        document.references.validate()

    def test_copy_clone_and_scope_guards_preserve_variant_identities(self):
        document = read(xml(), report=ConversionReport())
        variants = document.one('/Board/AssemblyVariants')
        member = document.one('/Board/Components/Component/AssemblyExclude/Item')
        target = member['Variant']
        duplicate = document.copy(member)
        self.assertIs(duplicate['Variant'], target)
        with self.assertRaises(ReferenceError):
            document.remove(target)
        with self.assertRaises(ReferenceError):
            member.move_to(variants)
        clone = document.clone()
        copied = clone.one('/Board/Components/Component/AssemblyExclude/Item[1]')
        self.assertIsNot(copied['Variant'], target)
        with self.assertRaises(ReferenceError):
            member['Variant'] = copied['Variant']
        extra = variants.add('AssemblyVariant', 'Prototype')
        self.assertIs(extra.schema, model.VARIANT)
        empty = member.parent.add('Item')
        empty['Variant'] = extra
        self.assertEqual(empty['Index'], 2)
        with self.assertRaises(TypeError):
            member.parent.add('Item', 1)
        document.references.validate()
        clone.references.validate()

    def test_missing_variants_are_explicit_and_repairable_for_both_selection_types(self):
        report = ConversionReport()
        document = read(xml(exclusion=8, selected=9), report=report)
        member = document.one('/Board/Components/Component/AssemblyExclude/Item')
        update = document.one('/Board/Tables/Table/AutoUpdate')
        self.assertEqual((member['Index'], update['AssemblyVariant']), (8, 9))
        for owner in (member, update):
            with self.assertRaises(ReferenceError):
                owner['Variant']
        target = document.one('/Board/AssemblyVariants/AssemblyVariant[2]')
        member['Variant'] = target
        update['Variant'] = None
        self.assertFalse(document.references.issues)
        self.assertEqual((member['Index'], update['AssemblyVariant']), (1, -1))
        self.assertIsNone(member.child('UnresolvedIndex'))
        self.assertIsNone(update.child('UnresolvedAssemblyVariant'))
        self.assertIn('unresolved-assembly-variant', [item.rule for item in report.warnings])
        document.references.validate()

    def test_empty_named_choices_do_not_invent_a_default_variant(self):
        document = read(source(), report=ConversionReport())
        update = document.one('/Board/Tables/Table/AutoUpdate')
        variants = document.one('/Board/AssemblyVariants')
        self.assertEqual(variants.children(), [])
        self.assertIsNone(update['Variant'])
        self.assertEqual(update['AssemblyVariant'], 0)
        observer = document.root.add('Selection', -1)
        document.references.bind(observer, update, Property(observer, 'AssemblyVariant'))
        added = variants.add('AssemblyVariant', 'First')
        self.assertEqual(observer.values, (-1,))
        update['Variant'] = added
        self.assertEqual(observer.values, (0,))
        update['Variant'] = None
        document.remove(added)
        self.assertEqual(observer.values, (0,))
        document.references.validate()

    def test_ascii_and_decoded_binary_use_the_same_named_records_and_position_domain(self):
        syntax = asc_fixture()
        board = syntax.one('/Board')
        variants = board.add('AssemblyVariants')
        variants.add('AssemblyVariant', 'Full')
        variants.add('AssemblyVariant', 'Reduced')
        excluded = board.one('Components/Component/AssemblyExclude')
        excluded.set_values(1)
        excluded.add('pt', 1)
        document = assemble_graphics(prepare_core(dumps(syntax, preserve=False))).document
        member = document.one('/Board/Components/Component/AssemblyExclude/Item')
        self.assertEqual(member['Variant']['Name'], 'Reduced')
        self.assertEqual(document.one('/Board/Tables/Table/AutoUpdate')['Variant']['Name'], 'Full')
        decoded = decoded_fixture()
        names = decoded.board.add('Settings').add('AssemblyVariants')
        names.add('AssemblyVariant', 'Full')
        names.add('AssemblyVariant', 'Reduced')
        decoded.board.one('Components/Component').add('AssemblyExclude').add('Item', 1)
        binary = assemble_core(decoded).document
        self.assertEqual(binary.one('/Board/Components/Component/AssemblyExclude/Item')['Variant']['Name'], 'Reduced')
        self.assertIsNone(binary.one('/Board/Settings').child('AssemblyVariants'))
        binary.references.validate()


if __name__ == '__main__':
    unittest.main()
