"""Legacy rules become ordinary current facts, with precise format gates."""
from decimal import Decimal
from types import SimpleNamespace
import unittest

from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.model import Document, Element
from lib.pcb.formats.dip.rule_defaults import modernize_rules


def fixture(version, *, last=True, silk=False):
    board = Element('Board')
    net_class = board.add('NetClasses').add('NetClass', 'Sensitive')
    for _ in range(2):
        net_class.child('LayProperties') or net_class.add('LayProperties')
        net_class.one('LayProperties').add('LayProperty').add('Width', Decimal('0.8'))
    for kind in (('DRC', 'LastDRC') if last else ('DRC',)):
        drc = board.add(kind)
        drc.add('Name', 'Authored '+kind)
        drc.add('CheckSilk', silk)
        drc.add('AllLayers', True)
        clearances = drc.add('LayClearances')
        for _ in range(2):
            clearances.add('LayClearance').add('ClearanceDetails').add('TraceToVia', Decimal('0.9'))
    return SimpleNamespace(header=SimpleNamespace(version=version), board=board)


class RuleDefaultTests(unittest.TestCase):
    def test_earlier_class_length_bounds_modernize_into_target_and_full_delta(self):
        for version in (31, 37, 42):
            for minimum, maximum, fixed, delta in ((0, 255, Decimal('127.5'), 255),
                                                  (10, 2, 6, 8),
                                                  (0, Decimal('.0002'), Decimal('.0001'), Decimal('.0002')),
                                                  (0, Decimal('.0001'), -1, Decimal('7.62')),
                                                  (0, 0, -1, Decimal('7.62'))):
                with self.subTest(version=version, maximum=maximum):
                    source = fixture(version)
                    net_class = source.board.one('NetClasses/NetClass')
                    net_class.add('MinLength', minimum)
                    net_class.add('MaxLength', maximum)
                    net_class.add('CheckLength', False)
                    modernize_rules(source)
                    self.assertEqual((net_class['FixedLength'], net_class['LengthDelta']), (fixed, delta))
                    self.assertFalse(net_class['CheckLength'])
                    modernize_rules(source)
                    self.assertEqual((net_class['FixedLength'], net_class['LengthDelta']), (fixed, delta))

    def test_class_extensions_have_distinct_version_gates(self):
        for version in (39, 40, 42, 43, 47):
            with self.subTest(version=version):
                decoded = fixture(version)
                modernize_rules(decoded)
                rule = decoded.board.one('NetClasses/NetClass')
                self.assertEqual(rule.scalar('Phase'), 6 if version < 40 else None)
                self.assertEqual(rule.scalar('Phase_ErrorLength'), 15 if version < 40 else None)
                for row in rule.select('LayProperties/LayProperty'):
                    self.assertEqual(row.scalar('Neck_Width'), -1 if version < 40 else None)
                    self.assertEqual(row.scalar('Neck_DifClearance'), -1 if version < 40 else None)
                    self.assertEqual(row.scalar('Neck_MaxLength'), 0 if version < 40 else None)
                    self.assertEqual(row['Width'], Decimal('0.8'))
                self.assertEqual(rule.scalar('LengthDelta'), Decimal('7.62') if version < 43 else None)
                self.assertEqual(rule.scalar('FixedLength'), -1 if version < 43 else None)

    def test_same_net_and_object_rules_are_initialized_only_before_45(self):
        for version in (44, 45):
            with self.subTest(version=version):
                decoded = fixture(version)
                modernize_rules(decoded)
                for kind in ('DRC', 'LastDRC'):
                    drc = decoded.board.one(kind)
                    self.assertEqual(drc.scalar('CheckKeepouts'), False if version < 45 else None)
                    self.assertEqual(drc.scalar('CheckSameNet'), False if version < 45 else None)
                    self.assertEqual(drc.scalar('CheckSameComponentPads'), True if version < 45 else None)
                    for row in drc.select('LayClearances/LayClearance'):
                        for name in ('SameTraceToTrace', 'SameSmdToVia', 'SameSmdToPad', 'SameSmdToSmd'):
                            self.assertEqual(row.scalar(name), 0 if version < 45 else None)

    def test_silk_defaults_depend_on_existing_check_and_have_a_47_gate(self):
        for version in (46, 47):
            for enabled in (False, True):
                with self.subTest(version=version, enabled=enabled):
                    decoded = fixture(version, silk=enabled)
                    modernize_rules(decoded)
                    for kind in ('DRC', 'LastDRC'):
                        drc = decoded.board.one(kind)
                        self.assertEqual(drc['CheckSilk'], enabled)
                        expected = (0 if enabled else Decimal('0.45')) if version < 47 else None
                        self.assertEqual(drc.scalar('SilkClearance'), expected)
                        self.assertEqual(drc.scalar('CheckCourtyard'), False if version < 47 else None)

    def test_missing_last_used_snapshot_stays_absent(self):
        for version in (39, 40, 41):
            with self.subTest(version=version):
                decoded = fixture(version, last=False)
                modernize_rules(decoded)
                self.assertIsNone(decoded.board.child('LastDRC'))
                self.assertEqual(decoded.board.one('DRC')['Name'], 'Authored DRC')

    def test_supplied_last_used_snapshot_keeps_its_own_rule_choices(self):
        decoded = fixture(46)
        decoded.board.one('LastDRC/CheckSilk').set_values(True)
        modernize_rules(decoded)
        self.assertEqual(decoded.board.one('DRC')['SilkClearance'], Decimal('0.45'))
        self.assertEqual(decoded.board.one('LastDRC')['SilkClearance'], 0)
        self.assertEqual(decoded.board.one('LastDRC')['Name'], 'Authored LastDRC')

    def test_current_authored_values_are_not_overwritten(self):
        decoded = fixture(47)
        rule = decoded.board.one('NetClasses/NetClass')
        rule.add('Phase', 23)
        rule.add('LengthDelta', Decimal('1.2'))
        for kind in ('DRC', 'LastDRC'):
            drc = decoded.board.one(kind)
            drc.add('CheckSameComponentPads', False)
            drc.add('CheckCourtyard', True)
            drc.add('SilkClearance', Decimal('0.7'))
        before = [(node.path, node.values) for node in decoded.board.walk(include_self=True)]
        modernize_rules(decoded)
        self.assertEqual([(node.path, node.values) for node in decoded.board.walk(include_self=True)], before)

    def test_modernization_is_idempotent_and_reported_as_information(self):
        @import_diagnostics('dip')
        def run(decoded):
            modernize_rules(decoded)
            return Document(Element(''))
        decoded, report = fixture(39, last=False), ConversionReport()
        run(decoded, report=report)
        before = [(node.path, node.values) for node in decoded.board.walk(include_self=True)]
        self.assertEqual(len(report.infos), 1)
        self.assertFalse(report.warnings or report.errors)
        run(decoded, report=report)
        self.assertEqual(len(report.infos), 1)
        self.assertEqual([(node.path, node.values) for node in decoded.board.walk(include_self=True)], before)


if __name__ == '__main__':
    unittest.main()
