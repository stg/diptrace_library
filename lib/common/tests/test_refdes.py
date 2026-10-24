"""Numbered RefDes families compare counters without losing authored spelling."""
import unittest

from lib.common.refdes import RefDesFamily, split_refdes


class RefDesTests(unittest.TestCase):
    def test_split_uses_only_the_final_ascii_digit_run(self):
        for text, expected in (
            ("R12", ("R", 12)), ("R1-X12", ("R1-X", 12)),
            ("J6-02", ("J6-", 2)), ("A1B02", ("A1B", 2)),
            ("R003", ("R", 3)), ("0", ("", 0)), ("123", ("", 123)),
            ("Ω12", ("Ω", 12)), ("R", ("R", 0)), ("R0", ("R", 0)),
            ("R-", ("R-", 0)), ("R-1", ("R-", 1)),
            ("BLOCK_%_2", ("BLOCK_%_", 2)), ("R\u0663", ("R\u0663", 0)),
        ):
            with self.subTest(reference=text):
                self.assertEqual(split_refdes(text), expected)
        for text in ("", "R 1", " R1", "R1 "):
            with self.subTest(reference=text), self.assertRaises(ValueError):
                split_refdes(text)
        with self.assertRaises(TypeError):
            split_refdes(3)

    def test_exact_prefix_matching_retains_all_records_and_spelling(self):
        references = ["R1-X2", "R1-10", "R1-002", "R1-2", "R1-2", "r1-1", "", "NET"]
        family = RefDesFamily("R1-", references)
        self.assertEqual(family.matches(), ["R1-002", "R1-2", "R1-2", "R1-10"])
        self.assertEqual(family.matches("R1-0002"), ["R1-002", "R1-2", "R1-2"])
        self.assertEqual(family.designators(), ["R1-002", "R1-2", "R1-10"])
        self.assertEqual(family.matches("R1-X2"), [])
        self.assertIn("R1-0002", family)
        self.assertNotIn("R1-X2", family)
        self.assertNotIn("NET", family)
        self.assertEqual(references[2], "R1-002")

    def test_endpoints_and_first_free(self):
        family = RefDesFamily("R", ["R010", "R2", "R4", "R2"])
        self.assertEqual(family.first(), "R2")
        self.assertEqual(family.last(), "R010")
        self.assertEqual(family.first_free(), "R1")
        self.assertEqual(family.first_free(2), "R3")
        self.assertEqual(family.first_free(10), "R11")
        self.assertEqual(family.first_free(0), "R0")
        empty = RefDesFamily("R", [])
        self.assertIsNone(empty.first())
        self.assertIsNone(empty.last())
        self.assertEqual(empty.first_free(), "R1")
        for invalid in (-1, True, 1.5, "1"):
            with self.subTest(start=invalid), self.assertRaises(ValueError):
                family.first_free(invalid)

    def test_next_and_previous_have_explicit_strict_modes(self):
        family = RefDesFamily("R", ["R2", "R004", "R10"])
        for current, mode, after, before in (
            ("R4", "number", "R5", "R3"),
            ("R4", "existing", "R10", "R2"),
            ("R4", "free", "R5", "R3"),
            ("R3", "existing", "R004", "R2"),
            ("R3", "free", "R5", "R1"),
        ):
            with self.subTest(current=current, mode=mode):
                self.assertEqual(family.next(current, mode=mode), after)
                self.assertEqual(family.previous(current, mode=mode), before)
        self.assertIsNone(family.next("R10", mode="existing"))
        self.assertIsNone(family.previous("R2", mode="existing"))
        for mode in ("number", "free"):
            self.assertIsNone(family.previous("R0", mode=mode))
        self.assertEqual(family.previous("R1", mode="number"), "R0")
        with self.assertRaisesRegex(ValueError, "does not belong"):
            family.next("R1-X2", mode="number")
        with self.assertRaisesRegex(ValueError, "mode"):
            family.next("R2", mode="nearest")
        with self.assertRaises(TypeError):
            family.next("R2")

    def test_zero_padded_names_occupy_the_same_number(self):
        family = RefDesFamily("R", ["R000", "R001", "R003"])
        self.assertIn("R3", family)
        self.assertEqual(family.first_free(), "R2")
        self.assertEqual(family.first_free(0), "R2")
        self.assertEqual(family.next("R1", mode="free"), "R2")
        self.assertEqual(family.next("R2", mode="free"), "R4")
        self.assertEqual(family.previous("R2", mode="existing"), "R001")
        self.assertIsNone(family.previous("R1", mode="free"))

    def test_bare_prefix_is_zero_for_every_family(self):
        for prefix in ("R", "U", "BLOCK_%_", "R-"):
            with self.subTest(prefix=prefix):
                family = RefDesFamily(prefix, [prefix, prefix + "2"])
                self.assertEqual(family.matches(prefix + "000"), [prefix])
                self.assertIn(prefix + "0", family)
                self.assertEqual(family.first(), prefix)
                self.assertEqual(family.first_free(0), prefix + "1")
                self.assertEqual(family.next(prefix, mode="number"), prefix + "1")
                self.assertEqual(family.next(prefix, mode="existing"), prefix + "2")
                self.assertEqual(family.previous(prefix + "1", mode="existing"), prefix)
                self.assertIsNone(family.previous(prefix, mode="number"))

    def test_live_record_sources_and_captured_iterables(self):
        records = [{"RefDes": "R2"}, {"RefDes": "R4"}]
        family = RefDesFamily("R", lambda: records, get_refdes=lambda row: row["RefDes"])
        self.assertIs(family.matches("R02")[0], records[0])
        records[0]["RefDes"] = "C1"
        self.assertEqual(family.first(), "R4")
        records.append({"RefDes": "R1"})
        self.assertEqual(family.first_free(), "R2")
        records.pop()
        self.assertEqual(family.first_free(), "R1")
        captured = RefDesFamily("R", (name for name in ("R1", "R3")))
        self.assertEqual(captured.designators(), captured.designators())
        for prefix in ("R1", "R ", 2):
            with self.subTest(prefix=prefix), self.assertRaises((ValueError, TypeError)):
                RefDesFamily(prefix, [])
        with self.assertRaises(TypeError):
            RefDesFamily("R", "R1")
        with self.assertRaisesRegex(ValueError, "spaces"):
            RefDesFamily("R", ["R 1"]).first_free()
