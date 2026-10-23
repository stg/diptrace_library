from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.structural.decoder import decode_structural_components
from apps.deprecated.pre_shared_model.lib.tree_query import TreeQuery
import math


def _q(s: str) -> str:
    # DipTrace ASC keeps Windows paths with single backslashes.
    return '"' + str(s).replace('"', '\\"') + '"'


def _fmt_num(v: float, digits: int = 6) -> str:
    s = f"{float(v):.{int(digits)}f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _angle_to_asc_degrees(raw_angle: Any) -> float:
    if not isinstance(raw_angle, (int, float)):
        return 0.0
    v = float(raw_angle)
    # Observed across sample corpus:
    # - some records store angle directly in degrees
    # - some records store angle in radians
    # This branch is data-domain based and deterministic per record.
    if abs(v) <= 6.4:
        return v * 180.0 / math.pi
    return v


def _fmt_value(v: Any) -> str:
    if isinstance(v, dict):
        vv = v.get("value")
        if isinstance(vv, bool):
            return "1" if vv else "0"
        if isinstance(vv, int):
            return str(vv)
        if isinstance(vv, float):
            return _fmt_num(vv)
        raw = v.get("raw")
        if isinstance(raw, (bytes, bytearray)):
            return _q(bytes(raw).hex(" "))
        return _q(str(v))
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return _fmt_num(v)
    if isinstance(v, (bytes, bytearray)):
        return _q(bytes(v).hex(" "))
    return _q(str(v))


def _prop_scalar(props: dict[str, Any], key: str, default: Any = None) -> Any:
    if key not in props:
        return default
    v = props.get(key)
    if isinstance(v, dict) and "value" in v:
        return v.get("value", default)
    return v


def _show_angle_from_part_radians(raw_angle: Any) -> float:
    if not isinstance(raw_angle, (int, float)):
        return 0.0
    v = float(raw_angle)
    if not math.isfinite(v):
        return 0.0
    # Observed ASC behavior for Part-derived show angles:
    # fold to principal orientation in [0, pi].
    twopi = 2.0 * math.pi
    a = v % twopi
    if a > math.pi:
        a = twopi - a
    if abs(a - twopi) < 1e-4 or abs(a) < 1e-4:
        return 0.0
    return a


def _wrap_angle_radians(raw_angle: Any) -> float:
    if not isinstance(raw_angle, (int, float)):
        return 0.0
    v = float(raw_angle)
    if not math.isfinite(v):
        return 0.0
    twopi = 2.0 * math.pi
    a = v % twopi
    if abs(a - twopi) < 1e-4 or abs(a) < 1e-4:
        return 0.0
    return a


def _normalize_show_tuple_angle(vals: list[Any], part_angle: Any = None) -> list[Any]:
    if not isinstance(vals, list) or not vals:
        return vals
    out = list(vals)
    part_wrapped = _wrap_angle_radians(part_angle) if isinstance(part_angle, (int, float)) else None
    part_show = _show_angle_from_part_radians(part_angle) if isinstance(part_angle, (int, float)) else None

    def _fix_angle(v: Any) -> Any:
        if not isinstance(v, (int, float)):
            return v
        a = _wrap_angle_radians(v)
        if part_wrapped is not None and part_show is not None:
            if abs(a - part_wrapped) < 1e-3:
                return part_show
        return a

    if len(out) >= 8 and isinstance(out[7], (int, float)):
        out[7] = _fix_angle(out[7])
    elif len(out) >= 7 and isinstance(out[6], (int, float)):
        out[6] = _fix_angle(out[6])
    return out


