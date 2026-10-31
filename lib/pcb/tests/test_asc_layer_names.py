"""Copper-layer names occupy raw ASC tokens, independently of layer identity."""
import unittest

from lib.common import asc
from lib.common.conversion import ConversionReport
from lib.pcb.formats import io
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_component_projection import design, signature


class AscLayerNameTests(unittest.TestCase):
    def test_empty_numeric_and_spaced_names_keep_layer_connections(self):
        for name, token in (('Bottom', 'Bottom'), ('003', '003'), ('0', '0'),
                            ('', ''), ('Inner  Layer ', 'Inner!!Layer!')):
            with self.subTest(name=name):
                document, report = design(), ConversionReport()
                layer = document.one('/Board/Layers/Layer[2]')
                document.one('/Board/Components/Component')['Layer'] = layer
                layer['Name'] = name
                before = signature(document.root)
                data = io.serialize(document, format='asc', report=report)
                syntax = asc.loads_bytes(data)
                header = syntax.one('/Board/Layers/Name[2]')
                if token:
                    self.assertEqual(header.arguments[0].lexeme, token)
                    self.assertNotEqual(header.arguments[0].kind, 'string')
                else:
                    self.assertEqual(header.arguments, ())
                self.assertEqual(syntax.one('/Units').arguments[0].kind, 'string')
                restored = io.parse(data, report=ConversionReport())
                saved_layer = restored.one('/Board/Layers/Layer[2]')
                component = restored.one('/Board/Components/Component')
                self.assertEqual(saved_layer['Name'], name)
                self.assertIs(component['Layer'], saved_layer)
                self.assertIs(component['Via']['ToLayer'], saved_layer)
                self.assertFalse(any(row.rule in ('asc-token-sanitization', 'layer-name-spelling',
                                                  'asc-reader-text-normalization')
                                     for row in report.warnings))
                self.assertEqual(signature(document.root), before)
                restored.validate()

    def test_input_quotes_are_literal_and_remain_in_binary_and_xml(self):
        document = design()
        document.one('/Board/Components/Component')['Layer'] = document.one('/Board/Layers/Layer[2]')
        text = io.serialize(document, format='asc', report=ConversionReport()).decode('cp1252')
        self.assertIn('(Name Bottom', text)
        text = text.replace('(Name Bottom', '(Name "Inner!!Layer!"', 1)
        restored = io.parse(text, report=ConversionReport())
        self.assertEqual(restored.one('/Board/Layers/Layer[2]')['Name'], '"Inner  Layer "')
        for format in ('dip', 'dipxml'):
            with self.subTest(format=format):
                report = ConversionReport()
                data = io.serialize(restored, format=format, report=report)
                saved = io.parse(data, report=ConversionReport())
                self.assertEqual(saved.one('/Board/Layers/Layer[2]')['Name'], '"Inner  Layer "')
                component = saved.one('/Board/Components/Component')
                self.assertIs(component['Via']['ToLayer'],
                              saved.one('/Board/Layers/Layer[2]'))
                if format == 'dip':
                    self.assertIs(component['Layer'], saved.one('/Board/Layers/Layer[2]'))
                else:
                    # XML lacks the independent component copper-layer field;
                    # its existing omission diagnostic is separate from names.
                    self.assertTrue(any(row.rule == 'component-connected-layer' for row in report.warnings))

    def test_token_delimiters_report_loss_without_mutating_layer_names(self):
        for name, token, normalized in (('Inner(A)', 'Inner!A!', 'Inner A '),
                                         ('"Inner"', '!Inner!', ' Inner '),
                                         ('Inner\nLayer', 'Inner!Layer', 'Inner Layer')):
            with self.subTest(name=name):
                document, report = design(), ConversionReport()
                layer = document.one('/Board/Layers/Layer[2]')
                layer['Name'] = name
                before = signature(document.root)
                data = io.serialize(document, format='asc', report=report)
                self.assertEqual(asc.loads_bytes(data).one('/Board/Layers/Name[2]').arguments[0].lexeme, token)
                restored = io.parse(data, report=ConversionReport())
                self.assertEqual(restored.one('/Board/Layers/Layer[2]')['Name'], normalized)
                self.assertEqual([row.rule for row in report.warnings if row.rule.startswith('asc-')],
                                 ['asc-token-sanitization'])
                self.assertEqual(signature(document.root), before)
                restored.validate()

    def test_literal_bang_uses_the_layer_specific_loss_notice(self):
        document, report = design(), ConversionReport()
        layer = document.one('/Board/Layers/Layer[2]')
        layer['Name'] = 'Bottom!side'
        data = io.serialize(document, format='asc', report=report)
        restored = io.parse(data, report=ConversionReport())
        self.assertEqual(restored.one('/Board/Layers/Layer[2]')['Name'], 'Bottom side')
        self.assertEqual(layer['Name'], 'Bottom!side')
        self.assertEqual([row.rule for row in report.warnings], ['layer-name-spelling'])

    def test_layer_tokens_follow_the_selected_output_encoding(self):
        document, report = design(), ConversionReport()
        layer = document.one('/Board/Layers/Layer[2]')
        layer['Name'] = '\u03a9 plane'
        data = io.serialize(document, format='asc', report=report)
        restored = io.parse(data, report=ConversionReport())
        self.assertEqual(restored.one('/Board/Layers/Layer[2]')['Name'], 'O plane')
        self.assertTrue(any(row.rule == 'asc-text-encoding' for row in report.warnings))
        data = io.serialize(document, format='asc', encoding='utf-8-sig', report=ConversionReport())
        restored = io.parse(data, report=ConversionReport())
        self.assertEqual(restored.one('/Board/Layers/Layer[2]')['Name'], '\u03a9 plane')
        self.assertEqual(layer['Name'], '\u03a9 plane')

    def test_multiple_layer_name_tokens_are_rejected(self):
        text = io.serialize(design(), format='asc', report=ConversionReport()).decode('cp1252')
        text = text.replace('(Name Bottom', '(Name Bottom extra', 1)
        with self.assertRaisesRegex(PcbError, 'at most one copper-layer name token'):
            io.parse(text, report=ConversionReport())


if __name__ == '__main__':
    unittest.main()
