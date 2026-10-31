"""PCB ASC headers distinguish quoted component names from raw RefDes tokens."""
import unittest

from lib.common import asc
from lib.common.conversion import ConversionReport
from lib.pcb.formats import io
from lib.pcb.model.objects import new_document, new_component, new_pad, new_net
from lib.pcb.tests.test_component_projection import design, signature


class AscRefDesTests(unittest.TestCase):
    def test_names_numbers_and_empty_refdes_use_the_receivers_header_positions(self):
        for name in ('U1', '003', '0', '', 'R-1', 'R1_X2'):
            with self.subTest(name=name):
                document = design()
                document.one('/Board/Components/Component')['RefDes'] = name
                before = asc.dumps(document, preserve=False)
                data = io.serialize(document, format='asc', report=ConversionReport())
                header = asc.loads_bytes(data).one('/Board/Components/Component')
                self.assertEqual(header.arguments[0].kind, 'string')
                if name:
                    self.assertEqual(header.arguments[1].lexeme, name)
                    self.assertNotEqual(header.arguments[1].kind, 'string')
                else:
                    self.assertEqual(len(header.arguments), 1)
                restored = io.parse(data, report=ConversionReport())
                component = restored.one('/Board/Components/Component')
                self.assertEqual((component['Name'], component['RefDes']), ('Device', name))
                net = restored.one('/Board/Nets/Net')
                self.assertTrue(all(pad['Net'] is net for pad in component.select('Pattern/Pads/Pad')))
                self.assertEqual(asc.dumps(document, preserve=False), before)
                restored.validate()

    def test_quote_marks_on_input_refdes_are_literal_name_characters(self):
        text = io.serialize(design(), format='asc', report=ConversionReport()).decode('cp1252')
        self.assertIn('(Component "Device" U1', text)
        text = text.replace('(Component "Device" U1', '(Component "Device" "U1"', 1)
        component = io.parse(text, report=ConversionReport()).one('/Board/Components/Component')
        self.assertEqual(component['Name'], 'Device')
        self.assertEqual(component['RefDes'], '"U1"')

    def test_forbidden_token_characters_report_loss_without_changing_the_design(self):
        for name, expected in (('R(1)', 'R!1!'), ('"R3"', '!R3!')):
            with self.subTest(name=name):
                document, report = design(), ConversionReport()
                component = document.one('/Board/Components/Component')
                component['RefDes'] = name
                before = signature(document.root)
                data = io.serialize(document, format='asc', report=report)
                saved = io.parse(data, report=ConversionReport()).one('/Board/Components/Component')
                self.assertEqual(saved['RefDes'], expected)
                notices = [row for row in report.warnings if row.rule == 'asc-token-sanitization']
                self.assertEqual(len(notices), 1)
                self.assertEqual(notices[0].format, 'asc')
                self.assertEqual(signature(document.root), before)

    def test_literal_bang_in_component_header_warns_about_receiver_normalization(self):
        document, report = design(), ConversionReport()
        component = document.one('/Board/Components/Component')
        component['Name'], component['RefDes'] = 'Part!Name', 'R!1'
        data = io.serialize(document, format='asc', report=report)
        saved = io.parse(data, report=ConversionReport()).one('/Board/Components/Component')
        self.assertEqual((saved['Name'], saved['RefDes']), ('Part!Name', 'R!1'))
        notices = [row for row in report.warnings if row.rule == 'asc-reader-text-normalization']
        self.assertEqual(len(notices), 1)
        self.assertFalse(any(row.rule == 'asc-token-sanitization' for row in report.notices))

    def test_unquoted_refdes_uses_the_selected_encoding_policy(self):
        document, report = design(), ConversionReport()
        component = document.one('/Board/Components/Component')
        component['RefDes'] = '\u03a93'
        data = io.serialize(document, format='asc', report=report)
        self.assertEqual(io.parse(data, report=ConversionReport()).one('/Board/Components/Component')['RefDes'], 'O3')
        self.assertTrue(any(row.rule == 'asc-text-encoding' for row in report.warnings))
        data = io.serialize(document, format='asc', encoding='utf-8-sig', report=ConversionReport())
        self.assertEqual(io.parse(data, report=ConversionReport()).one('/Board/Components/Component')['RefDes'], '\u03a93')
        self.assertEqual(component['RefDes'], '\u03a93')

    def test_lossy_token_collision_keeps_separate_components_and_connections(self):
        document = new_document()
        for name, refdes in (('Left', 'R(1)'), ('Right', 'R!1!')):
            component = document.one('/Board/Components').append(new_component(name, refdes))
            pad = component.one('Pattern/Pads').append(new_pad('1'))
            pad['Net'] = document.one('/Board/Nets').append(new_net(name))
        report = ConversionReport()
        data = io.serialize(document, format='asc', report=report)
        restored = io.parse(data, report=ConversionReport())
        components = restored.select('/Board/Components/Component')
        self.assertEqual([row['RefDes'] for row in components], ['R!1!', 'R!1!'])
        self.assertEqual([row.one('Pattern/Pads/Pad')['Net']['Name'] for row in components], ['Left', 'Right'])
        self.assertIsNot(components[0], components[1])
        self.assertTrue(any(row.rule == 'asc-token-sanitization' for row in report.warnings))
        self.assertEqual([row['RefDes'] for row in document.select('/Board/Components/Component')], ['R(1)', 'R!1!'])
        restored.validate()


if __name__ == '__main__':
    unittest.main()
