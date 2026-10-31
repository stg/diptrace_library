"""Catalogues expose complete immutable definitions without hiding conflicts."""
from types import SimpleNamespace
import unittest

from lib.common.schema import Child, Field, Record
from lib.common.schema_catalogue import record_catalogue


class SchemaCatalogueTests(unittest.TestCase):
    def test_aliases_and_mapping_exports_preserve_definition_identity(self):
        row = Record('Row', {'Name': Field('Name', 'text')})
        root = Record('Root', {}, children={'Row': Child('Row', row.name, maximum=None)})
        result = record_catalogue(SimpleNamespace(ROOT=root, ALIAS=row, COLLECTIONS={'row': row}))
        self.assertEqual(tuple(result), ('Root', 'Row'))
        self.assertIs(result['Row'], row)
        with self.assertRaises(TypeError):
            result['Row'] = root

    def test_conflicting_names_require_an_explicit_family_definition(self):
        base = Record('Row', {})
        complete = Record('Row', {'Name': Field('Name', 'text')})
        module = SimpleNamespace(BASE=base, COMPLETE=complete)
        with self.assertRaisesRegex(ValueError, 'conflicting record definitions for Row'):
            record_catalogue(module)
        self.assertIs(record_catalogue(module, overrides=(complete,))['Row'], complete)

    def test_child_types_are_checked_and_roots_select_only_reachable_records(self):
        row = Record('Row', {})
        root = Record('Root', {}, children={'Row': Child('Row', row.name)})
        orphan = Record('Orphan', {}, children={'Missing': Child('Missing', 'Undeclared')})
        module = SimpleNamespace(ROOT=root, ROW=row, ORPHAN=orphan)
        self.assertEqual(tuple(record_catalogue(module, roots=(root.name,))), ('Root', 'Row'))
        with self.assertRaisesRegex(ValueError, 'undeclared child record: Undeclared'):
            record_catalogue(module)

    def test_undeclared_override_does_not_silently_add_a_record(self):
        with self.assertRaisesRegex(ValueError, 'override has no declared record'):
            record_catalogue(SimpleNamespace(), overrides=(Record('Absent', {}),))

    def test_named_tuple_member_definitions_are_reachable_without_guessing_by_value(self):
        fields = {'X': Field('X', 'number'), 'Y': Field('Y', 'number')}
        point = Record('Point', fields, parameters=('X', 'Y'))
        unrelated = Record('OtherPoint', {'X': Field('X', 'number'), 'Y': Field('Y', 'number')},
                           parameters=('X', 'Y'))
        root = Record('Root', {'Position': Field('Position', 'tuple', members=tuple(point.fields.values()))})
        result = record_catalogue(SimpleNamespace(ROOT=root, POINT=point, OTHER=unrelated), roots=('Root',))
        self.assertEqual(tuple(result), ('Point', 'Root'))