def _emit_part_block(part_node: dict[str, Any], indent: int) -> list[str]:
    props = part_node.get("props", {}) if isinstance(part_node.get("props"), dict) else {}
    name = str(props.get("Name", ""))
    refdes = str(props.get("RefDes", ""))

    pad = " " * indent
    lines: list[str] = [f"{pad}(Part {_q(name)} {_q(refdes)}"]

    type_v = int(_prop_scalar(props, "Type", 0) or 0)
    page_v = int(_prop_scalar(props, "Page", 0) or 0)
    ori_v = int(_prop_scalar(props, "Orientation", 0) or 0)
    show_name_v = 0
    show_value_v = 1 if str(_prop_scalar(props, "Value", "")).strip() != "" else 0
    show_refdes_v = int(_prop_scalar(props, "unknown19", 0) or 0)
    angle_raw = _prop_scalar(props, "Angle", None)
    angle_v = _angle_to_asc_degrees(angle_raw)

    ordered_fields: list[tuple[str, Any]] = [
        ("Enabled", "Y"),
        ("Selected", str(_prop_scalar(props, "Selected", "N"))),
        ("Value", _prop_scalar(props, "Value", "")),
        ("BaseName", _prop_scalar(props, "BaseName", name)),
        ("BaseRefDes", _prop_scalar(props, "BaseRefDes", "")),
        ("X", _prop_scalar(props, "X", 0)),
        ("Y", _prop_scalar(props, "Y", 0)),
        ("Type", type_v),
        ("Number1", 0),
        ("Number2", 0),
        ("Page", page_v),
        ("Orientation", ori_v),
        ("Group", _prop_scalar(props, "Group", -1)),
        ("Number", _prop_scalar(props, "Number", 0)),
        ("Width", _prop_scalar(props, "Width", 0)),
        ("Height", _prop_scalar(props, "Height", 0)),
        ("ShowText", 0),
        ("TextAlign", 0),
        ("PartNumber", 0),
        ("PartType", _prop_scalar(props, "PartType", 0)),
        ("PartName", _prop_scalar(props, "PartName", "Part 1")),
        ("PartDescriptor", _prop_scalar(props, "PartDescriptor", "1")),
        ("AllowParts", "N"),
        ("ShowText2", 0),
        ("TextAlign2", 0),
        ("ShowNumbers", 2),
        ("TextPosX", 0),
        ("TextPosY", 0),
        ("TextPosX2", 0),
        ("TextPosY2", 0),
        ("PartString", ""),
        ("HiddenId", _prop_scalar(props, "HiddenId", 0)),
    ]
    used = {
        "Name",
        "RefDes",
        "Value",
        "BaseName",
        "BaseRefDes",
        "X",
        "Y",
        "Type",
        "Page",
        "Orientation",
        "Group",
        "Number",
        "Width",
        "Height",
        "PartType",
        "unknown2",
        "PartName",
        "PartDescriptor",
        "ShowRefDes",
        "ShowNameFlag",
        "ShowNumbers",
        "TextPosX",
        "TextPosY",
        "TextPosX2",
        "TextPosY2",
        "HiddenId",
        "FieldIndex1",
        "FieldIndex2",
        "Angle",
        "LibPath",
        "LibPath_Variable",
    }
    for key, val in ordered_fields:
        lines.append(f"{pad}  ({key} {_fmt_value(val)})")

    lines.append(f"{pad}  (UserFields")
    lines.append(f"{pad}  )")
    lines.append(f"{pad}  (FieldIndex1 {_fmt_value(_prop_scalar(props, 'FieldIndex1', -1))})")
    lines.append(f"{pad}  (FieldIndex2 {_fmt_value(_prop_scalar(props, 'FieldIndex2', -1))})")
    lines.append(f"{pad}  (Locked {_q(str(_prop_scalar(props, 'Locked', 'N')))})")
    lines.append(f"{pad}  (Angle {_fmt_num(angle_v, 4)})")
    lp = str(_prop_scalar(props, "LibPath", "") or "")
    lpv = str(_prop_scalar(props, "LibPath_Variable", lp) or "")
    if lp != "":
        lines.append(f"{pad}  (LibPath {_q(lp)})")
        lines.append(f"{pad}  (LibPath_Variable {_q(lpv)})")
    lines.append(f"{pad}  (ModelType 0)")
    lines.append(f"{pad}  (ModelString \"\")")
    lines.append(f"{pad}  (LockProperties \"N\")")
    lines.append(f"{pad}  (Origin_X 0)")
    lines.append(f"{pad}  (Origin_Y 0)")
    lines.append(f"{pad}  (ModelBody")
    lines.append(f"{pad}  )")
    lines.append(f"{pad}  (Datasheet \"\")")
    lines.append(f"{pad}  (HorzFlip \"N\")")
    lines.append(f"{pad}  (VertFlip \"N\")")
    lines.append(f"{pad}  (ShowOrigin \"N\")")
    lines.append(f"{pad}  (PageHiddenId 0)")
    lines.append(f"{pad}  (Manufacturer \"\")")
    lines.append(f"{pad}  (Component_CategoryName \"\")")
    lines.append(f"{pad}  (Component_CategoryIndex -1)")
    lines.append(f"{pad}  (Component_CategoryTypes 0")
    lines.append(f"{pad}  )")
    lines.append(f"{pad}  (CustomMarkingFont \"N\")")
    lines.append(f"{pad}  (MarkingFontSize 6)")
    lines.append(f"{pad}  (MarkingFontAll \"N\")")
    def _show_values_from_children(type_name: str, expected_text: str) -> list[Any] | None:
        children = part_node.get("children", []) if isinstance(part_node.get("children"), list) else []
        part_angle = _prop_scalar(props, "Angle", 0.0)
        exp = str(expected_text)
        for ch in children:
            if not isinstance(ch, dict):
                continue
            if str(ch.get("type", "")) != type_name:
                continue
            cprops = ch.get("props", {}) if isinstance(ch.get("props"), dict) else {}
            text_val = str(_prop_scalar(cprops, "Text", "") or "")
            if text_val != exp:
                continue
            vals = cprops.get("Values")
            if isinstance(vals, list):
                return _normalize_show_tuple_angle(vals, part_angle=part_angle)
            tok_a = int(_prop_scalar(cprops, "TokenA", 0) or 0) * 4
            metric0 = int(round(float(_prop_scalar(cprops, "Metric0", 0.0) or 0.0)))
            x = float(_prop_scalar(cprops, "X", 0.0) or 0.0)
            y = float(_prop_scalar(cprops, "Y", 0.0) or 0.0)
            show_angle = _show_angle_from_part_radians(_prop_scalar(props, "Angle", 0.0))
            if type_name == "ShowValue":
                return [show_value_v, tok_a, 0, -1, x, y, show_angle]
            visible = show_refdes_v if type_name == "ShowRefDes" else show_name_v
            return [visible, 0, tok_a, 0, metric0, x, y, show_angle]
        return None

    def _show_tuple_text(vals: list[Any]) -> str:
        return " ".join(_fmt_num(v, 4) if isinstance(v, float) else str(v) for v in vals)

    ref_vals = _show_values_from_children("ShowRefDes", refdes)
    name_vals = _show_values_from_children("ShowName", name)
    value_vals = _show_values_from_children("ShowValue", str(_prop_scalar(props, "Value", "")))
    if ref_vals is None:
        ref_vals = [show_refdes_v, 0, 0, 0, 0, 0, 0, 0]
    if name_vals is None:
        name_vals = [show_name_v, 0, 0, 0, 0, 0, 0, 0]
    if value_vals is None:
        value_vals = [show_value_v, 0, 0, 0, 0, 0, 0]
    part_angle = _prop_scalar(props, "Angle", 0.0)
    ref_vals = _normalize_show_tuple_angle(ref_vals, part_angle=part_angle)
    name_vals = _normalize_show_tuple_angle(name_vals, part_angle=part_angle)
    value_vals = _normalize_show_tuple_angle(value_vals, part_angle=part_angle)
    lines.append(f"{pad}  (ShowRefDes {_show_tuple_text(ref_vals)})")
    lines.append(f"{pad}  (ShowName {_show_tuple_text(name_vals)})")
    lines.append(f"{pad}  (ShowValue {_show_tuple_text(value_vals)})")
    lines.append(f"{pad}  (ShowManufacturer 0 0 0 0 0 0 0)")
    lines.append(f"{pad}  (ShowDatasheet 0 0 0 0 0 0 0)")
    lines.append(f"{pad}  (Suppliers")
    lines.append(f"{pad}    (PartNumber \"\")")
    lines.append(f"{pad}    (Manufacturer \"\")")
    lines.append(f"{pad}    (Pattern \"\")")
    lines.append(f"{pad}    (Supplier \"\")")
    lines.append(f"{pad}    (Currency \"\")")
    lines.append(f"{pad}    (MainSupplier \"N\")")
    lines.append(f"{pad}  )")
    lines.append(f"{pad}  (Pins")
    lines.append(f"{pad}  )")
    lines.append(f"{pad}  (Shapes")
    lines.append(f"{pad}  )")

    # Emit remaining decoded props to preserve structural information.
    for k, v in props.items():
        key = str(k)
        if key in used:
            continue
        if key.startswith("unknown"):
            continue
        lines.append(f"{pad}  ({key} {_fmt_value(v)})")

    children = part_node.get("children", []) if isinstance(part_node.get("children"), list) else []
    for ch in children:
        if not isinstance(ch, dict):
            continue
        ctype = str(ch.get("type", "Record"))
        if ctype != "Pattern":
            continue
        cprops = ch.get("props", {}) if isinstance(ch.get("props"), dict) else {}
        pattern_name = str(cprops.get("Name", ""))
        lines.append(f"{pad}  (Pattern {_q(pattern_name)}")
        lines.append(f"{pad}    (Enabled \"Y\")")
        lines.append(f"{pad}    (Name {_q(pattern_name)})")
        lines.append(f"{pad}    (Name_Description \"\")")
        lines.append(f"{pad}    (Name_Unique \"\")")
        lines.append(f"{pad}    (RecoveryCode \"\")")
        lines.append(f"{pad}    (Pattern_Manufacturer \"\")")
        lines.append(f"{pad}    (Pads")
        lines.append(f"{pad}    )")
        lines.append(f"{pad}    (Shapes")
        lines.append(f"{pad}    )")
        lines.append(f"{pad}    (Holes")
        lines.append(f"{pad}    )")
        lines.append(f"{pad}    (Model3D")
        lines.append(f"{pad}    )")
        lines.append(f"{pad}    (Pattern_CategoryName \"\")")
        lines.append(f"{pad}    (Pattern_CategoryIndex -1)")
        lines.append(f"{pad}    (Pattern_CategoryTypes 0")
        lines.append(f"{pad}    )")
        lines.append(f"{pad}  )")

    lines.append(f"{pad})")
    return lines


def dch_to_minimal_asc(input_dch: Path) -> tuple[str, bool, int]:
    tree = decode_structural_components(input_dch)
    tq = TreeQuery(tree)
    components = tq.find("Components")
    parts = components.find_all("Part", sort_by_offset=True) if components is not None else []

    lines: list[str] = []
    lines.append("(Schematic")
    lines.append("  (Components")
    for p in parts:
        lines.extend(_emit_part_block(p.node, indent=4))
    lines.append("  )")
    lines.append(")")

    return "\n".join(lines) + "\n", bool(tree.get("clean_eof", False)), len(parts)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate a minimal ASC-like view from .dch tree: Schematic -> Components -> Part list."
    )
    ap.add_argument("input_dch", help="Input DipTrace schematic binary (.dch)")
    ap.add_argument("output_asc", help="Output ASC text path")
    args = ap.parse_args()

    inp = Path(args.input_dch)
    out = Path(args.output_asc)
    if not inp.exists():
        raise SystemExit(f"input not found: {inp}")

    txt, clean_eof, part_count = dch_to_minimal_asc(inp)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(txt, encoding="utf-8", newline="\n")
    print(f"wrote={out} parts={part_count} clean_eof={int(clean_eof)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
