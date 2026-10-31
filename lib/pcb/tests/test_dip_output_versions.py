"""Older output versions report projection losses without changing the design."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.pcb.formats.capabilities import DIP
from lib.pcb.formats.dip.binary import read_header, MIN_VERSION, MAX_KNOWN_VERSION, UnsupportedVersionError
from lib.pcb.formats.dip.write import encode
from lib.pcb.model.objects import new_document
from lib.pcb.tests.test_dip_output import configured_document, reopen


class DipOutputVersionTests(unittest.TestCase):
    def test_capability_policy_and_binary_boundaries_share_one_declaration(self):
        self.assertEqual((MIN_VERSION, MAX_KNOWN_VERSION), (min(DIP.read_versions), max(DIP.read_versions)))
        self.assertEqual(DIP.write_versions, tuple(range(54, 63)))
        for version in DIP.write_versions:
            data = encode(new_document(), version=version, report=ConversionReport())
            self.assertEqual(read_header(data).version, version)
        for version in (31, 53, 63, True, 54.0):
            with self.subTest(version=version), self.assertRaises(UnsupportedVersionError):
                encode(new_document(), version=version, report=ConversionReport())

    def test_empty_documents_stabilize_without_spurious_downgrade_warnings(self):
        document = new_document()
        before = dumps(document, preserve=False)
        for version in DIP.write_versions:
            with self.subTest(version=version):
                report = ConversionReport()
                data = encode(document, version=version, report=report)
                rebuilt = reopen(data, report=ConversionReport())
                self.assertEqual(encode(rebuilt, version=version, report=ConversionReport()), data)
                self.assertEqual(report.warnings, [])
        self.assertEqual(dumps(document, preserve=False), before)

    def test_each_feature_uses_its_own_gate_and_export_is_detached(self):
        document = configured_document()
        board = document.one('/Board')
        board['ShieldGroup'], board['SchemNetClasses'] = 19, True
        board['CompFontSize'], board['CompFontMono'] = Decimal('2.375'), True
        component = board.one('Components/Component')
        component['ShieldGroup'], component['MarkingFontSize'] = 23, Decimal('1.625')
        net = board.one('Nets/Net')
        net['HiddenId'], net['AllowLoops'] = 901, True
        net.one('Traces/Trace[1]/Points/Point[1]')['ShieldGroup'] = 31
        pour = board.one('CopperPours/CopperPour')
        pour['ShieldGroup'], pour['TraceShieldGroup'] = 37, 41
        shape = board.one('Shapes/Shape[1]')
        shape['PictureFlipped'] = True
        board['PanelDX'], board['PanelDY'] = Decimal('1.5'), Decimal('2.5')
        for name, value in zip(('LeftGap', 'RightGap', 'TopGap', 'BottomGap'), (3, 4, 5, 6)):
            board.one('Panel')[name] = value
        before = dumps(document, preserve=False)
        for version in DIP.write_versions:
            with self.subTest(version=version):
                report = ConversionReport()
                data = encode(document, version=version, report=report)
                rebuilt = reopen(data, report=ConversionReport())
                current = rebuilt.one('/Board')
                self.assertEqual(current.get('ShieldGroup', -1), 19 if version >= 57 else -1)
                self.assertEqual(current.one('Components/Component').get('ShieldGroup', -1), 23 if version >= 57 else -1)
                self.assertEqual(current.one('Nets/Net').get('HiddenId', -1), 901 if version >= 56 else -1)
                self.assertEqual(current.one('Nets/Net').get('AllowLoops', False), version >= 62)
                self.assertEqual(current.one('Nets/Net/Traces/Trace[1]/Points/Point[1]').get('ShieldGroup', -1), 31 if version >= 57 else -1)
                self.assertEqual(current.one('CopperPours/CopperPour').get('TraceShieldGroup', -1), 41 if version >= 58 else -1)
                self.assertEqual(current.one('Shapes/Shape[1]').get('PictureFlipped', False), version >= 59)
                self.assertEqual(current['SchemNetClasses'], version >= 60)
                self.assertEqual(current['CompFontSize'], Decimal('2.375') if version >= 61 else 2)
                self.assertEqual(current.get('CompFontMono', False), version >= 61)
                self.assertEqual(current.one('Components/Component')['MarkingFontSize'], Decimal('1.625') if version >= 61 else 2)
                self.assertEqual(current.one('Panel')['LeftGap'], 3 if version >= 55 else Decimal('1.5'))
                rules = {notice.rule for notice in report.warnings}
                for rule, first_version in (
                        ('panel-side-gaps', 55), ('persistent-net-id', 56), ('shield-groups', 57),
                        ('pour-trace-shield', 58), ('picture-flipped', 59), ('schematic-net-classes', 60),
                        ('fractional-font-size', 61), ('monospaced-font', 61), ('net-loop-policy', 62)):
                    self.assertEqual(rule in rules, version < first_version, rule)
                self.assertEqual(encode(rebuilt, version=version, report=ConversionReport()), data)
                rebuilt.references.validate()
        self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
