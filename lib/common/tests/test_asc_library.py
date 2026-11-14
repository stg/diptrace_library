"""Library catalogues and explicit path pairs share ASC boundary helpers."""
import unittest
from lib.common import asc
from lib.common.asc_library import loads_library, loads_library_bytes

from lib.common.asc_library import project_catalogs, project_library_paths
from lib.common.model import Element


class AscLibraryOutputTests(unittest.TestCase):
    def test_catalogue_keys_and_order_are_independent_of_generated_counts(self):
        cache = Element('CacheLib')
        category = cache.add('Categories').add('Category','Parts',91)
        kind = category.add('Type','Function',17)
        kind.add('Subtype','General',28)
        kind.add('Subtype','Special',4)
        cache.add('Subfolders').add('Folder','Connectors')
        output = project_catalogs(cache)
        self.assertEqual(output.one('cl_Categories').values,(1,))
        self.assertEqual(output.one('cl_Categories/cl_Category').values,('Parts',91,1))
        self.assertEqual(output.one('cl_Categories/cl_Category/cl_Type').values,('Function',17,2))
        self.assertEqual([row.values for row in output.select('cl_Categories/cl_Category/cl_Type/cl_SubType')],
                         [('General',28),('Special',4)])
        self.assertEqual(category.values,('Parts',91))

    def test_missing_empty_catalogues_generate_no_authored_rows(self):
        output = project_catalogs(Element('CacheLib'))
        self.assertEqual([row.values for row in output.children()],[(0,),(0,)])

    def test_path_pairs_preserve_empty_expressions_unless_a_dialect_requests_fallback(self):
        source = Element('ProjectLibs_Folders')
        first = source.add('Folder','parts')
        first.add('VariablePath','')
        source.add('Folder','other').add('VariablePath','${ROOT}/other')
        output = project_library_paths(source,'Folder')
        self.assertEqual(output.values,(2,))
        self.assertEqual([row.values for row in output.children()],
                         [('parts',),('',),('other',),('${ROOT}/other',)])
        self.assertEqual(project_library_paths(source,'Folder',variable_fallback=True).children()[1].values,('parts',))
        self.assertEqual(first.scalar('VariablePath'),'')

    def test_unknown_catalogue_and_path_children_fail(self):
        cache = Element('CacheLib')
        cache.add('Categories').add('Category','Parts',0).add('Unexpected',1)
        with self.assertRaises(ValueError):
            project_catalogs(cache)
        paths = Element('ProjectLibs_Libs')
        paths.add('Lib','parts.eli').add('Unexpected',1)
        with self.assertRaises(ValueError):
            project_library_paths(paths,'Lib')


class LibrarySyntaxTests(unittest.TestCase):
    def test_byte_input_shares_the_ASC_encoding_and_source_policy(self):
        for data,expected in ((b'(Library (Name "caf\xe9"))()','caf\u00e9'),
                              ('\ufeff(Library (Name "\u03a9"))()'.encode('utf-8'),'\u03a9')):
            with self.subTest(expected=expected):
                detailed = loads_library_bytes(data)
                lean = loads_library_bytes(memoryview(data), retain_source=False)
                self.assertEqual(expected, detailed.one('/Library/Name').values[0])
                self.assertEqual(expected, lean.one('/Library/Name').values[0])
                self.assertEqual(data, detailed._source_bytes)
                self.assertIsNone(lean._source_bytes)
                self.assertIsNone(lean._source_text)

    def test_canonical_empty_terminator_is_not_an_authored_record(self):
        text = '(Source "DipTrace-ComLibrary" 24)\n(Library (Name "Example"))\n()\n'
        document = loads_library(text, retain_source=False)
        self.assertEqual(('Example',), document.one('/Library/Name').values)
        self.assertEqual(['Source', 'Library'], [node.kind for node in document.root.children()])
        with self.assertRaises(ValueError):
            asc.loads(text)

    def test_optional_marker_does_not_change_quoted_parentheses_or_accept_inner_empty_data(self):
        document = loads_library('(Library (Name "Example ()"))')
        self.assertEqual(('Example ()',), document.one('/Library/Name').values)
        for text in ('(Library ())()', '(Library)()()', '()()', '(Library (Name "unfinished)()'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                loads_library(text)


if __name__ == '__main__':
    unittest.main()
