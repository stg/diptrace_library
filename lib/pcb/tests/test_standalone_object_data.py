"""Standalone-object load rules do not retain component-only historical data."""
import unittest
from decimal import Decimal
from xml.etree import ElementTree as ET

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport, import_diagnostics, _set_import_format
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import FORMATS
from lib.pcb.formats.dip.decode import decode
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.dipxml.read import prepare
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.tests.test_dipxml_library import source
from lib.pcb.tests.test_xml_via_masks import via_document, COMPONENT


def design(kind):
    document = via_document()
    component = document.one(COMPONENT)
    pattern = component.one('Pattern')
    if kind == 15:
        component['Via'] = None
        pattern['Type'] = 15
        document.remove(pattern.one('Pads/Pad'))
        pattern.one('Holes').add('Hole', True, False, 3, 6, 2, 1, -1)
    return document


def customize(component):
    pattern = component.one('Pattern')
    pattern['OriginX'], pattern['OriginY'] = 7, -9
    model = pattern.one('Model3D')
    for name, value in dict(Model3DFile='fixture.step', Model3DFile_Variable='${MODELS}/fixture.step',
            Mirror=True, NoSearch=True, KeepPins=True, Type=2, Units=2,
            IPC_XOff=4, IPC_YOff=5, AutoHeight=6, AutoColor=0x123456).items():
        model[name] = value
    for name, value in (('Offset', 3), ('Rotate', 4), ('Zoom', 5)):
        for axis in ('X', 'Y', 'Z'):
            model.one(name)[axis] = value


@import_diagnostics()
def stale_input(data, format, *, report=None):
    """Inject discarded source selections before the shared identity binder."""
    _set_import_format(format)
    prepared = {'dip': decode, 'asc': prepare_core, 'dipxml': prepare}[format](data)
    component = prepared.board.one('Components/Component')
    component.set_field('HiddenId', 37)
    for name, values in (('HierarchyPath', (111, 37)), ('AssemblyExclude', (999,))):
        collection = component.child(name) or component.add(name)
        for row in tuple(collection.children()):
            row.detach()
        for value in values:
            collection.add('Item', value)
    collection = component.child('InternalConnection_Records') or component.add('InternalConnection_Records')
    collection.add('pt', 999, 999)
    return assemble_graphics(prepared).document


class StandaloneObjectDataTests(unittest.TestCase):
    def test_load_resets_special_origins_and_only_vias_reset_the_model_attachment(self):
        for kind in (15, 16):
            for format in FORMATS:
                with self.subTest(kind=kind, format=format):
                    document = design(kind)
                    component = document.one(COMPONENT)
                    customize(component)
                    before = model_text(document, preserve=False), tuple(document.references)
                    exported = ConversionReport()
                    data = io.serialize(document, format=format, report=exported)
                    report = ConversionReport()
                    current = io.parse(data, report=report)
                    pattern = current.one(COMPONENT+'/Pattern')
                    self.assertEqual(pattern['Type'], kind)
                    self.assertEqual((pattern['OriginX'], pattern['OriginY']), (0, 0))
                    model = pattern.one('Model3D')
                    if kind == 16:
                        self.assertEqual((model['Model3DFile'], model['Model3DFile_Variable']), ('', ''))
                        self.assertEqual((model['Mirror'], model['NoSearch'], model['KeepPins']), (False, False, False))
                        self.assertEqual((model['Type'], model['IPC_XOff'], model['IPC_YOff'], model['AutoHeight']), (0, 0, 0, 0))
                        self.assertEqual(model['AutoColor'], 0x4B4B4B)
                        for name, value in (('Offset', 0), ('Rotate', 0), ('Zoom', 1)):
                            self.assertEqual(tuple(model.one(name)[axis] for axis in ('X', 'Y', 'Z')), (value,)*3)
                    else:
                        self.assertEqual(model['Model3DFile'], 'fixture.step')
                        self.assertEqual(model.one('Offset')['X'], 3)
                    self.assertIn('standalone-object-data', {notice.rule for notice in report.infos})
                    self.assertIn('standalone-object-data', {notice.rule for notice in exported.warnings})
                    self.assertEqual((model_text(document, preserve=False), tuple(document.references)), before)
                    current.validate()

    def test_discarded_source_selections_do_not_create_dangling_model_relationships(self):
        for kind in (15, 16):
            for format in FORMATS:
                with self.subTest(kind=kind, format=format):
                    document = design(kind)
                    data = io.serialize(document, format=format, report=ConversionReport())
                    report = ConversionReport()
                    current = stale_input(data, format, report=report)
                    component = current.one(COMPONENT)
                    for name in ('HierarchyPath', 'AssemblyExclude', 'IntConRecords'):
                        self.assertEqual(component.one(name).children(), [])
                    self.assertFalse(current.references.issues)
                    self.assertIn('standalone-object-data', {notice.rule for notice in report.infos})
                    current.validate()

    def test_xml_constructor_cleanup_precedes_later_type_classification(self):
        root = ET.fromstring(source())
        root.find('Board/Components/Component').set('Type', 'Via')
        pattern = root.find('Library/Library/Patterns/Pattern')
        ET.SubElement(pattern, 'Origin', X='3', Y='4')
        model = pattern.find('Model3D')
        filename = ET.SubElement(model, 'Filename')
        ET.SubElement(filename, 'Path').text = 'fixture.step'
        report = ConversionReport()
        document = io.parse(ET.tostring(root, encoding='unicode'), report=report)
        current = document.one(COMPONENT+'/Pattern')
        self.assertEqual(current['Type'], 0)  # Several physical objects remain.
        # Constructor origin is cleared; the final ordinary footprint recenters.
        self.assertEqual((current['OriginX'], current['OriginY']), (Decimal('2.4'), 0))
        self.assertEqual(current.one('Model3D')['Model3DFile'], '')
        cached = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
        self.assertEqual((cached['OriginX'], cached['OriginY']), (9, -12))
        self.assertEqual(cached.one('Model3D')['Model3DFile'], 'fixture.step')
        document.validate()

    def test_ordinary_components_keep_independent_origins_and_model_data(self):
        document = io.parse(source(), report=ConversionReport())
        component = document.one(COMPONENT)
        customize(component)
        for format in FORMATS:
            with self.subTest(format=format):
                report = ConversionReport()
                rebuilt = io.parse(io.serialize(document, format=format, report=report), report=ConversionReport())
                pattern = rebuilt.one(COMPONENT+'/Pattern')
                self.assertEqual((pattern['OriginX'], pattern['OriginY']), (7, -9))
                self.assertEqual(pattern.one('Model3D')['Model3DFile'], 'fixture.step')
                self.assertEqual(pattern.one('Model3D/Offset')['X'], 3)
                self.assertNotIn('standalone-object-data', {notice.rule for notice in report.notices})
                rebuilt.validate()

    def test_clean_special_data_remains_clean_in_every_output_profile(self):
        for kind in (15, 16):
            document = design(kind)
            for format, support in FORMATS.items():
                for version in support.write_versions:
                    with self.subTest(kind=kind, format=format, version=version):
                        report = ConversionReport()
                        current = io.parse(io.serialize(document, format=format, version=version, report=report),
                                           report=ConversionReport())
                        self.assertEqual(current.one(COMPONENT+'/Pattern')['Type'], kind)
                        self.assertNotIn('standalone-object-data', {notice.rule for notice in report.warnings})
                        current.validate()


if __name__ == '__main__':
    unittest.main()
