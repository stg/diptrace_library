"""BOM extraction uses the same component facts across supported inputs."""
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from lib import new_schematic
from lib.schematic.model.objects import (new_symbol)
from lib.schematic.model.refs import (bind_schematic_references)
from apps.diptrace_bom.build_bom import build_bom


def design():
    document=new_schematic()
    parts=document.one('/Schematic/Components')
    for ref,value,kind in (('R10','10k',0),('R2','10k',0),('R2','unused duplicate',0),('NET','',2)):
        part=parts.append(new_symbol('Resistor',ref))
        part.set_field('Value',value)
        part.set_field('PartType',kind)
        part.one('Pattern').set_values('R_0603')
    bind_schematic_references(document)
    return document


class BomTests(unittest.TestCase):
    def test_all_formats_group_physical_parts_in_natural_reference_order(self):
        document=design()
        expected=[dict(RefDes='R2, R10',Name='Resistor',Value='10k',Pattern='R_0603')]
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            for suffix,emit in (('.dch',document.to_dch_bytes),('.asc',document.to_asc_bytes),
                                ('.dchxml',document.to_dchxml_bytes)):
                path=Path(folder)/('input'+suffix)
                data=emit()
                path.write_bytes(data)
                rows,complete=build_bom(path)
                self.assertEqual(rows,expected,suffix)
                self.assertTrue(complete)
                self.assertEqual(path.read_bytes(),data)

    def test_invalid_input_leaves_an_existing_csv_untouched(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source,target=Path(folder)/'input.dch',Path(folder)/'output.csv'
            source.write_bytes(b'invalid design')
            target.write_text('existing output')
            result=subprocess.run([sys.executable,str(ROOT/'apps/diptrace_bom/build_bom.py'),str(source),str(target)],
                                  capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(target.read_text(),'existing output')


if __name__=='__main__':
    unittest.main()
