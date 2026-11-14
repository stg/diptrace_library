"""All standalone serializations regenerate group caches from one editable model."""
import unittest
import xml.etree.ElementTree as ET

from lib.common.asc import dumps as render_asc
from lib.common.conversion import ConversionReport
from lib.common.library_context import ExportContext
from lib.common.text.layout import TextLayout
from lib.common.text.vector import TextMetrics
from lib.pattern import model as patterns
from lib.component import model as components
from lib.pattern.formats import io as pattern_io
from lib.component.formats import io as component_io
from lib.pattern.formats.lib.decode import decode as decode_pattern
from lib.component.formats.eli.decode import decode as decode_component


class FixedMetrics:
    def measure(self, text, **settings):
        return TextMetrics(100, 10)


class LibraryGroupCoordinateTests(unittest.TestCase):
    def examples(self, *, text=False):
        for family, model, api, native, xml, decoder in (
                ('pattern', patterns, pattern_io, 'lib', 'libxml', decode_pattern),
                ('component', components, component_io, 'eli', 'elixml', decode_component)):
            document = model.new_library('Group example')
            if family == 'pattern':
                owner = document.one('/Library/Patterns').append(model.new_pattern('Example'))
                group_path = 'Pattern_Groups'
                raw_path = 'Patterns/Pattern/Pattern_Groups/pt'
                asc_path = '/Library/Patterns/Pattern/Pattern_Groups/pt'
                xml_path = 'Patterns/Pattern/Groups/Group'
            else:
                entry = document.one('/Library/Components').append(model.new_component('Example'))
                owner = entry.one('Parts/Part')
                group_path = 'Groups'
                raw_path = 'Components/Component/Parts/Part/Groups/pt'
                asc_path = '/Library/Components/Component/Part/Groups/pt'
                xml_path = 'Components/Component/Part/Groups/Group'
            group = owner.one(group_path).append(model.new_group())
            if text:
                shape = owner.one('Shapes').append(model.new_drawing(kind=7 if family == 'pattern' else 10))
                shape.one('Points_New').add('pt', 0, 0)
                shape.one('TextLine').add('pt', 'A name')
                shape['TextHorz'], shape['TextVert'] = -1, -1
                shape['FontWidth'], shape['FontSize'] = -1, 6
                shape['Group'] = group
            elif family == 'pattern':
                member = owner.one('Pads').append(model.new_pad('1', x=12, y=6))
                member['Group'] = group
            else:
                member = owner.one('Pins').append(model.new_pin())
                member['X'], member['Y'], member['Length'], member['ShowName'] = 12, 6, 12, False
                member['Group'] = group
            yield family, document, owner, group, group_path, api, native, xml, decoder, raw_path, asc_path, xml_path

    def test_import_discards_stale_centres_and_positional_codes(self):
        for family, document, owner, group, group_path, api, _, _, _, _, asc_path, _ in self.examples():
            with self.subTest(family=family):
                syntax = api.project(document, format='asc', report=ConversionReport())
                syntax.one(asc_path).set_values('Y', 97, 999, -999)
                restored = api.parse(render_asc(syntax), report=ConversionReport())
                result = restored.one(owner.path+'/'+group_path+'/pt')
                self.assertEqual(0, result['Id'])
                self.assertNotIn(999, (result['X'], result['Y']))
                self.assertNotIn(-999, (result['X'], result['Y']))
                self.assertIsNone(result.child('X'))
                self.assertIsNone(result.child('Y'))
                restored.validate()

    def test_all_three_formats_settle_after_the_first_projection_without_source_edits(self):
        for family, document, _, group, _, api, native, xml, _, _, _, _ in self.examples():
            before = [(node.path, node.values) for node in document.root.walk(include_self=True)]
            for format in (native, 'asc', xml):
                with self.subTest(family=family, format=format):
                    current, previous = document, None
                    for cycle in range(3):
                        current = api.parse(api.serialize(current, format=format, report=ConversionReport()),
                                            report=ConversionReport())
                        snapshot = [(node.path, node.values) for node in current.root.walk(include_self=True)]
                        if previous is not None:
                            self.assertEqual(previous, snapshot)
                        previous = snapshot
                        current.validate()
            self.assertEqual(before, [(node.path, node.values) for node in document.root.walk(include_self=True)])

    def test_optional_layout_drives_every_output_cache_without_entering_the_model(self):
        context = ExportContext(text_layout=TextLayout(vector_metrics=FixedMetrics()))
        for family, document, _, group, _, api, native, xml, decoder, raw_path, asc_path, xml_path in self.examples(text=True):
            before = group['X'], group['Y']
            for format in (native, 'asc', xml):
                with self.subTest(family=family, format=format):
                    data = api.serialize(document, format=format, context=context, report=ConversionReport())
                    if format == native:
                        result = decoder(data).root.one(raw_path).values[2:4]
                    elif format == 'asc':
                        result = api.project(document, format=format, context=context,
                                             report=ConversionReport()).one(asc_path).values[2:4]
                    else:
                        node = ET.fromstring(data).find(xml_path)
                        result = float(node.get('X'))*3, -float(node.get('Y'))*3
                    self.assertAlmostEqual(50.5, result[0], places=8)
                    self.assertAlmostEqual(5.5, result[1], places=8)
                    restored = api.parse(data, report=ConversionReport())
                    self.assertEqual(before, (restored.one(group.path)['X'], restored.one(group.path)['Y']))
            self.assertEqual(before, (group['X'], group['Y']))
            document.validate()
