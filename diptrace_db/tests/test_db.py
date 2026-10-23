"""The component database uses strict model parsing and versioned extraction caches."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from lib.design import new_schematic,parse_dch
from lib.design.schematic_objects import new_symbol
from lib.design.schematic_refs import bind_schematic_references
from diptrace_db.build_db import build_db,_load_previous_index,_extract_file_rows,EXTRACTION_FORMAT


class DatabaseTests(unittest.TestCase):
    def test_component_kind_and_enabled_state_control_inclusion(self):
        document=new_schematic()
        part=document.one('/Schematic/Components').append(new_symbol('RES','NetPort1'))
        part.set_field('Value','10k')
        part.one('Pattern').set_values('RES_0603')
        bind_schematic_references(document)
        document=parse_dch(document.to_dch_bytes())
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'input.dch'
            path.write_bytes(document.to_dch_bytes())
            self.assertEqual(_extract_file_rows(path),[('','10k','RES_0603')])
            document.one('/Schematic/Components/Part').set_field('Enabled',False)
            path.write_bytes(document.to_dch_bytes())
            self.assertFalse(parse_dch(path.read_bytes()).one('/Schematic/Components/Part').scalar('Enabled'))
            self.assertEqual(_extract_file_rows(path),[])

    def test_scan_rejects_bad_input_and_reuses_only_current_cache_format(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root=Path(folder)
            (root/'good.dch').write_bytes(new_schematic().to_dch_bytes())
            (root/'bad.dch').write_bytes(b'invalid design')
            with redirect_stdout(io.StringIO()):
                result=build_db(root,workers=1)
            self.assertEqual(result['files_failed'],1)
            self.assertEqual(len(result['file_stats']),1)
            output=root/'database.json'
            output.write_text(json.dumps(result))
            current=_load_previous_index(output)
            self.assertEqual(set(current),{str(root/'good.dch'),str(root/'bad.dch')})
            self.assertIsNone(current[str(root/'bad.dch')]['stats'])
            with redirect_stdout(io.StringIO()):
                resumed=build_db(root,workers=1,prev_index=current)
            self.assertEqual(resumed['files_read'],1)  # Only the failed input is retried.
            self.assertEqual(resumed['files_failed'],1)
            self.assertEqual(resumed['extraction_format'],EXTRACTION_FORMAT)
            del result['extraction_format']
            output.write_text(json.dumps(result))
            self.assertEqual(_load_previous_index(output),{})


if __name__=='__main__':
    unittest.main()
