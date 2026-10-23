"""Common loading rules depend on route state, rather than input origin."""
import unittest
import xml.etree.ElementTree as ET

from lib.design import AscExportContext, ExportReport, Index, new_schematic, parse
from lib.design.route_normalization import normalize_imported_routes


PATH = '/Schematic/Nets/Net/Lines/Line'


def source(*, enabled=True, end=(3, 1)):
    root = ET.fromstring(new_schematic().to_dchxml_bytes())
    root.find('Schematic').append(ET.fromstring(f'''
      <Nets><Net Id="0" NetClass="0" Enabled="{'Y' if enabled else 'N'}"><Name>Signal</Name>
      <Wires><Wire Id="0" Sheet="0" Connected1="Free" Connected2="Free">
      <Points><Point X="0" Y="0" Dir="-1"/><Point X="{end[0]}" Y="{end[1]}" Dir="1"/></Points>
      </Wire></Wires></Net></Nets>'''))
    current = parse(ET.tostring(root), format='dchxml')
    # Author an obsolete hint after initial loading, so each adapter must
    # modernize an actual input rather than a fixture already normalized here.
    current.one(PATH+'/Points/pt[2]').set_argument(2, 1)
    return current


def encode(current, destination, *, version=None):
    arguments = dict(report=ExportReport())
    if destination == 'asc':
        arguments['context'] = AscExportContext(compact_inactive=False)
    if version is not None:
        arguments['version'] = version
    return getattr(current, 'to_'+destination+'_bytes')(**arguments)


class RouteImportTests(unittest.TestCase):
    def test_all_inputs_normalize_the_same_two_point_route_and_keep_geometry(self):
        original = source()
        points = [point.values for point in original.select(PATH+'/Points/pt')]
        for destination in ('dch', 'asc', 'dchxml'):
            with self.subTest(destination=destination):
                current = parse(encode(original, destination), format=destination)
                for _ in range(3):
                    actual = [point.values for point in current.select(PATH+'/Points/pt')]
                    self.assertEqual([row[:2] for row in actual], [row[:2] for row in points])
                    self.assertEqual([row[2] for row in actual], [-1, 0])
                    self.assertEqual(normalize_imported_routes(current), 0)
                    current = parse(encode(current, destination), format=destination)
        self.assertEqual([point.values for point in original.select(PATH+'/Points/pt')], points)

    def test_supported_binary_output_versions_have_the_same_loading_rule(self):
        original = source(end=(0, 0))
        for version in (46, 47, 48):
            with self.subTest(version=version):
                current = parse(encode(original, 'dch', version=version), format='dch')
                self.assertEqual(current.one(PATH+'/Points/pt[2]').values, (0, 0, 0))
                self.assertEqual(normalize_imported_routes(current), 0)

    def test_disabled_nets_keep_their_two_point_hints_in_every_input(self):
        original = source(enabled=False)
        expected = [point.values for point in original.select(PATH+'/Points/pt')]
        for destination in ('dch', 'asc', 'dchxml'):
            with self.subTest(destination=destination):
                current = parse(encode(original, destination), format=destination)
                self.assertEqual([point.values for point in current.select(PATH+'/Points/pt')], expected)

    def test_related_unresolved_identity_defers_normalization_without_a_backup(self):
        current = source()
        points = current.one(PATH+'/Points')
        expected = [point.values for point in points.children('pt')]
        unknown = current.root.add('UnknownAttachment', 99)
        current.references.note(unknown, 'unknown route anchor', Index(unknown), collections=(points,))
        self.assertEqual(normalize_imported_routes(current), 0)
        self.assertEqual([point.values for point in points.children('pt')], expected)
        self.assertTrue(any('Route normalization deferred' in message for message in current.diagnostics))
        self.assertIsNone(current.one(PATH).child('StoredData'))


if __name__ == '__main__':
    unittest.main()
