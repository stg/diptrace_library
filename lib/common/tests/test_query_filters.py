"""Callable filters operate on final matches before one() checks cardinality."""
import unittest

from lib.common.model import Document


class QueryFilterTests(unittest.TestCase):
    def setUp(self):
        self.document = Document()
        self.parts = self.document.root.add("Components")
        self.first = self.parts.add("Part")
        self.first.add("RefDes", "R1")
        self.first.add("X", 10)
        self.first.add("Y", 20)
        self.second = self.parts.add("Part")
        self.second.add("RefDes", "R2")
        self.second.add("X", 40)
        self.second.add("Y", 10)

    def test_numeric_ranges_and_combined_conditions_at_both_entry_points(self):
        predicate = lambda p: 0 <= p["X"] <= 30 and 15 <= p["Y"] <= 25
        self.assertEqual(self.document.select("/Components/Part", where=predicate), [self.first])
        self.assertEqual(self.parts.select("Part", where=predicate), [self.first])
        self.assertEqual(self.document.find_all("Part", where=predicate), [self.first])
        self.assertEqual(self.parts.find_all("Part", where=predicate), [self.first])
        self.assertIs(self.document.one("/Components/Part", where=predicate), self.first)
        self.assertIs(self.parts.one("Part", where=predicate), self.first)

    def test_path_predicates_and_ordinals_precede_callable_filtering(self):
        predicate = lambda p: p["X"] > 30
        self.assertEqual(self.parts.select('Part[RefDes="R2"]', where=predicate), [self.second])
        self.assertEqual(self.parts.select("Part[1]", where=predicate), [])
        self.assertEqual(self.parts.select("Part[2]", where=predicate), [self.second])
        visited = []
        self.document.select("/Components/Part", where=lambda p: visited.append(p) or True)
        self.assertEqual(visited, [self.first, self.second])

    def test_one_checks_filtered_cardinality(self):
        for predicate in (lambda p: True, lambda p: False):
            with self.assertRaises(LookupError):
                self.document.one("//Part", where=predicate)
        self.assertIs(self.document.one("//Part", where=lambda p: p["RefDes"] == "R2"), self.second)

    def test_filters_observe_current_values_and_document_order(self):
        predicate = lambda p: p["X"] > 30
        self.assertEqual(self.parts.select("Part", where=predicate), [self.second])
        self.first.set_field("X", 50)
        self.assertEqual(self.parts.select("Part", where=predicate), [self.first, self.second])
        self.second.move_to(self.parts, 0)
        self.assertEqual(self.parts.select("Part", where=predicate), [self.second, self.first])

    def test_root_filter_and_invalid_predicates(self):
        self.assertEqual(self.document.select("/", where=lambda p: p is self.document.root),
                         [self.document.root])
        self.assertEqual(self.document.select("/", where=lambda p: False), [])
        for query in (
            lambda: self.document.select("//Missing", where=3),
            lambda: self.parts.select("Missing", where=3),
            lambda: self.document.find_all("Missing", where=3),
            lambda: self.parts.find_all("Missing", where=3),
        ):
            with self.assertRaisesRegex(TypeError, "where"):
                query()
        with self.assertRaisesRegex(RuntimeError, "caller failure"):
            self.parts.select("Part", where=lambda p: self.fail_predicate())

    def fail_predicate(self):
        raise RuntimeError("caller failure")
