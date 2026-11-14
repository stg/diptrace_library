"""Wire values are independent of document-family version numbering."""
from decimal import Decimal, localcontext
import re
import unittest

from lib.common.binary import BinaryReader, BinaryWriter
from lib.common.binary_records import RecordReader, RecordWriter, grid_step_value, write_grid_step
from lib.common.model import Document, Element
from lib.common.schema import Field, Record
from lib.common.conversion import ConversionReport


class BinaryTests(unittest.TestCase):
    def test_later_drawing_coordinates_replace_the_pair_without_changing_identity(self):
        from lib.common.drawing_codec import replace_point_coordinates

        class Reader(RecordReader, BinaryReader):
            source_format = 'binary'

        writer = BinaryWriter()
        for value in (1, 2, 5, 7):
            writer.number(value)
        for retained, compact in ((False, True), (True, True), (False, False)):
            with self.subTest(retained=retained, compact=compact):
                reader = Reader(writer.buffer, source='fixture')
                reader.retain_source, reader.compact_fields = retained, compact
                shape = Element('Shape')
                points = reader.points(shape.add('Points_New'), 1)
                point = points.one('pt')
                identity = point.uid
                held = point.child('X') if point.schema is not None else None
                replace_point_coordinates(reader, shape)
                self.assertIs(points.one('pt'), point)
                self.assertEqual(point.uid, identity)
                self.assertEqual(point.values, (5, 7))
                self.assertEqual((point.source.start, point.source.end), (8, 16))
                if held is not None:
                    self.assertIs(point.child('X'), held)
                    self.assertEqual(held.values, (5,))
                if retained:
                    self.assertEqual((point.arguments[0].source.start, point.arguments[0].source.end), (8, 12))

    def test_incomplete_replacement_does_not_write_one_coordinate(self):
        from lib.common.drawing_codec import replace_point_coordinates

        class Reader(RecordReader, BinaryReader):
            retain_source = False

        writer = BinaryWriter()
        for value in (1, 2, 5):
            writer.number(value)
        reader = Reader(writer.buffer)
        shape = Element('Shape')
        point = reader.points(shape.add('Points_New'), 1).one('pt')
        with self.assertRaisesRegex(ValueError, 'truncated'):
            replace_point_coordinates(reader, shape)
        self.assertEqual(point.values, (1, 2))

    def test_neutral_point_decode_is_editable_and_preserves_live_field_handles(self):
        class Reader(RecordReader, BinaryReader):
            retain_source = False

        points = Element('Points')
        reader = Reader(bytes.fromhex('3b9afa39 3b9b1820'))
        self.assertIs(reader.points(points, 1), points)
        point = points.one('pt')
        self.assertEqual(point.values, (1.2345, 2.0))
        held = point.child('X')
        point['X'] = 3
        self.assertEqual(held.values, (3,))
        with self.assertRaises(ValueError):
            point['X'] = float('nan')
        self.assertEqual(held.values, (3,))
        clone = point.clone()
        clone['X'] = 4
        self.assertEqual(point['X'], 3)
        point.schema.validate_fields(point)

    def test_neutral_point_debug_and_uncompacted_modes_keep_record_metadata(self):
        class Reader(RecordReader, BinaryReader):
            pass

        for retained, compact in ((True, True), (False, False)):
            with self.subTest(retained=retained, compact=compact):
                reader = Reader(bytes.fromhex('3b9afa39 3b9b1820'), source='fixture')
                reader.retain_source, reader.compact_fields = retained, compact
                points = reader.points(Element('Points'), 1)
                point = points.one('pt')
                self.assertIsNone(point.schema)
                self.assertEqual(point.values, (1.2345, 2.0))
                self.assertEqual((point.source.start, point.source.end), (0, 8))
                if retained:
                    self.assertEqual((point.arguments[0].source.start, point.arguments[0].source.end), (0, 4))

    def test_neutral_point_count_and_truncation_do_not_attach_partial_records(self):
        class Reader(RecordReader, BinaryReader):
            retain_source = False

        points = Element('Points')
        reader = Reader(bytes.fromhex('3b9afa39 3b'))
        with self.assertRaisesRegex(ValueError, 'truncated'):
            reader.points(points, 1)
        self.assertFalse(points.children())
        for count in (-1, True, 1.5):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, 'count'):
                Reader(b'').points(points, count)
        Reader(b'').points(points, 0)
        self.assertFalse(points.children())

    def test_decoder_construction_preserves_content_and_observed_field_views(self):
        for compact in (False, True):
            class Reader(RecordReader, BinaryReader):
                compact_fields = compact
            schema = Record('Row', {'Label': Field('Label', 'text'),
                'Size': Field('Size', 'number'), 'Flags': Field('Flags', 'tuple')})
            row = Element('Row').bind_schema(schema)
            reader = Reader(b'')
            label = reader.add(row, 'Label', 'first')
            label.annotations['note'] = 'keep'
            reader.add_into(row, 'Size', 0)
            reader.add_into(row, 'Flags', False, 2)
            collection = reader.add(row, 'Items')
            reader.add_into(collection, 'Item', 'text', 3)
            self.assertEqual(row.children(), [label, row.one('Size'), row.one('Flags'), collection])
            self.assertEqual(row['Flags'], (False, 2))
            self.assertEqual(collection.one('Item').values, ('text', 3))
            self.assertIs(label.parent, row)
            self.assertIs(row.one('Label'), label)
            label.set_values('edited')
            self.assertEqual(row['Label'], 'edited')
            self.assertEqual(label.annotations, {'note': 'keep'})
            with self.assertRaises(ValueError):
                reader.add_into(row, 'Bad', float('nan'))
            self.assertIsNone(row.child('Bad'))
            # Raw duplicate content is retained for the normal audit to reject.
            reader.add_into(row, 'Label', 'duplicate')
            self.assertEqual(len(row.children('Label')), 2)
            with self.assertRaisesRegex(ValueError, 'more than once'):
                schema.validate_fields(row)

    def test_decoder_construction_does_not_expand_unused_compact_fields(self):
        class Reader(RecordReader, BinaryReader):
            compact_fields = True
            retain_source = False
        row = Element('Row').bind_schema(Record('Row', {'Size': Field('Size', 'number')}))
        Reader(b'').add_into(row, 'Size', 0)
        self.assertFalse(row._content.handles)
        self.assertFalse(row._content.details)
        self.assertEqual(row['Size'], 0)

    def test_record_writer_reads_scalar_slots_without_materializing_fields(self):
        node = Element('Row').bind_schema(Record('Row', {
            'Size': Field('Size', 'number'), 'Enabled': Field('Enabled', 'boolean')}))
        node['Size'], node['Enabled'] = Decimal('1.2345'), True
        node._compact_fields()
        writer = RecordWriter()
        writer.field(node, 'Size', 'number')
        writer.field(node, 'Enabled', 'boolean')
        self.assertEqual(writer.buffer, bytes.fromhex('3b9afa39 01'))
        self.assertFalse(node._content.handles)

    def test_later_scalar_codec_replaces_equal_earlier_value_in_both_source_modes(self):
        class Reader(RecordReader, BinaryReader):
            pass

        schema = Record('Row', {'Size': Field('Size', 'number')})
        data = bytes.fromhex('0f4242 3b9b1820')  # integer 2, number 2.0000
        for compact in (False, True):
            for retained in (False, True):
                for batch in (False, True):
                    with self.subTest(compact=compact, retained=retained, batch=batch):
                        node = Element('Row').bind_schema(schema)
                        reader = Reader(data)
                        reader.compact_fields, reader.retain_source = compact, retained
                        reader.field(node, 'Size', 'integer')
                        if batch:
                            reader.fields(node, (('Size', 'number'),), replace=True)
                        else:
                            reader.field(node, 'Size', 'number', replace=True)
                        self.assertIs(type(node['Size']), float)
                        self.assertEqual(node['Size'], 2.0)

    def test_declared_scalar_import_avoids_leaf_objects_without_debug_data(self):
        class Reader(RecordReader, BinaryReader):
            compact_fields = True
            retain_source = False

        schema = Record('Row', {'Count': Field('Count', 'integer'),
                               'Enabled': Field('Enabled', 'boolean'),
                               'Caption': Field('Caption', 'text')})
        document = Document()
        node = document.root.append(Element('Row').bind_schema(schema))
        reader = Reader(bytes.fromhex('0f4243 00 0001 0041'))
        reader.fields(node, (('Count', 'integer'), ('Enabled', 'boolean'), ('Caption', 'text')))
        self.assertEqual(reader.pos, len(reader.data))
        self.assertEqual((node['Count'], node['Enabled'], node['Caption']), (3, False, 'A'))
        document.validate()
        self.assertEqual(len(node._content.handles), 0)
        self.assertFalse(node._content.details)

    def test_known_scalar_bytes(self):
        # A mix of signed, unsigned, fixed-point and text values exercises the
        # actual wire representation, rather than only our reader/writer pair.
        data = bytes.fromhex('0f423f 3b9afa39 01 563412 0002 0041 03a9')
        reader = BinaryReader(data)
        self.assertEqual(reader.integer(), -1)
        self.assertEqual(reader.number(), 1.2345)
        self.assertIs(reader.boolean(), True)
        self.assertEqual(reader.color(), 0x123456)
        self.assertEqual(reader.text(), 'A\u03a9')
        self.assertEqual(reader.pos, len(data))
        writer = BinaryWriter()
        writer.integer(-1)
        writer.number(Decimal('1.2345'))
        writer.boolean(True)
        writer.color(0x123456)
        writer.text('A\u03a9')
        self.assertEqual(bytes(writer.buffer), data)

    def test_fixed_point_decode_does_not_use_decimal_context(self):
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(BinaryReader(bytes.fromhex('3b9afa39')).number(), 1.2345)

    def test_fixed_point_rounding_uses_exact_decimal_ties_and_ignores_caller_context(self):
        for value, expected in (('.00015', '.0002'), ('-.00015', '-.0002'),
                                 ('1.50005', '1.5000'), ('-1.50005', '-1.5000'),
                                 ('.00014999999999999999999999', '.0001'),
                                 ('.00015000000000000000000001', '.0002')):
            for precision in (2, 28):
                with self.subTest(value=value, precision=precision), localcontext() as context:
                    context.prec = precision
                    writer = BinaryWriter()
                    writer.number(Decimal(value))
                    self.assertEqual(BinaryReader(bytes(writer.buffer)).number(), float(expected))

    def test_float_and_decimal_spellings_use_the_same_number_projection(self):
        for value in (.00015, -.00015, 1.50005, -1.50005):
            with self.subTest(value=value):
                first, second = BinaryWriter(), BinaryWriter()
                first.number(value)
                second.number(Decimal(str(value)))
                self.assertEqual(first.buffer, second.buffer)

    def test_text_mode_and_offset_are_explicit(self):
        data = bytes.fromhex('ff 0f4243 41819f')
        reader = BinaryReader(data, offset=1, unicode_text=False)
        self.assertEqual(reader.text(), 'A\x81\u0178')
        self.assertEqual(reader.pos, len(data))
        self.assertEqual(BinaryReader(bytes.fromhex('0002 d800 0041')).text(), '\ud800A')

    def test_one_byte_ansi_lengths_preserve_the_following_field(self):
        reader = BinaryReader(b'\x03A\x81\x9f\x01', unicode_text=False, ansi_length_bytes=1)
        self.assertEqual('A\x81\u0178', reader.text())
        self.assertEqual(4, reader.pos)
        self.assertTrue(reader.boolean())
        # Selecting the older length prefix must not change UTF-16 decoding.
        reader = BinaryReader(bytes.fromhex('0002 d800 0041'), ansi_length_bytes=1)
        self.assertEqual('\ud800A', reader.text())

    def test_ansi_length_configuration_is_explicit(self):
        for value in (0, 2, 4, True, '1'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                BinaryReader(b'', ansi_length_bytes=value)

    def test_bad_fields_raise_family_error_without_consuming_following_data(self):
        class BadInput(ValueError):
            pass

        class Reader(BinaryReader):
            error_type = BadInput

        reader = Reader(b'\x01\x02')
        with self.assertRaisesRegex(BadInput, 'truncated field'):
            reader.integer()
        self.assertEqual(reader.pos, 0)
        self.assertTrue(reader.boolean())
        with self.assertRaisesRegex(BadInput, 'invalid boolean'):
            reader.boolean()

    def test_lengths_cannot_escape_input(self):
        for data, method in ((b'\x00\x03\x00A', 'text'), (bytes.fromhex('0f423f'), 'count')):
            with self.subTest(method=method):
                with self.assertRaises(ValueError):
                    reader = BinaryReader(data)
                    reader.count('points') if method == 'count' else reader.text()
        for offset in (-1, 2, True):
            with self.subTest(offset=offset):
                with self.assertRaises(ValueError):
                    BinaryReader(b'\x00', offset=offset)

    def test_writer_rejects_values_outside_wire_domain(self):
        for method, value in (('number', float('inf')), ('number', True),
                              ('number', 100001), ('number', Decimal('100000.00000000000000001')),
                              ('integer', 1.5),
                              ('integer', 1000001), ('color', -1),
                              ('boolean', 1), ('text', 'a'*65536)):
            with self.subTest(method=method, value_type=type(value).__name__):
                writer = BinaryWriter()
                with self.assertRaises((ValueError, TypeError)):
                    getattr(writer, method)(value)
                self.assertEqual(writer.buffer, b'')

    def test_record_writer_errors_identify_the_field_without_partial_scalar_output(self):
        root = Element('')
        group = root.add('Group')
        group.add('Width', 1, 2)
        group.add('Size', 100001)
        group.add('Flag', 1)
        for name, codec, location, message in (
                ('Missing', 'number', '/Group[1]/Missing', 'scalar binary value is missing'),
                ('Width', 'number', '/Group[1]/Width[1]', 'expected one scalar binary value'),
                ('Size', 'number', '/Group[1]/Size[1]', ''),
                ('Flag', 'boolean', '/Group[1]/Flag[1]', '')):
            with self.subTest(field=name):
                writer = RecordWriter()
                with self.assertRaisesRegex((TypeError, ValueError), re.escape(location)+': '+message):
                    writer.field(group, name, codec)
                self.assertEqual(writer.buffer, b'')

    def test_named_extended_colors_use_rgb_bytes_and_report_projection(self):
        writer = RecordWriter()
        writer.report = ConversionReport()
        shape = Element('Shape')
        shape.add('Color', -1)
        shape.add('FontColor', 0x12345678)
        writer.fields(shape, 'color', 'Color FontColor')
        self.assertEqual(writer.buffer, bytes.fromhex('000000 785634'))
        self.assertEqual((shape['Color'], shape['FontColor']), (-1, 0x12345678))
        self.assertEqual([row.rule for row in writer.report.warnings], ['color-rgb-range']*2)

    def test_scaled_grid_keeps_small_steps_and_is_independent_of_decimal_context(self):
        for step in (Decimal('.3'), Decimal('.000012345'), Decimal('.0000005')):
            writer = BinaryWriter()
            write_grid_step(writer, step)
            reader = BinaryReader(bytes(writer.buffer))
            numerator, divisor = reader.number(), reader.integer()
            with localcontext() as context:
                context.prec = 2
                result = grid_step_value(numerator, divisor)
            self.assertEqual(result, float(step))
            self.assertEqual(reader.pos, len(reader.data))
        self.assertEqual(grid_step_value(Decimal('1.2345'), 0), 1.2345)


if __name__ == '__main__':
    unittest.main()
