"""Standalone pattern selections share the library catalogue contract."""
import unittest

from lib.pattern.model import new_library, new_pattern
from lib.pattern.formats import io
from lib.tests.library_catalogue_contract import LibraryCatalogueContract


class PatternCatalogueTests(LibraryCatalogueContract, unittest.TestCase):
    library = staticmethod(new_library)
    entry = staticmethod(new_pattern)
    io = io
    prefix = 'Pattern'
    collection = 'Patterns'
    formats = ('lib', 'asc', 'libxml')
