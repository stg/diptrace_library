"""Portable ANSI file views preserve Unicode authoring values and wire units."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lib.design.dch_binary import Cursor
from lib.design.windows_1252 import encode, decode, project
from lib.design import read_source as read, new_schematic, ExportReport, AscExportContext, parse, parse_source
from lib.design.schematic_objects import new_symbol
from lib.design.schematic_refs import bind_schematic_references
import tempfile


def header(version):
    return b'\x07DTSCHEM'+(version+1_000_000).to_bytes(3, 'big')


class EncodingTests(unittest.TestCase):
    def test_explicit_utf8_preserves_unicode_before_asc_text_projection(self):
        source = new_schematic()
        part = source.one('/Schematic/Components').append(new_symbol('Power', 'U1'))
        part.set_field('Value', '\u03a9 \u6f22 \U0001f600')
        bind_schematic_references(source)
        context = AscExportContext(encoding='cp1252')
        report = ExportReport()
        output = source.to_asc_bytes(encoding='utf-8-sig', context=context, report=report)
        self.assertTrue(output.startswith(b'\xef\xbb\xbf'))
        self.assertIn(part.scalar('Value'), output.decode('utf-8-sig'))
        self.assertNotIn('asc-text-encoding', {notice.rule for notice in report.notices})
        self.assertEqual(context.encoding, 'cp1252')
        self.assertEqual(part.scalar('Value'), '\u03a9 \u6f22 \U0001f600')

    def test_shared_asc_cycles_use_an_explicit_encoding_without_import_history(self):
        source = new_schematic()
        part = source.one('/Schematic/Components').append(new_symbol('Power', 'U1'))
        bind_schematic_references(source)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder)/'unicode.asc'
            for encoding, text in (('utf-8-sig', '\u03a9'), ('cp1252', '\u00e9')):
                part.set_field('Value', text)
                data = source.to_asc_bytes(encoding=encoding, report=ExportReport())
                for _ in range(3):
                    path.write_bytes(data)
                    shared = read(path).as_schematic()
                    self.assertNotIn('asc_encoding', shared.metadata)
                    self.assertEqual(shared.one('/Schematic/Components/Part').scalar('Value'), text)
                    report = ExportReport()
                    data = shared.to_asc_bytes(encoding=encoding, report=report)
                    self.assertEqual(data.startswith(b'\xef\xbb\xbf'), encoding == 'utf-8-sig')
                    self.assertNotIn('asc-text-encoding', {notice.rule for notice in report.notices})

    def test_ansi_input_is_not_guessed_as_utf8_when_both_decodings_are_valid(self):
        data = b'(Name "\xc3\xa9")\r\n'
        self.assertEqual(parse_source(data, format='asc').one('/Name').values, ('\u00c3\u00a9',))
        self.assertEqual(parse_source(data, format='asc', encoding='utf-8').one('/Name').values, ('\u00e9',))
        self.assertEqual(parse_source(b'\xef\xbb\xbf'+data, format='asc').one('/Name').values, ('\u00e9',))

    def test_shared_export_defaults_do_not_depend_on_import_encoding(self):
        source = new_schematic()
        part = source.one('/Schematic/Components').append(new_symbol('Power', 'U1'))
        part.set_field('Value', '\u03a9')
        bind_schematic_references(source)
        data = source.to_asc_bytes(encoding='utf-8-sig', report=ExportReport())
        shared = parse(data, format='asc')
        report = ExportReport()
        canonical = shared.to_asc_bytes(report=report)
        self.assertFalse(canonical.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(parse(canonical, format='asc').one('/Schematic/Components/Part').scalar('Value'), 'O')
        self.assertIn('asc-text-encoding', {notice.rule for notice in report.warnings})
        self.assertEqual(shared.one('/Schematic/Components/Part').scalar('Value'), '\u03a9')

    def test_every_ansi_byte_round_trips_including_control_slots(self):
        raw = bytes(range(256))
        text = decode(raw)
        self.assertEqual(encode(text, best_fit=False), raw)
        self.assertEqual(Cursor(header(29)+(1_000_256).to_bytes(3, 'big')+raw).text(), text)
        self.assertEqual([ord(text[i]) for i in (0x81, 0x8d, 0x8f, 0x90, 0x9d)], [0x81, 0x8d, 0x8f, 0x90, 0x9d])

    def test_output_best_fit_and_utf16_default_character_count(self):
        text = '\u03a9 \u03bc \u0101 \U0001f600 \ud800'
        self.assertEqual(encode(text), b'O \xb5 a ?? ?')
        self.assertEqual(project(text), 'O \xb5 a ?? ?')
        self.assertEqual(text[0], '\u03a9')
        with self.assertRaises(UnicodeEncodeError):
            encode(text, best_fit=False)

    def test_dch_unicode_reader_retains_unpaired_code_units(self):
        for text in ('\ud800', '\udfff', 'A\ud800Z', '\ud800\ud800', '\U0001f600'):
            raw = text.encode('utf-16-be', errors='surrogatepass')
            cursor = Cursor(header(32)+(len(raw)//2).to_bytes(2, 'big')+raw)
            self.assertEqual(cursor.text(), text)
            self.assertEqual(cursor.pos, len(cursor.data))

    def test_asc_control_slots_remain_editable_and_strict(self):
        raw=b'(Name "\x81\x8d\x8f\x90\x9d")\r\n'
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'controls.asc'
            path.write_bytes(raw)
            document=read(path)
            self.assertEqual(document.to_asc_bytes(),raw)
            name=document.one('/Name')
            name.set_values(name.values[0]+' edited')
            self.assertEqual(document.to_asc_bytes(),raw.replace(b'")',b' edited")'))
            name.set_values('\u03a9')
            with self.assertRaises(UnicodeEncodeError):
                document.to_asc_bytes()


if __name__ == '__main__':
    unittest.main()
