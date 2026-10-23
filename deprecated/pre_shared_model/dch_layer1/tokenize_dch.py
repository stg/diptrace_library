from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.opcode.layer1 import read_bytes, tokenize_opcode_layer as tokenize_layer1


def main() -> None:
    ap = argparse.ArgumentParser(description="Tokenize a .dch into first-layer opcode/literal tokens.")
    ap.add_argument("--in", dest="input_path", required=True, help="Input .dch file")
    ap.add_argument("--out", required=True, help="Output JSON file")
    args = ap.parse_args()

    inp = Path(args.input_path)
    data = read_bytes(inp)
    toks = tokenize_layer1(data)
    payload = {
        "file": str(inp),
        "size": len(data),
        "token_count": len(toks),
        "tokens": [t.as_dict() for t in toks],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote={out} tokens={len(toks)}")


if __name__ == "__main__":
    main()
