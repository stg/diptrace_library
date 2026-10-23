from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.structural.decoder import decode_structural_components, encode_structural_tree


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Read a .dch through structural tree and write it back.")
    ap.add_argument("input_dch", help="Input .dch path")
    ap.add_argument("output_dch", help="Output .dch path")
    ap.add_argument("--verify", action="store_true", help="Verify output bytes are identical to input.")
    args = ap.parse_args()

    inp = Path(args.input_dch)
    out = Path(args.output_dch)
    if not inp.exists():
        raise SystemExit(f"input not found: {inp}")

    tree = decode_structural_components(inp)
    data_out = encode_structural_tree(tree)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data_out)

    msg = f"wrote={out} bytes={len(data_out)} clean_eof={int(bool(tree.get('clean_eof', False)))}"
    if args.verify:
        data_in = inp.read_bytes()
        ok = data_in == data_out
        msg += (
            f" identical={int(ok)}"
            f" sha_in={_sha256(data_in)}"
            f" sha_out={_sha256(data_out)}"
        )
    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

