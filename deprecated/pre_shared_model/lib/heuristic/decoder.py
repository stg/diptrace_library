from __future__ import annotations

# Intended use:
# Shared DipTrace binary decode primitives for application/runtime usage.
# State:

# By no means complete, fully validated, or cleaned up; intended to be iteratively improved as new patterns and heuristics are discovered.

import argparse
import json
from pathlib import Path
import re
import string
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

PRINTABLE = set(bytes(string.printable, "ascii")) - {0x0B, 0x0C}


@dataclass
class StringHit:
    encoding: str
    offset: int
    text: str


def read_bytes(path: str | Path) -> bytes:
    return Path(path).read_bytes()


def extract_ascii_strings(data: bytes, min_len: int = 4) -> list[StringHit]:
    hits: list[StringHit] = []
    i = 0
    n = len(data)
    while i < n:
        if data[i] in PRINTABLE and data[i] >= 32:
            start = i
            i += 1
            while i < n and data[i] in PRINTABLE and data[i] >= 32:
                i += 1
            if i - start >= min_len:
                hits.append(StringHit("ascii", start, data[start:i].decode("ascii", errors="ignore")))
        else:
            i += 1
    return hits


def extract_utf16le_strings(data: bytes, min_len: int = 4) -> list[StringHit]:
    hits: list[StringHit] = []
    i = 0
    n = len(data)
    while i + 1 < n:
        if 32 <= data[i] <= 126 and data[i + 1] == 0:
            start = i
            chars: list[int] = []
            while i + 1 < n and 32 <= data[i] <= 126 and data[i + 1] == 0:
                chars.append(data[i])
                i += 2
            if len(chars) >= min_len:
                hits.append(StringHit("utf16le", start, bytes(chars).decode("ascii", errors="ignore")))
        else:
            i += 1
    return hits


def extract_strings(data: bytes, min_len: int = 4) -> list[StringHit]:
    return extract_ascii_strings(data, min_len=min_len) + extract_utf16le_strings(data, min_len=min_len)


NET_NAME_RE = re.compile(r"^Net\s+\S.*$")
PART_REF_RE = re.compile(r"^(?:NetPort[0-9]{1,5}|[A-Z]{1,4}[0-9]{1,5}[A-Za-z]{0,3})$")
PART_NAME_RE = re.compile(r"^[A-Za-z0-9_./+-]{2,40}$")
VALUE_RE = re.compile(r"^(?:\d+(?:\.\d+)?[kKmMuUnNpPfF]?|[A-Za-z0-9_./+-]{1,32})$")
SHEET_RE = re.compile(r"^Sheet\s+\d+$")
BASE_REF_RE = re.compile(r"^[A-Z]{1,5}$")
NET_PORT_RE = re.compile(r"^NetPort[0-9]{1,5}$")

TRIVIAL_TEXT = {
    "",
    ";",
    "Part 1",
    "1",
    "2",
    "3",
    "4",
    "5",
    "Consolas",
    "Arial",
    "Default",
}

COORD_BIAS_BE24 = 0x9ACA00
NUM_TOKEN_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
PART_NAME_LEN16_HEADER_BYTES = 2
GEOM_X_FROM_PART_NAME_BLOCK = -16
GEOM_Y_FROM_PART_NAME_BLOCK = -12
GEOM_ORI_FROM_PART_NAME_BLOCK = -24
META_TYPE_FROM_PART_NAME_BLOCK = -36
META_PAGE_FROM_PART_NAME_BLOCK = -27
META_FLAGS_FROM_PART_NAME_BLOCK = -44
META_SHOW_NAME_FROM_PART_NAME_BLOCK = -33
META_SHOW_VALUE_FROM_PART_NAME_BLOCK = -3
META_SHOW_VALUE_SUPPRESS_FROM_PART_NAME_BLOCK = -4
META_WIDTH_FROM_PART_NAME_BLOCK = -8
META_HEIGHT_FROM_PART_NAME_BLOCK = -4

LINE_POINT_STRIDE = 11
LINE_XY_DELTA = 4
LINE_NET_GUESS_FROM_POINT_BASE = -12
LINE_PAGE_GUESS_FROM_POINT_BASE = -21
LINE_REGION_GUESS_FROM_POINT_BASE = -9
LINE_NUMBER_GUESS_FROM_POINT_BASE = -6
LINE_CONNECT1_GUESS_FROM_POINT_BASE = -39
LINE_CONNECT2_GUESS_FROM_POINT_BASE = -36
LINE_CONNECTL1_GUESS_FROM_POINT_BASE = -33
LINE_CONNECTL2_GUESS_FROM_POINT_BASE = -30
LINE_CONNECTB1_GUESS_FROM_POINT_BASE = -27
LINE_CONNECTB2_GUESS_FROM_POINT_BASE = -24
LINE_CONNECTMODE1_GUESS_FROM_POINT_BASE = -18
LINE_CONNECTMODE2_GUESS_FROM_POINT_BASE = -15

NET_NUMBER_FROM_NAME_TAG3F = -5
NET_ACTIVE_LINE_FROM_NAME_TAG3F = -11
NET_ACTIVE_POINT_FROM_NAME_TAG3F = -8
NET_ACTIVE_LINE_ALT_FROM_NAME_TAG3F = -23
NET_ACTIVE_POINT_ALT_FROM_NAME_TAG3F = 27

PIN_RECORD_ENABLED = 0x01
PIN_TOKEN_STRIDE = 3
PIN_XYZ_LEAD_OFF = (13, 17, 21)
PIN_XYZ_PAYLOAD_OFF = (14, 18, 22)
PIN_NAME_LEN16_BE_OFF = 25

PATTERN_TYPE_FROM_NAME_BLOCK = -61
PATTERN_NUMBER1_FROM_NAME_BLOCK = -54
PATTERN_NUMBER2_FROM_NAME_BLOCK = -51
PATTERN_SPACING1_FROM_NAME_BLOCK = -48
PATTERN_SPACING2_FROM_NAME_BLOCK = -44
PATTERN_SPACING3_FROM_NAME_BLOCK = -39
PATTERN_LOCK_FROM_NAME_BLOCK = -35
PATTERN_ORIENTATION_FROM_NAME_BLOCK = -34
PATTERN_WIDTH_FROM_NAME_BLOCK = -31
PATTERN_HEIGHT_FROM_NAME_BLOCK = -27
PATTERN_PAD_WIDTH_FROM_NAME_BLOCK = -23
PATTERN_PAD_HEIGHT_FROM_NAME_BLOCK = -19
PATTERN_PAD_SHAPE_FROM_NAME_BLOCK = -15
PATTERN_SURFACE_PAD_FROM_NAME_BLOCK = -12
PATTERN_PAD_HOLE_FROM_NAME_BLOCK = -11
PATTERN_PAD_HOLE_H_FROM_NAME_BLOCK = -7
PATTERN_PAD_HOLE_TYPE_FROM_NAME_BLOCK = -3


@dataclass
class SeqRecord:
    offset: int
    text: str
    encoding: str


def infer_units_from_asc_hint(strings: list[str]) -> str:
    for s in strings:
        if s == "mm":
            return "mm"
        if s == "mil":
            return "mil"
    return "mm"


def extract_project_dir_from_binary(data: bytes) -> str:
    # Observed project dir encoding:
    #   22 00 + UTF16LE ASCII-path chars (sometimes final high-byte is replaced by a control byte).
    # We decode loosely, then keep directory-like paths only.
    path_re = re.compile(r"^[A-Za-z]:\\")
    best = ""
    n = len(data)
    for i in range(0, n - 4):
        if data[i] != 0x22 or data[i + 1] != 0x00:
            continue
        j = i + 2
        chars: list[str] = []
        while j + 1 < n:
            lo = data[j]
            hi = data[j + 1]
            if hi == 0 and 32 <= lo <= 126:
                chars.append(chr(lo))
                j += 2
                continue
            # Allow one final ASCII low-byte without 00 high-byte.
            if 32 <= lo <= 126 and hi != 0:
                chars.append(chr(lo))
                j += 1
            break
        s = "".join(chars)
        if not path_re.match(s):
            continue
        lower = s.lower()
        if any(lower.endswith(ext) for ext in (".eli", ".step", ".stp", ".png", ".jpg", ".jpeg", ".pn")):
            continue
        tail = s.rsplit("\\", 1)[-1]
        if "." in tail:
            continue
        # Prefer a concrete path over an unresolved variable expression.
        if not best or '%' in best and '%' not in s:
            best = s
    return best


def likely_page_name(s: str) -> bool:
    if SHEET_RE.match(s):
        return True
    if len(s) < 2 or len(s) > 48:
        return False
    if "\\" in s or "/" in s or ":" in s:
        return False
    if PART_REF_RE.match(s) or NET_NAME_RE.match(s):
        return False
    # human-facing title-ish names with spaces or alpha words
    if " " in s and any(ch.isalpha() for ch in s):
        return True
    if s in {"Power", "Compute", "CHANGED", "Default"}:
        return True
    return False


def split_refdes(ref: str) -> tuple[str, str]:
    i = 0
    while i < len(ref) and ref[i].isalpha():
        i += 1
    return ref[:i] or "U", ref


def _has_disallowed_controls(s: str) -> bool:
    if s == "":
        return True
    good = 0
    for ch in s:
        o = ord(ch)
        if o == 0:
            return True
        if o < 32 and ch not in ("\t", "\r", "\n"):
            return True
        if 0xD800 <= o <= 0xDFFF:
            return True
        # Keep decode focused on practical schematic text ranges.
        # This admits Latin, Greek (for symbols), and common punctuation.
        if o > 0x03FF:
            return True
        if ch.isalnum() or ch in " _-./\\:+*#()[]{}<>,;='\"`~!?@$%^&|µ°±×":
            good += 1
    return (good / len(s)) < 0.60


def _decode_len16_utf16(data: bytes, start: int, char_len: int) -> tuple[int, str] | None:
    text_start = start + 2
    text_end = text_start + 2 * char_len
    if text_end > len(data):
        return None
    raw = data[text_start:text_end]
    try:
        text = raw.decode("utf-16le")
    except UnicodeDecodeError:
        return None
    if _has_disallowed_controls(text):
        return None
    return text_end, text


def extract_len16_utf16_stream(data: bytes, min_len: int = 1, max_len: int = 256) -> list[SeqRecord]:
    # Greedy stream parse: strongly reduces overlap noise while preserving
    # high-signal schematic text (refdes/value/name clusters).
    out: list[SeqRecord] = []
    i = 0
    n = len(data)
    while i + 3 < n:
        ln = data[i] | (data[i + 1] << 8)
        if min_len <= ln <= max_len:
            decoded = _decode_len16_utf16(data, i, ln)
            if decoded is not None:
                end, text = decoded
                out.append(SeqRecord(offset=i, text=text, encoding="len16_utf16le"))
                i = end
                continue
        i += 1
    return out


def extract_len16_utf16_noterm_stream(data: bytes, min_len: int = 1, max_len: int = 256) -> list[SeqRecord]:
    # Non-terminated variant observed in the same text regions:
    # <len16><UTF16LE chars...> where the final high-byte is omitted.
    out: list[SeqRecord] = []
    n = len(data)
    for i in range(0, n - 4):
        ln = data[i] | (data[i + 1] << 8)
        if not (min_len <= ln <= max_len):
            continue
        start = i + 2
        end = start + (2 * ln - 1)
        if end > n:
            continue
        raw = data[start:end]
        if len(raw) < 1:
            continue
        body = raw[:-1]
        tail = raw[-1]
        if len(body) % 2 != 0:
            continue
        try:
            text = body.decode("utf-16le") + chr(tail)
        except UnicodeDecodeError:
            continue
        if _has_disallowed_controls(text):
            continue
        out.append(SeqRecord(offset=i, text=text, encoding="len16_utf16le_noterm"))
    return out


def extract_len16_utf16_noterm_stream_greedy(data: bytes, min_len: int = 1, max_len: int = 256) -> list[SeqRecord]:
    # Greedy variant for the same non-terminated format:
    # <len16><UTF16LE chars...> where the final high-byte is omitted.
    # This avoids overlap/suffix artifacts from byte-wise full scans.
    out: list[SeqRecord] = []
    i = 0
    n = len(data)
    while i + 4 < n:
        ln = data[i] | (data[i + 1] << 8)
        if not (min_len <= ln <= max_len):
            i += 1
            continue
        start = i + 2
        end = start + (2 * ln - 1)
        if end > n:
            i += 1
            continue
        raw = data[start:end]
        if len(raw) >= 1:
            body = raw[:-1]
            tail = raw[-1]
            if len(body) % 2 == 0:
                try:
                    text = body.decode("utf-16le") + chr(tail)
                except UnicodeDecodeError:
                    text = ""
                if text != "" and not _has_disallowed_controls(text):
                    out.append(SeqRecord(offset=i, text=text, encoding="len16_utf16le_noterm_greedy"))
                    i = end
                    continue
        i += 1
    return out


def extract_3f_len16_stream(data: bytes, min_len: int = 1, max_len: int = 256) -> list[SeqRecord]:
    # Observed high-yield net-name stream:
    # 3F 00 <len16> then UTF16-like chars with no trailing high-byte zero.
    out: list[SeqRecord] = []
    n = len(data)
    for i in range(0, n - 5):
        if data[i] != 0x3F or data[i + 1] != 0x00:
            continue
        ln = data[i + 2] | (data[i + 3] << 8)
        if not (min_len <= ln <= max_len):
            continue
        start = i + 4
        end = start + (2 * ln - 1)
        if end > n:
            continue
        raw = data[start:end]
        chars: list[str] = []
        ok = True
        for j, b in enumerate(raw):
            if j % 2 == 0:
                if not (32 <= b <= 126):
                    ok = False
                    break
                chars.append(chr(b))
            else:
                if b != 0:
                    ok = False
                    break
        if ok:
            out.append(SeqRecord(offset=i, text="".join(chars), encoding="tag3f_len16_utf16le_noterm"))
    return out


def _good_text_payload(s: str) -> bool:
    if s in TRIVIAL_TEXT:
        return False
    if len(s) > 96:
        return False
    if "\\" in s or s.startswith("@"):
        return False
    return True


def likely_net_name(s: str) -> bool:
    if NET_NAME_RE.match(s):
        return True
    if len(s) < 1 or len(s) > 48:
        return False
    if any(ch.islower() for ch in s):
        return False
    if " " in s:
        return False
    if "\\" in s or s.startswith("@"):
        return False
    if any(ch in s for ch in ("_", "+", "-", "/")):
        return True
    if any(ch.isdigit() for ch in s):
        return True
    u = s.upper()
    if u in {"GND", "VCC", "AGND", "DGND", "PGND", "VIN", "VBUS", "VUSB", "RST"}:
        return True
    if u.endswith("GND") or u.endswith("VCC"):
        return True
    return False


def _looks_base_ref_token(s: str) -> bool:
    return bool(BASE_REF_RE.match(s) and len(s) <= 5)


def _parse_component_tail_tokens(ref: str, tail_tokens: list[str], part_name: str) -> tuple[str, str, str]:
    value = ""
    base_ref = ""
    base_name = part_name

    # Typical observed order:
    # [value?], [base_ref?], [base_name?]
    if len(tail_tokens) >= 3 and _looks_base_ref_token(tail_tokens[1]):
        value = tail_tokens[0]
        base_ref = tail_tokens[1]
        if len(tail_tokens[2]) >= 2:
            base_name = tail_tokens[2]
        return value, base_ref, base_name

    if len(tail_tokens) >= 2 and _looks_base_ref_token(tail_tokens[0]):
        base_ref = tail_tokens[0]
        if len(tail_tokens[1]) >= 2:
            base_name = tail_tokens[1]
        return value, base_ref, base_name

    if len(tail_tokens) >= 2:
        value = tail_tokens[0]
        if not (_looks_base_ref_token(tail_tokens[1]) and len(tail_tokens[1]) <= 2):
            base_name = tail_tokens[1]
        return value, base_ref, base_name

    if len(tail_tokens) == 1:
        t = tail_tokens[0]
        if _looks_base_ref_token(t):
            base_ref = t
        elif len(t) >= 2:
            base_name = t
    return value, base_ref, base_name


def _extract_local_short_fields(ref: str, ref_offset: int, short_seq: list[SeqRecord]) -> tuple[list[str], str]:
    if not short_seq:
        return [], ""

    idx = -1
    for i, rec in enumerate(short_seq):
        if rec.offset == ref_offset and rec.text == ref:
            idx = i
            break
    if idx < 0:
        # Some records differ by a small offset between streams.
        best_delta = 6
        for i, rec in enumerate(short_seq):
            if rec.text != ref:
                continue
            d = abs(rec.offset - ref_offset)
            if d <= best_delta:
                best_delta = d
                idx = i
                if d == 0:
                    break
    if idx < 0:
        return [], ""

    tokens: list[str] = []
    lib_path = ""
    part1_idx = -1
    for j in range(idx + 1, min(idx + 24, len(short_seq))):
        t = short_seq[j].text
        if t == "Part 1":
            part1_idx = j
            break
        if t in TRIVIAL_TEXT:
            continue
        tokens.append(t)
    if part1_idx >= 0:
        for j in range(part1_idx + 1, min(part1_idx + 16, len(short_seq))):
            t = short_seq[j].text
            if ".eli" in t:
                lib_path = t
                break
    if not lib_path:
        for j in range(idx + 1, min(idx + 32, len(short_seq))):
            t = short_seq[j].text
            if ".eli" in t:
                lib_path = t
                break
    return tokens, lib_path


def _decode_be24_with_bias(data: bytes, pos: int) -> float | None:
    if pos < 0 or pos + 3 > len(data):
        return None
    raw = int.from_bytes(data[pos : pos + 3], "big")
    return (raw - COORD_BIAS_BE24) / 10000.0


def _is_0p01_grid(v: float, tol: float = 1e-6) -> bool:
    return abs(v * 100.0 - round(v * 100.0)) <= tol


def _decode_s8(data: bytes, pos: int) -> int | None:
    v = _decode_u8(data, pos)
    if v is None:
        return None
    return v - 256 if v >= 128 else v


def _decode_be_len16_string_at(data: bytes, pos: int, min_len: int = 0, max_len: int = 256) -> tuple[int, str] | None:
    if pos < 0 or pos + 2 > len(data):
        return None
    ln = (data[pos] << 8) | data[pos + 1]
    if not (min_len <= ln <= max_len):
        return None
    end = pos + 2 + 2 * ln
    if end > len(data):
        return None
    raw = data[pos + 2 : end]
    try:
        text = raw.decode("utf-16be")
    except UnicodeDecodeError:
        return None
    if _has_disallowed_controls(text):
        return None
    return end, text


def _extract_component_head_fields_be(
    data: bytes, ref: str, ref_offset_hint: int, part_name_hint: str
) -> tuple[str, str, str, str] | None:
    # Deterministic local component head shape observed in binary:
    #   <len16be part_name><len16be refdes><len16be value><len16be base_ref><len16be base_name>...
    token = bytes([(len(ref) >> 8) & 0xFF, len(ref) & 0xFF]) + ref.encode("utf-16be")
    s = max(0, ref_offset_hint - 96)
    e = min(len(data), ref_offset_hint + 96)
    cands: list[int] = []
    i = s
    while True:
        j = data.find(token, i, e)
        if j < 0:
            break
        cands.append(j)
        i = j + 1
    if not cands:
        return None
    cands.sort(key=lambda p: abs(p - ref_offset_hint))

    for ref_pos in cands:
        # Validate previous part-name token when available.
        part_name = part_name_hint
        pn_pos = ref_pos - (2 + 2 * len(part_name_hint))
        if part_name_hint != "" and pn_pos >= 0:
            prev = _decode_be_len16_string_at(data, pn_pos, min_len=1, max_len=256)
            if prev is not None:
                _, prev_text = prev
                if prev_text != part_name_hint and not part_name_hint.startswith("#"):
                    continue
                part_name = prev_text

        p = ref_pos + 2 + 2 * len(ref)
        v = _decode_be_len16_string_at(data, p, min_len=0, max_len=256)
        if v is None:
            continue
        p, value = v
        br = _decode_be_len16_string_at(data, p, min_len=0, max_len=32)
        if br is None:
            continue
        p, base_ref = br
        bn = _decode_be_len16_string_at(data, p, min_len=0, max_len=256)
        if bn is None:
            continue
        _, base_name = bn
        return part_name, value, base_ref, base_name
    return None


def _decode_branch_index_guess(b: int | None) -> int:
    # Wire branch indices appear to use small non-negative values with -1 sentinel.
    # Empirically, value 63 behaves like sentinel.
    if b is None:
        return -1
    v = b % 64
    if v == 63:
        return -1
    if 0 <= v <= 62:
        return int(v)
    return -1


def _part_name_block_start(ref_offset: int, part_name: str) -> int:
    # Records are length-prefixed UTF16-like strings:
    # <len16><text-bytes>. ref follows part_name in this stream.
    return ref_offset - (PART_NAME_LEN16_HEADER_BYTES + 2 * len(part_name))


def _decode_component_geometry(data: bytes, ref_offset: int, part_name: str) -> tuple[float | None, float | None, int | None, float | None]:
    
    # Use the part-name len16 block as a stable local anchor.
    pn_start = _part_name_block_start(ref_offset, part_name)
    x_pos = pn_start + GEOM_X_FROM_PART_NAME_BLOCK
    y_pos = pn_start + GEOM_Y_FROM_PART_NAME_BLOCK
    ori_pos = pn_start + GEOM_ORI_FROM_PART_NAME_BLOCK

    x = _decode_be24_with_bias(data, x_pos)
    y = _decode_be24_with_bias(data, y_pos)
    if x is None or y is None:
        return None, None, None, None
    if ori_pos < 0 or ori_pos >= len(data):
        return x, y, None, None

    orientation = data[ori_pos] % 4
    angle = 0.0 if orientation == 0 else orientation * 90.0002
    return x, y, orientation, angle


def _decode_u8(data: bytes, pos: int) -> int | None:
    if pos < 0 or pos >= len(data):
        return None
    return data[pos]


def _decode_tok42_value(data: bytes, pos: int) -> int | None:
    # Compact small-int token observed across component/pin records:
    #   0F 42 <val+0x40>
    if pos < 0 or pos + PIN_TOKEN_STRIDE > len(data):
        return None
    if data[pos] != 0x0F or data[pos + 1] != 0x42:
        return None
    return int(data[pos + 2]) - 0x40


def _decode_tok4x_value(data: bytes, pos: int) -> int | None:
    # Compact integer tokens:
    #   0F 42 <v> => v-0x40
    #   0F 43..4F <v> => extended positive range (observed in large net/connect ids)
    if pos < 0 or pos + PIN_TOKEN_STRIDE > len(data):
        return None
    if data[pos] != 0x0F:
        return None
    tag = int(data[pos + 1])
    v = int(data[pos + 2])
    if tag == 0x42:
        return v - 0x40
    if 0x43 <= tag <= 0x4F:
        return ((tag - 0x43) * 256) + 192 + v
    return None


def decode_net_rows_from_name_stream(data: bytes, name_stream: list[SeqRecord]) -> list[dict[str, Any]]:
    # Net records are anchored by the observed 3F-len16 string stream.
    # We prefer a binary signature around each anchor:
    #   Number(-5), ActiveLine(-11), ActivePoint(-8), sentinel(-2 == -1).
    # This captures mixed-case/custom net names that name heuristics miss.
    out: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    seen_numbers: set[int] = set()
    used_numbers: set[int] = set()
    next_auto_number = 0

    for rec in name_stream:
        name = rec.text
        number_raw = _decode_tok4x_value(data, rec.offset + NET_NUMBER_FROM_NAME_TAG3F)
        active_line_raw = _decode_tok4x_value(data, rec.offset + NET_ACTIVE_LINE_FROM_NAME_TAG3F)
        active_point_raw = _decode_tok4x_value(data, rec.offset + NET_ACTIVE_POINT_FROM_NAME_TAG3F)
        sentinel_m2 = _decode_tok4x_value(data, rec.offset - 2)

        has_signature = (
            number_raw is not None
            and active_line_raw is not None
            and active_point_raw is not None
            and sentinel_m2 == -1
            and 0 <= int(number_raw) <= 8191
            and -1 <= int(active_line_raw) <= 8191
            and -1 <= int(active_point_raw) <= 8191
        )

        if not has_signature and not likely_net_name(name):
            continue

        if has_signature:
            number = int(number_raw)
            if number in seen_numbers:
                continue
            seen_numbers.add(number)
        else:
            if name in seen_names:
                continue
            number = int(number_raw) if number_raw is not None else -1

        if number < 0 or number in used_numbers:
            while next_auto_number in used_numbers:
                next_auto_number += 1
            number = next_auto_number
            next_auto_number += 1
        used_numbers.add(int(number))
        seen_names.add(name)

        active_line = int(active_line_raw) if active_line_raw is not None else -1
        active_point = int(active_point_raw) if active_point_raw is not None else -1
        active_line_alt = _decode_tok4x_value(data, rec.offset + NET_ACTIVE_LINE_ALT_FROM_NAME_TAG3F)
        active_point_alt = _decode_tok4x_value(data, rec.offset + NET_ACTIVE_POINT_ALT_FROM_NAME_TAG3F)
        
        # Keep this condition very narrow to avoid degrading the general case.
        t30 = _decode_tok4x_value(data, rec.offset + 30)
        t33 = _decode_tok4x_value(data, rec.offset + 33)
        t36 = _decode_tok4x_value(data, rec.offset + 36)
        t39 = _decode_tok4x_value(data, rec.offset + 39)
        if (
            active_line_alt is not None
            and active_line_alt == 0
            and active_line > 0
            and t30 is not None
            and t33 == 0
            and t36 is not None
            and t39 is not None
            and t30 == (t36 + t39 - 1)
        ):
            active_line = active_line_alt

        out.append(
            {
                "name": name,
                "number": int(number),
                "active_line": int(active_line),
                "active_point": int(active_point),
                # Keep alternates for diagnostics; writer uses primary fields.
                "active_line_alt_guess": int(active_line_alt) if active_line_alt is not None else -1,
                "active_point_alt_guess": int(active_point_alt) if active_point_alt is not None else -1,
                "source_offset": int(rec.offset),
            }
        )

    # If numbered decode produced collisions, fall back to deterministic order.
    numbers = [int(n.get("number", -1)) for n in out]
    if len(set(numbers)) != len(numbers):
        for idx, row in enumerate(out):
            row["number"] = idx
    out.sort(key=lambda r: int(r.get("number", -1)))
    return out


def _decode_tok4x_hidden_id_value(data: bytes, pos: int) -> int | None:
    # Extended id token observed for component HiddenId-like values:
    #   0F 44..4F <v>
    # Empirical decode:
    #   ((tag - 0x43) * 256) + 192 + v
    if pos < 0 or pos + PIN_TOKEN_STRIDE > len(data):
        return None
    if data[pos] != 0x0F:
        return None
    tag = int(data[pos + 1])
    if not (0x44 <= tag <= 0x4F):
        return None
    v = int(data[pos + 2])
    return ((tag - 0x43) * 256) + 192 + v


def _decode_be16_ascii_utf16(data: bytes, pos: int, max_len: int = 32) -> tuple[str, int] | None:
    # Pin name/string-number stream uses big-endian UTF16-ish strings:
    #   <len16_be><00 ch>...
    if pos < 0 or pos + 2 > len(data):
        return None
    n = (data[pos] << 8) | data[pos + 1]
    if n < 0 or n > max_len:
        return None
    p = pos + 2
    chars: list[str] = []
    for _ in range(n):
        if p + 2 > len(data):
            return None
        hi = data[p]
        lo = data[p + 1]
        if hi != 0 or not (32 <= lo <= 126):
            return None
        chars.append(chr(lo))
        p += 2
    return "".join(chars), p


def detect_pin_records_from_binary(data: bytes) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    n = len(data)
    for pos in range(0, n - 120):
        if data[pos] != PIN_RECORD_ENABLED:
            continue

        p_type = _decode_tok42_value(data, pos + 1)
        p_ori = _decode_tok42_value(data, pos + 4)
        p_num = _decode_tok42_value(data, pos + 7)
        p_net = _decode_tok42_value(data, pos + 10)
        if None in (p_type, p_ori, p_num, p_net):
            continue
        if not (
            -1 <= int(p_type) <= 16
            and -1 <= int(p_ori) <= 16
            and -1 <= int(p_num) <= 255
            and -1 <= int(p_net) <= 255
        ):
            continue

        if not (
            data[pos + PIN_XYZ_LEAD_OFF[0]] == 0x3B
            and data[pos + PIN_XYZ_LEAD_OFF[1]] == 0x3B
            and data[pos + PIN_XYZ_LEAD_OFF[2]] == 0x3B
        ):
            continue

        p_x = _decode_be24_with_bias(data, pos + PIN_XYZ_PAYLOAD_OFF[0])
        p_y = _decode_be24_with_bias(data, pos + PIN_XYZ_PAYLOAD_OFF[1])
        p_len = _decode_be24_with_bias(data, pos + PIN_XYZ_PAYLOAD_OFF[2])
        if p_x is None or p_y is None or p_len is None:
            continue
        if not (-2000.0 <= p_x <= 2000.0 and -2000.0 <= p_y <= 2000.0 and -2000.0 <= p_len <= 2000.0):
            continue

        s1 = _decode_be16_ascii_utf16(data, pos + PIN_NAME_LEN16_BE_OFF, max_len=32)
        if s1 is None:
            continue
        p_name, s1_end = s1
        s2 = _decode_be16_ascii_utf16(data, s1_end, max_len=32)
        if s2 is None:
            continue
        p_strnum, s2_end = s2

        show_name_guess = 1 if _decode_u8(data, pos + 34) not in (None, 0) else 0
        pin_num_x_shift = _decode_be24_with_bias(data, s2_end + 3)
        pin_num_y_shift = _decode_be24_with_bias(data, s2_end + 7)
        pin_name_x_shift = _decode_be24_with_bias(data, s2_end + 11)
        pin_name_y_shift = _decode_be24_with_bias(data, s2_end + 15)
        electric_type = _decode_tok42_value(data, s2_end + 18)
        name_font_size = _decode_tok42_value(data, s2_end + 26)
        name_font_width = _decode_be24_with_bias(data, s2_end + 30)
        name_font_scale = _decode_be24_with_bias(data, s2_end + 34)

        out.append(
            {
                "offset": int(pos),
                "enabled": "Y",
                "type": int(p_type),
                "orientation": int(p_ori),
                "number": int(p_num),
                "net_number": int(p_net),
                "x": float(p_x),
                "y": float(p_y),
                "length": float(p_len),
                "name": p_name,
                "string_number": p_strnum,
                "fconnect": "N",
                "show_name": "Y" if show_name_guess else "N",
                "pin_num_x_shift": float(pin_num_x_shift) if pin_num_x_shift is not None else 0.0,
                "pin_num_y_shift": float(pin_num_y_shift) if pin_num_y_shift is not None else 0.0,
                "pin_name_x_shift": float(pin_name_x_shift) if pin_name_x_shift is not None else 0.0,
                "pin_name_y_shift": float(pin_name_y_shift) if pin_name_y_shift is not None else 0.0,
                "electric_type": int(electric_type) if electric_type is not None else 0,
                "hidden": "N",
                "locked": "N",
                "model_sig": "",
                "no_connect": "N",
                "name_font_size": int(name_font_size) if name_font_size is not None else 5,
                "name_font_width": float(name_font_width) if name_font_width is not None else -2.0,
                "name_font_scale": float(name_font_scale) if name_font_scale is not None else 1.0,
                "net_name": "",
                "signal_delay": 0,
                "group": -1,
                "pin_name_rotate": 0,
                "pin_num_rotate": 0,
            }
        )

    # De-dup on offset while preserving file order.
    uniq: list[dict[str, Any]] = []
    seen: set[int] = set()
    for rec in sorted(out, key=lambda r: int(r["offset"])):
        off = int(rec["offset"])
        if off in seen:
            continue
        seen.add(off)
        uniq.append(rec)
    return uniq


def assign_pins_to_components(
    components: list[dict[str, Any]], pin_records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not components:
        return components
    for c in components:
        c["pins"] = []

    anchors: list[tuple[int, int]] = []
    for idx, c in enumerate(components):
        a = int(c.get("anchor_part_name_start", -1))
        if a >= 0:
            anchors.append((a, idx))
    if not anchors:
        return components

    anchors.sort(key=lambda t: t[0])
    ai = 0
    for rec in sorted(pin_records, key=lambda r: int(r.get("offset", -1))):
        off = int(rec.get("offset", -1))
        if off < 0:
            continue
        while ai + 1 < len(anchors) and anchors[ai + 1][0] <= off:
            ai += 1
        ci = anchors[ai][1]
        row = dict(rec)
        row.pop("offset", None)
        components[ci]["pins"].append(row)
    return components


def infer_component_origin_from_pins(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for c in components:
        pins = c.get("pins", [])
        if not isinstance(pins, list) or not pins:
            c["origin_x"] = float(c.get("origin_x", 0.0))
            c["origin_y"] = float(c.get("origin_y", 0.0))
            continue
        xs: list[float] = []
        ys: list[float] = []
        for p in pins:
            if not isinstance(p, dict):
                continue
            try:
                xs.append(float(p.get("x", 0.0)))
                ys.append(float(p.get("y", 0.0)))
            except (TypeError, ValueError):
                continue
        if not xs or not ys:
            c["origin_x"] = float(c.get("origin_x", 0.0))
            c["origin_y"] = float(c.get("origin_y", 0.0))
            continue
        c["origin_x"] = float((min(xs) + max(xs)) / 2.0)
        c["origin_y"] = float((min(ys) + max(ys)) / 2.0)
    return components


def decode_component_hidden_id_guesses(data: bytes, components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not components:
        return components
    anchors: list[tuple[int, int]] = []
    for idx, c in enumerate(components):
        a = int(c.get("anchor_part_name_start", -1))
        if a >= 0:
            anchors.append((a, idx))
    if not anchors:
        for c in components:
            c["hidden_id"] = 0
        return components

    anchors.sort(key=lambda t: t[0])
    for ai, (start, ci) in enumerate(anchors):
        end = anchors[ai + 1][0] if ai + 1 < len(anchors) else len(data)
        hid_tok4x = None
        tok42_pos_vals: list[int] = []
        for pos in range(start, end):
            if hid_tok4x is None:
                v4 = _decode_tok4x_hidden_id_value(data, pos)
                if v4 is not None and v4 != 700:
                    hid_tok4x = int(v4)
            v2 = _decode_tok42_value(data, pos)
            if v2 is not None and v2 > 0:
                tok42_pos_vals.append(int(v2))

        if hid_tok4x is not None:
            hid_guess = hid_tok4x
        elif tok42_pos_vals:
            if tok42_pos_vals[0] == 2 and len(tok42_pos_vals) > 1:
                hid_guess = tok42_pos_vals[1]
            else:
                hid_guess = tok42_pos_vals[0]
        else:
            hid_guess = 0
        components[ci]["hidden_id"] = int(hid_guess)
    return components


def _decode_shape_type_token(data: bytes, pos: int) -> int | None:
    v = _decode_tok42_value(data, pos)
    if v is not None:
        return int(v)
    # Common encoded value observed for text shapes.
    if pos + 3 <= len(data) and data[pos] == 0x0F and data[pos + 1] == 0x44 and data[pos + 2] == 0xFC:
        return 10
    return None


def _parse_shape_record_at(data: bytes, pos: int, limit: int) -> dict[str, Any] | None:
    if pos < 0 or pos >= len(data) or data[pos] != 0x01:
        return None

    ori = _decode_tok42_value(data, pos + 1)
    shape_type = _decode_shape_type_token(data, pos + 4)
    font_size = _decode_tok42_value(data, pos + 7)
    font_type = _decode_tok42_value(data, pos + 13)
    if None in (ori, shape_type, font_size, font_type):
        return None

    s_font = _decode_be16_ascii_utf16(data, pos + 16, max_len=64)
    if s_font is None:
        return None
    font_name, p = s_font
    s_name = _decode_be16_ascii_utf16(data, p, max_len=128)
    if s_name is None:
        return None
    shape_name, p = s_name

    if p + 7 >= limit or data[p] != 0x3B:
        return None
    pen_width = _decode_be24_with_bias(data, p + 1)
    point_count = _decode_tok42_value(data, p + 4)
    if pen_width is None or point_count is None:
        return None
    if not (1 <= int(point_count) <= 256):
        return None

    cur = p + 7
    pts_flat: list[float] = []
    for _ in range(int(point_count) * 2):
        if cur + 4 > limit or data[cur] != 0x3B:
            return None
        v = _decode_be24_with_bias(data, cur + 1)
        if v is None:
            return None
        pts_flat.append(float(v))
        cur += 4

    # Small flags/padding before trailing font width/scale.
    while cur < limit and data[cur] in (0x00, 0x01) and (cur - (p + 7 + int(point_count) * 8)) < 4:
        cur += 1

    if cur + 8 > limit or data[cur] != 0x3B or data[cur + 4] != 0x3B:
        return None
    font_width = _decode_be24_with_bias(data, cur + 1)
    font_scale = _decode_be24_with_bias(data, cur + 5)
    if font_width is None or font_scale is None:
        return None

    end = cur + 8
    pts_new: list[dict[str, float]] = []
    for i in range(0, len(pts_flat), 2):
        if i + 1 >= len(pts_flat):
            break
        pts_new.append({"x": float(pts_flat[i]), "y": float(pts_flat[i + 1])})

    return {
        "offset": int(pos),
        "end": int(end),
        "orientation": int(ori),
        "type": int(shape_type),
        "font_size": int(font_size),
        "font_color": 0,
        "font_type": int(font_type),
        "font_name": font_name,
        "name": shape_name,
        "pen_width": float(pen_width),
        "points_new": pts_new,
        "font_width": float(font_width),
        "font_scale": float(font_scale),
    }


def detect_shape_records_from_binary(
    data: bytes,
    components: list[dict[str, Any]],
    max_gap: int = 96,
    max_scan: int = 32768,
) -> list[dict[str, Any]]:
    if not components:
        return components

    anchors: list[tuple[int, int]] = []
    for idx, c in enumerate(components):
        a = int(c.get("anchor_part_name_start", -1))
        if a >= 0:
            anchors.append((a, idx))
    if not anchors:
        for c in components:
            c["shapes"] = []
        return components

    anchors.sort(key=lambda t: t[0])
    for _, ci in anchors:
        components[ci]["shapes"] = []

    for ai, (start, ci) in enumerate(anchors):
        end = anchors[ai + 1][0] if ai + 1 < len(anchors) else len(data)
        end = min(end, start + max_scan)

        p = start
        found_any = False
        last_end = start
        while p < end - 32:
            shape = _parse_shape_record_at(data, p, end)
            if shape is not None:
                row = dict(shape)
                row.pop("offset", None)
                row.pop("end", None)
                components[ci]["shapes"].append(row)
                p = int(shape["end"])
                found_any = True
                last_end = int(shape["end"])
                continue
            p += 1
            if found_any and (p - last_end) > max_gap:
                break

    return components


_PATTERN_BAD_NAME_RE = re.compile(r"(\\|\.eli$|\.step$|\.stp$|\.wrl$|\.pn$|\.png$|\.jpg$|\.jpeg$)", re.IGNORECASE)


def _parse_pattern_record_at_name(data: bytes, name_pos: int) -> dict[str, Any] | None:
    s_name = _decode_be16_ascii_utf16(data, name_pos, max_len=96)
    if s_name is None:
        return None
    pattern_name, name_end = s_name

    type_value = _decode_tok42_value(data, name_pos + PATTERN_TYPE_FROM_NAME_BLOCK)
    number1 = _decode_tok42_value(data, name_pos + PATTERN_NUMBER1_FROM_NAME_BLOCK)
    number2 = _decode_tok42_value(data, name_pos + PATTERN_NUMBER2_FROM_NAME_BLOCK)
    spacing1 = _decode_be24_with_bias(data, name_pos + PATTERN_SPACING1_FROM_NAME_BLOCK + 1)
    spacing2 = _decode_be24_with_bias(data, name_pos + PATTERN_SPACING2_FROM_NAME_BLOCK + 1)
    spacing3 = _decode_be24_with_bias(data, name_pos + PATTERN_SPACING3_FROM_NAME_BLOCK + 1)
    lock_raw = _decode_u8(data, name_pos + PATTERN_LOCK_FROM_NAME_BLOCK)
    orientation = _decode_tok42_value(data, name_pos + PATTERN_ORIENTATION_FROM_NAME_BLOCK)
    width = _decode_be24_with_bias(data, name_pos + PATTERN_WIDTH_FROM_NAME_BLOCK + 1)
    height = _decode_be24_with_bias(data, name_pos + PATTERN_HEIGHT_FROM_NAME_BLOCK + 1)
    pad_width = _decode_be24_with_bias(data, name_pos + PATTERN_PAD_WIDTH_FROM_NAME_BLOCK + 1)
    pad_height = _decode_be24_with_bias(data, name_pos + PATTERN_PAD_HEIGHT_FROM_NAME_BLOCK + 1)
    pad_shape = _decode_tok42_value(data, name_pos + PATTERN_PAD_SHAPE_FROM_NAME_BLOCK)
    surface_raw = _decode_u8(data, name_pos + PATTERN_SURFACE_PAD_FROM_NAME_BLOCK)
    pad_hole = _decode_be24_with_bias(data, name_pos + PATTERN_PAD_HOLE_FROM_NAME_BLOCK + 1)
    pad_hole_h = _decode_be24_with_bias(data, name_pos + PATTERN_PAD_HOLE_H_FROM_NAME_BLOCK + 1)
    pad_hole_type = _decode_tok42_value(data, name_pos + PATTERN_PAD_HOLE_TYPE_FROM_NAME_BLOCK)

    req = [
        type_value,
        number1,
        number2,
        spacing1,
        spacing2,
        spacing3,
        lock_raw,
        orientation,
        width,
        height,
        pad_width,
        pad_height,
        pad_shape,
        surface_raw,
        pad_hole,
        pad_hole_h,
        pad_hole_type,
    ]
    if any(v is None for v in req):
        return None

    if lock_raw not in (0, 1) or surface_raw not in (0, 1):
        return None
    if not (0 <= int(orientation) <= 3):
        return None
    if not (-64 <= int(type_value) <= 64):
        return None
    if not (-64 <= int(pad_shape) <= 64):
        return None
    if not (-64 <= int(pad_hole_type) <= 64):
        return None
    if not (-500.0 <= float(width) <= 500.0 and -500.0 <= float(height) <= 500.0):
        return None
    if not (-500.0 <= float(pad_width) <= 500.0 and -500.0 <= float(pad_height) <= 500.0):
        return None

    score = 0
    if pattern_name == "":
        score += 2
    elif _PATTERN_BAD_NAME_RE.search(pattern_name):
        score -= 6
    else:
        score += 6
    if float(width) > 0.0 and float(height) > 0.0:
        score += 2
    if float(pad_width) >= 0.0 and float(pad_height) >= 0.0:
        score += 1
    if int(type_value) in (0, 5, 6, 7, 10):
        score += 1
    if int(number2) >= int(number1):
        score += 1

    return {
        "offset": int(name_pos),
        "name_end": int(name_end),
        "name": pattern_name,
        "type": int(type_value),
        "number1": int(number1),
        "number2": int(number2),
        "spacing1": float(spacing1),
        "spacing2": float(spacing2),
        "spacing3": float(spacing3),
        "lock_properties": "Y" if int(lock_raw) else "N",
        "pattern_orientation": int(orientation),
        "width": float(width),
        "height": float(height),
        "pad_width": float(pad_width),
        "pad_height": float(pad_height),
        "pad_shape": int(pad_shape),
        "surface_pad": "Y" if int(surface_raw) else "N",
        "pad_hole": float(pad_hole),
        "pad_hole_h": float(pad_hole_h),
        "pad_hole_type": int(pad_hole_type),
        # Presently unresolved in binary map; keep explicit guesses.
        "origin_x": 0.0,
        "origin_y": 0.0,
        "score": int(score),
    }


def _parse_pattern_pad_record_at(data: bytes, pos: int) -> dict[str, Any] | None:
    # Pad subrecords are mostly fixed but include a variable-length
    # UTF-16 StringNumber field; decode offsets relative to that end.
    if pos < 0 or pos + 28 > len(data):
        return None
    lead = _decode_u8(data, pos)
    if lead not in (0, 1):
        return None
    num = _decode_tok42_value(data, pos + 1)
    if num is None or int(num) < 0:
        return None
    if data[pos + 4] != 0x3B or data[pos + 8] != 0x3B:
        return None

    x = _decode_be24_with_bias(data, pos + 5)
    y = _decode_be24_with_bias(data, pos + 9)
    s_num = _decode_be16_ascii_utf16(data, pos + 12, max_len=24)
    if s_num is None:
        return None
    string_number, s_end = s_num

    # After StringNumber comes 2 bytes pad/align, then the numeric block.
    pw_pos = s_end + 2
    if pw_pos + 41 > len(data):
        return None
    marker_positions = (pw_pos, pw_pos + 4, pw_pos + 8, pw_pos + 12, pw_pos + 33, pw_pos + 37)
    if any(data[m] != 0x3B for m in marker_positions):
        return None

    pad_width = _decode_be24_with_bias(data, pw_pos + 1)
    pad_height = _decode_be24_with_bias(data, pw_pos + 5)
    pad_hole = _decode_be24_with_bias(data, pw_pos + 9)
    pad_hole_h = _decode_be24_with_bias(data, pw_pos + 13)
    pad_hole_type = _decode_tok42_value(data, pw_pos + 16)
    surface_raw = _decode_u8(data, pw_pos + 19)
    pad_shape = _decode_tok42_value(data, pw_pos + 20)
    inverted_raw = _decode_u8(data, pw_pos + 23)
    angle_idx = _decode_tok42_value(data, pw_pos + 24)
    custom_swell = _decode_be24_with_bias(data, pw_pos + 34)
    custom_shrink = _decode_be24_with_bias(data, pw_pos + 38)

    req = [
        x,
        y,
        pad_width,
        pad_height,
        pad_hole,
        pad_hole_h,
        pad_hole_type,
        surface_raw,
        pad_shape,
        inverted_raw,
        angle_idx,
        custom_swell,
        custom_shrink,
    ]
    if any(v is None for v in req):
        return None
    if surface_raw not in (0, 1) or inverted_raw not in (0, 1):
        return None

    angle = float(angle_idx) * 1.5708
    if angle == 0.0:
        # Empirical default in observed ASC footprints.
        angle = 1.5708

    return {
        "end": int(pw_pos + 41),
        "number": int(num),
        "number_new": int(num),
        "x": float(x),
        "y": float(y),
        "name": str(num),
        "string_number": string_number,
        "inverted": "Y" if int(inverted_raw) else "N",
        "pad_width": float(pad_width),
        "pad_height": float(pad_height),
        "pad_hole": float(pad_hole),
        "pad_hole_h": float(pad_hole_h),
        "pad_hole_type": int(pad_hole_type),
        "surface_pad": "Y" if int(surface_raw) else "N",
        "pad_shape": int(pad_shape),
        "pad_angle": float(angle),
        "custom_swell_new": float(custom_swell),
        "custom_shrink_new": float(custom_shrink),
    }


def _detect_pattern_pads_from_binary(
    data: bytes,
    name_end: int,
    span_end: int,
    max_search: int = 8192,
) -> tuple[list[dict[str, Any]], int]:
    pads: list[dict[str, Any]] = []
    search_end = min(span_end, name_end + max_search)
    if name_end >= search_end:
        return pads, int(name_end)

    first: dict[str, Any] | None = None
    first_pos = -1
    p = name_end
    while p < search_end - 59:
        rec = _parse_pattern_pad_record_at(data, p)
        if rec is not None and int(rec.get("number", -1)) >= 1:
            first = rec
            first_pos = p
            break
        p += 1
    if first is None:
        return pads, int(name_end)

    row0 = dict(first)
    row0.pop("end", None)
    pads.append(row0)

    p = int(first.get("end", first_pos + 59))
    while p < search_end - 59 and len(pads) < 512:
        rec = _parse_pattern_pad_record_at(data, p)
        if rec is None:
            break
        row = dict(rec)
        row.pop("end", None)
        pads.append(row)
        p = int(rec.get("end", p + 59))
    return pads, int(p)


def _parse_pattern_shape_record_at(data: bytes, pos: int) -> dict[str, Any] | None:
    shape_type = _decode_tok42_value(data, pos)
    if shape_type is None or not (-16 <= int(shape_type) <= 32):
        return None
    cur = pos + 3

    coords: list[float] = []
    for _ in range(6):
        if cur + 4 > len(data) or data[cur] != 0x3B:
            return None
        v = _decode_be24_with_bias(data, cur + 1)
        if v is None:
            return None
        coords.append(float(v))
        cur += 4

    enabled_raw = _decode_u8(data, cur)
    if enabled_raw not in (0, 1):
        return None
    cur += 1

    layer = _decode_tok42_value(data, cur)
    if layer is None:
        return None
    cur += 3

    s1 = _decode_be16_ascii_utf16(data, cur, max_len=80)
    if s1 is None:
        return None
    font_name, cur = s1
    s2 = _decode_be16_ascii_utf16(data, cur, max_len=120)
    if s2 is None:
        return None
    text, cur = s2

    all_layers_raw = _decode_u8(data, cur)
    if all_layers_raw not in (0, 1):
        return None
    cur += 1

    text_horz = _decode_tok42_value(data, cur)
    if text_horz is None:
        return None
    cur += 3

    if cur + 8 > len(data) or data[cur] != 0x3B or data[cur + 4] != 0x3B:
        return None
    text_vert_raw = _decode_be24_with_bias(data, cur + 1)
    text_align_raw = _decode_be24_with_bias(data, cur + 5)
    if text_vert_raw is None or text_align_raw is None:
        return None
    cur += 8

    aux1 = _decode_tok42_value(data, cur)
    aux2 = _decode_tok42_value(data, cur + 3)
    if aux1 is None or aux2 is None:
        return None
    cur += 6

    if cur + 4 > len(data) or data[cur] != 0x3B:
        return None
    width = _decode_be24_with_bias(data, cur + 1)
    if width is None:
        return None
    cur += 4

    point_count = _decode_tok42_value(data, cur)
    if point_count is None or not (0 <= int(point_count) <= 256):
        return None
    cur += 3

    points: list[dict[str, float]] = []
    for _ in range(int(point_count)):
        if cur + 8 > len(data) or data[cur] != 0x3B or data[cur + 4] != 0x3B:
            return None
        px = _decode_be24_with_bias(data, cur + 1)
        py = _decode_be24_with_bias(data, cur + 5)
        if px is None or py is None:
            return None
        points.append({"x": float(px), "y": float(py)})
        cur += 8

    return {
        "end": int(cur),
        "shape_type": int(shape_type),
        "enabled": "Y" if int(enabled_raw) else "N",
        "layer": int(layer),
        "x1": float(coords[0]),
        "y1": float(coords[1]),
        "x2": float(coords[2]),
        "y2": float(coords[3]),
        "x3": float(coords[4]),
        "y3": float(coords[5]),
        "font_name": font_name,
        "text": text,
        "all_layers": "Y" if int(all_layers_raw) else "N",
        "text_horz": int(text_horz),
        "text_vert_raw": float(text_vert_raw),
        "text_align_raw": float(text_align_raw),
        "aux1": int(aux1),
        "aux2": int(aux2),
        "width": float(width),
        "points": points,
    }


def _detect_pattern_shapes_from_binary(
    data: bytes,
    start_pos: int,
    span_end: int,
    pattern_width: float,
    pattern_height: float,
    max_search: int = 4096,
) -> tuple[list[dict[str, Any]], int]:
    search_end = min(span_end, start_pos + max_search)
    if start_pos >= search_end:
        return [], int(start_pos)

    best_rows: list[dict[str, Any]] = []
    best_score = -1
    best_end = start_pos
    p = max(0, start_pos)
    while p < search_end - 3:
        count = _decode_tok42_value(data, p)
        if count is None or not (0 <= int(count) <= 512):
            p += 1
            continue
        cur = p + 3
        rows: list[dict[str, Any]] = []
        ok = True
        for _ in range(int(count)):
            rec = _parse_pattern_shape_record_at(data, cur)
            if rec is None:
                ok = False
                break
            row = dict(rec)
            row.pop("end", None)
            pts = row.get("points", [])
            if isinstance(pts, list) and pts and pattern_width != 0.0 and pattern_height != 0.0:
                # Heuristic: ASC Pattern Points_New frequently scales normalized points by footprint W/H.
                row["points_new_guess"] = [
                    {"x": float(pt.get("x", 0.0)) * float(pattern_width), "y": float(pt.get("y", 0.0)) * float(pattern_height)}
                    for pt in pts
                ]
            rows.append(row)
            cur = int(rec["end"])

        if ok:
            # Prefer non-empty shape blocks; tie-break with earliest offset.
            score = int(count)
            if score > best_score:
                best_score = score
                best_rows = rows
                best_end = int(cur)
        p += 1
    return best_rows, int(best_end)


def _parse_pattern_hole_record_at(data: bytes, pos: int) -> dict[str, Any] | None:
    if pos < 0 or pos + 17 > len(data):
        return None
    enabled_raw = _decode_u8(data, pos)
    if enabled_raw not in (0, 1):
        return None
    marker_offsets = (1, 5, 9, 13)
    if any(data[pos + mo] != 0x3B for mo in marker_offsets):
        return None
    x = _decode_be24_with_bias(data, pos + 2)
    y = _decode_be24_with_bias(data, pos + 6)
    d1 = _decode_be24_with_bias(data, pos + 10)
    d2 = _decode_be24_with_bias(data, pos + 14)
    if None in (x, y, d1, d2):
        return None
    return {
        "end": int(pos + 17),
        "enabled": "Y" if int(enabled_raw) else "N",
        "plated": "N",
        "x": float(x),
        "y": float(y),
        "diameter": float(d1),
        "drill": float(d2),
        "group": -1,
    }


def _detect_pattern_holes_from_binary(
    data: bytes,
    start_pos: int,
    span_end: int,
    max_holes: int = 256,
) -> tuple[list[dict[str, Any]], int]:
    count = _decode_tok42_value(data, start_pos)
    if count is None or not (0 <= int(count) <= max_holes):
        return [], int(start_pos)
    cur = start_pos + 3
    rows: list[dict[str, Any]] = []
    for _ in range(int(count)):
        rec = _parse_pattern_hole_record_at(data, cur)
        if rec is None:
            rec = _parse_pattern_hole_record_at(data, cur + 1)
        if rec is None:
            break
        row = dict(rec)
        row.pop("end", None)
        rows.append(row)
        cur = int(rec.get("end", cur + 17))
        if cur >= span_end:
            break
    return rows, int(cur)


def _detect_pattern_model3d_file_from_binary(
    data: bytes,
    start_pos: int,
    span_end: int,
    max_search: int = 8192,
) -> str:
    end = min(span_end, start_pos + max_search)
    p = max(0, start_pos)
    while p < end - 2:
        if data[p] != 0x00:
            p += 1
            continue
        s = _decode_be16_ascii_utf16(data, p, max_len=260)
        if s is None:
            p += 1
            continue
        txt, _ = s
        low = txt.lower()
        if low.endswith(".wrl") or low.endswith(".step") or low.endswith(".stp"):
            return txt
        p += 1
    return ""


def _find_next_tok42(data: bytes, start: int, limit: int) -> tuple[int, int] | None:
    p = max(0, start)
    lim = min(limit, len(data) - 2)
    while p < lim:
        v = _decode_tok42_value(data, p)
        if v is not None:
            return p, int(v)
        p += 1
    return None


def _find_next_nonempty_be16_string(data: bytes, start: int, limit: int, max_len: int = 120) -> tuple[int, str, int] | None:
    p = max(0, start)
    lim = min(limit, len(data) - 2)
    while p < lim:
        s = _decode_be16_ascii_utf16(data, p, max_len=max_len)
        if s is None:
            p += 1
            continue
        txt, end = s
        if txt != "":
            return p, txt, end
        p += 1
    return None


def _detect_pattern_global_metadata_from_binary(
    data: bytes,
    start_pos: int,
    scan_limit: int = 640,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "mounting": -1,
        "pattern_category_name": "",
        "pattern_category_index": -1,
        "pattern_category_types": 0,
        "pattern_type_entries": [],
        "possible_names": [],
    }
    if start_pos < 0 or start_pos >= len(data):
        return out
    end = min(len(data), start_pos + scan_limit)

    # Skip 3D transform tuple if present: 9 be24 values.
    p = start_pos
    be24_cnt = 0
    while p + 4 <= end and data[p] == 0x3B and be24_cnt < 12:
        if _decode_be24_with_bias(data, p + 1) is None:
            break
        p += 4
        be24_cnt += 1

    t0 = _find_next_tok42(data, p, min(end, p + 48))
    if t0 is None:
        return out
    t1 = _find_next_tok42(data, t0[0] + 3, min(end, t0[0] + 64))
    if t1 is None:
        return out
    mount = int(t1[1])
    if mount in (-1, 0, 1, 2, 3):
        out["mounting"] = mount

    # Optional category block.
    s_cat = _find_next_nonempty_be16_string(data, t1[0] + 3, min(end, t1[0] + 160), max_len=120)
    if s_cat is None:
        return out
    _, cat_name, cat_end = s_cat
    out["pattern_category_name"] = cat_name

    t_idx = _find_next_tok42(data, cat_end, min(end, cat_end + 32))
    if t_idx is None:
        return out
    out["pattern_category_index"] = int(t_idx[1])

    t_cnt = _find_next_tok42(data, t_idx[0] + 3, min(end, t_idx[0] + 32))
    if t_cnt is None:
        return out
    type_count = int(t_cnt[1])
    if type_count < 0:
        type_count = 0
    out["pattern_category_types"] = type_count

    # Best-effort parser for Pattern_Type entries.
    cur = t_cnt[0] + 3
    entries: list[dict[str, Any]] = []
    for _ in range(min(type_count, 16)):
        s_name = _find_next_nonempty_be16_string(data, cur, min(end, cur + 220), max_len=120)
        if s_name is None:
            break
        _, type_name, s1_end = s_name

        # Optional description string before numeric pair.
        desc = ""
        t_a_probe = _find_next_tok42(data, s1_end, min(end, s1_end + 32))
        s_desc = _find_next_nonempty_be16_string(data, s1_end, min(end, s1_end + 140), max_len=180)
        after_desc = s1_end
        if s_desc is not None and (t_a_probe is None or s_desc[0] < t_a_probe[0]):
            _, desc, after_desc = s_desc
        t_a = _find_next_tok42(data, after_desc, min(end, after_desc + 40))
        if t_a is None:
            break
        t_b = _find_next_tok42(data, t_a[0] + 3, min(end, t_a[0] + 40))
        if t_b is None:
            break
        entries.append({"name": type_name, "desc": desc, "a": int(t_a[1]), "b": int(t_b[1])})
        cur = t_b[0] + 3
    out["pattern_type_entries"] = entries

    # Optional PossibleNames list after Pattern_Type entries.
    t_pn = _find_next_tok42(data, cur, min(end, cur + 40))
    if t_pn is not None:
        pn_count = int(t_pn[1])
        if 0 <= pn_count <= 64:
            pcur = t_pn[0] + 3
            pnames: list[str] = []
            for _ in range(pn_count):
                s_pn = _find_next_nonempty_be16_string(data, pcur, min(end, pcur + 220), max_len=180)
                if s_pn is None:
                    break
                _, pn_name, pn_end = s_pn
                pnames.append(pn_name)
                pcur = pn_end
            out["possible_names"] = pnames
    return out


def detect_global_pattern_metadata_by_name(
    data: bytes,
    components: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not components:
        return out

    local_offsets_by_name: dict[str, set[int]] = {}
    wanted = sorted(
        {
            str(c.get("pattern", {}).get("name", ""))
            for c in components
            if isinstance(c.get("pattern"), dict) and str(c.get("pattern", {}).get("name", "")) != ""
        }
    )
    for c in components:
        pat = c.get("pattern")
        if not isinstance(pat, dict):
            continue
        name = str(pat.get("name", ""))
        if name == "":
            continue
        off = int(pat.get("local_offset", -1))
        if off >= 0:
            local_offsets_by_name.setdefault(name, set()).add(off)

    for name in wanted:
        enc = name.encode("utf-16be")
        i = 0
        offsets: list[int] = []
        while True:
            j = data.find(enc, i)
            if j < 0:
                break
            i = j + 1
            noff = j - 2
            if noff < 0:
                continue
            rec = _parse_pattern_record_at_name(data, noff)
            if rec is None or str(rec.get("name", "")) != name:
                continue
            offsets.append(int(noff))

        if not offsets:
            continue
        local_offsets = local_offsets_by_name.get(name, set())
        candidates = [o for o in offsets if o not in local_offsets]
        if not candidates:
            continue

        # Global/library pattern records are consistently located after
        # component-local occurrences in observed files.
        chosen_row: dict[str, Any] | None = None
        for noff in sorted(set(candidates), reverse=True):
            rec = _parse_pattern_record_at_name(data, noff)
            if rec is None or str(rec.get("name", "")) != name:
                continue
            pads, p_end = _detect_pattern_pads_from_binary(data, int(rec.get("name_end", noff)), len(data))
            shapes, s_end = _detect_pattern_shapes_from_binary(
                data,
                start_pos=p_end,
                span_end=len(data),
                pattern_width=float(rec.get("width", 0.0)),
                pattern_height=float(rec.get("height", 0.0)),
            )
            holes, h_end = _detect_pattern_holes_from_binary(data, start_pos=s_end, span_end=len(data))
            mf = _detect_pattern_model3d_file_from_binary(data, start_pos=h_end, span_end=len(data))
            meta_start = h_end
            if mf != "":
                mo = data.find(mf.encode("utf-16be"), h_end, min(len(data), h_end + 8192))
                if mo >= 2:
                    meta_start = mo - 2 + 2 + 2 * len(mf)
            meta = _detect_pattern_global_metadata_from_binary(data, start_pos=meta_start)
            row = dict(meta)
            row["source_offset"] = int(noff)
            chosen_row = row
            # Prefer rows with explicit mounting/category/type payload.
            if (
                int(row.get("mounting", -1)) != -1
                or str(row.get("pattern_category_name", "")) != ""
                or bool(row.get("pattern_type_entries", []))
                or bool(row.get("possible_names", []))
            ):
                break

        if chosen_row is not None:
            out[name] = chosen_row
    return out


def _global_pattern_meta_is_plausible(local_pattern: dict[str, Any], meta: dict[str, Any]) -> bool:
    cat = str(meta.get("pattern_category_name", "")).strip()
    idx = int(meta.get("pattern_category_index", -1))
    type_rows = meta.get("pattern_type_entries", [])
    if not isinstance(type_rows, list):
        type_rows = []
    type_count = int(meta.get("pattern_category_types", 0))
    possible_names = meta.get("possible_names", [])
    if not isinstance(possible_names, list):
        possible_names = []

    # Canonical empty-category payload.
    if cat == "" and idx == -1 and type_count == 0 and not type_rows and not possible_names:
        return True

    # Build token set from local pad names/numbers to detect accidental
    # pin-list parsing as category metadata.
    pad_tokens: set[str] = set()
    pads = local_pattern.get("pads", [])
    if isinstance(pads, list):
        for p in pads:
            if not isinstance(p, dict):
                continue
            for k in ("name", "string_number", "number", "number_new"):
                v = str(p.get(k, "")).strip().upper()
                if v != "":
                    pad_tokens.add(v)

    meta_tokens: list[str] = []
    if cat != "":
        meta_tokens.append(cat.upper())
    for e in type_rows:
        if not isinstance(e, dict):
            continue
        n = str(e.get("name", "")).strip().upper()
        d = str(e.get("desc", "")).strip().upper()
        if n != "":
            meta_tokens.append(n)
        if d != "":
            meta_tokens.append(d)
    for pn in possible_names:
        s = str(pn).strip().upper()
        if s != "":
            meta_tokens.append(s)

    if pad_tokens and meta_tokens:
        overlap = sum(1 for t in meta_tokens if t in pad_tokens)
        if overlap >= 2 and (2 * overlap) >= len(meta_tokens):
            return False

    if cat.isdigit() and (type_count > 0 or bool(type_rows)):
        return False

    descs = [str(e.get("desc", "")).strip() for e in type_rows if isinstance(e, dict)]
    nonempty_descs = [d for d in descs if d != ""]
    if nonempty_descs and all(d.isdigit() for d in nonempty_descs):
        return False

    return True


def detect_pattern_records_from_binary(
    data: bytes,
    components: list[dict[str, Any]],
    max_scan: int = 32768,
    back_scan: int = 96,
) -> list[dict[str, Any]]:
    if not components:
        return components

    anchors: list[tuple[int, int]] = []
    cut_anchors: set[int] = set()
    for idx, c in enumerate(components):
        a = int(c.get("anchor_part_name_start", -1))
        if a >= 0:
            anchors.append((a, idx))
            cut_anchors.add(a)
        for aa in c.get("all_part_name_starts", []):
            try:
                av = int(aa)
            except (TypeError, ValueError):
                continue
            if av >= 0:
                cut_anchors.add(av)
    if not anchors:
        for c in components:
            c["pattern"] = {"name": ""}
        return components

    anchors.sort(key=lambda t: t[0])
    cut_sorted = sorted(cut_anchors)
    for _, ci in anchors:
        components[ci]["pattern"] = {"name": ""}

    n = len(data)
    for ai, (start, ci) in enumerate(anchors):
        ref = str(components[ci].get("refdes", ""))
        if NET_PORT_RE.match(ref):
            components[ci]["pattern"] = {"name": ""}
            continue
        end = n
        for a2 in cut_sorted:
            if a2 > start:
                end = a2
                break
        end = min(end, start + max_scan)
        scan_start = max(0, start - back_scan)
        best: dict[str, Any] | None = None

        p = scan_start
        while p < end - 2:
            if data[p] != 0x00:
                p += 1
                continue
            cand = _parse_pattern_record_at_name(data, p)
            if cand is not None:
                if best is None:
                    best = cand
                else:
                    cscore = int(cand.get("score", -9999))
                    bscore = int(best.get("score", -9999))
                    if cscore > bscore:
                        best = cand
                    elif cscore == bscore and int(cand.get("offset", 0)) < int(best.get("offset", 0)):
                        best = cand
            p += 1

        if best is not None:
            row = dict(best)
            row.pop("score", None)
            row["local_offset"] = int(row.get("offset", -1))
            row.pop("offset", None)
            name_end = int(row.pop("name_end", 0))
            pads, pads_end = _detect_pattern_pads_from_binary(data, name_end=name_end, span_end=end)
            row["pads"] = pads
            shapes, shapes_end = _detect_pattern_shapes_from_binary(
                data,
                start_pos=pads_end,
                span_end=end,
                pattern_width=float(row.get("width", 0.0)),
                pattern_height=float(row.get("height", 0.0)),
            )
            row["shapes"] = shapes
            holes, holes_end = _detect_pattern_holes_from_binary(data, start_pos=shapes_end, span_end=end)
            row["holes"] = holes
            row["model3d_file"] = _detect_pattern_model3d_file_from_binary(data, start_pos=holes_end, span_end=end)
            components[ci]["pattern"] = row
        else:
            # Deterministic fallback: some symbols expose package token via base_name
            # but have no local binary pattern block near this anchor.
            bname = str(components[ci].get("base_name", "")).strip()
            if (
                bname != ""
                and " " not in bname
                and any(ch.isdigit() for ch in bname)
                and any(ch in bname for ch in ("_", "-", "/", "."))
            ):
                components[ci]["pattern"] = {"name": bname}

    return components


def _decode_component_meta(data: bytes, pn_start: int, value: str) -> dict[str, int]:
    # Backward-compatible shim; callsites should prefer the contextual decoder.
    return _decode_component_meta_with_context(data, pn_start, "", value, False)


def _decode_component_meta_with_context(
    data: bytes, pn_start: int, ref: str, value: str, has_non_primary_part: bool
) -> dict[str, int]:
    b_type = _decode_u8(data, pn_start + META_TYPE_FROM_PART_NAME_BLOCK)
    b_page = _decode_u8(data, pn_start + META_PAGE_FROM_PART_NAME_BLOCK)
    b_show_name = _decode_u8(data, pn_start + META_SHOW_NAME_FROM_PART_NAME_BLOCK)
    b_show_value = _decode_u8(data, pn_start + META_SHOW_VALUE_FROM_PART_NAME_BLOCK)

    type_value = (b_type % 4) if b_type is not None else 0
    page = (b_page % 8) if b_page is not None else 0

    is_netport = NET_PORT_RE.match(ref) is not None
    if is_netport:
        part_type = 2
        show_name = 1
        show_refdes = 2
        show_value = (b_show_value & 0x02) if b_show_value is not None else 0
    else:
        part_type = 0
        show_refdes = 0
        show_name = (b_show_name & 0x01) if b_show_name is not None else 0
        show_value = 1 if value != "" else 0
        if has_non_primary_part and value != "":
            show_value = 0

    return {
        "type": int(type_value),
        "page": int(page),
        "part_type": int(part_type),
        "show_name": int(show_name),
        "show_refdes": int(show_refdes),
        "show_value": int(show_value),
        
        # schematic symbols close to original defaults.
        "show_numbers": int((type_value + 2) % 4),
    }


def _is_numeric_token(s: str) -> bool:
    return bool(NUM_TOKEN_RE.match(s))


def infer_page_names_from_short_header(short_seq: list[SeqRecord], expected_count: int | None = None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    for rec in short_seq:
        if rec.offset > 0x3000:
            break
        t = rec.text.strip()
        if not t:
            continue
        if t == "Default":
            if out:
                break
            continue
        if t.startswith("Part "):
            if out:
                break
            continue
        if t in TRIVIAL_TEXT:
            continue
        if "\\" in t or "/" in t or t.startswith("@"):
            continue
        if len(t) > 64:
            continue
        if not any(ch.isalpha() for ch in t):
            continue
        if t in seen:
            continue
        out.append(t)
        seen.add(t)
        if expected_count is not None and len(out) >= expected_count:
            break

    if expected_count is not None and out and len(out) < expected_count:
        for i in range(len(out), expected_count):
            out.append(f"Sheet {i + 1}")

    return out


def _parse_component_occurrence(
    seq: list[SeqRecord], short_seq: list[SeqRecord], data: bytes | None, ref: str, idx: int
) -> dict[str, Any]:
    prev = seq[idx - 1].text if idx > 0 else ""
    part_name = prev if _good_text_payload(prev) else "UNKNOWN"
    ref_offset = seq[idx].offset

    # Deterministic repair for truncated part-name tokens:
    # some records expose a shortened len16 name in seq while short_seq
    # carries the full text immediately before the same ref anchor.
    if part_name.startswith("#"):
        short_idx = -1
        for si, srec in enumerate(short_seq):
            if srec.offset == ref_offset and srec.text == ref:
                short_idx = si
                break
        if short_idx > 0:
            prev_short = short_seq[short_idx - 1].text
            if (
                _good_text_payload(prev_short)
                and not PART_REF_RE.match(prev_short)
                and not prev_short.startswith("Part ")
                and len(prev_short) > len(part_name)
            ):
                part_name = prev_short

    local_short_tokens, lib_path = _extract_local_short_fields(ref, ref_offset, short_seq)
    if local_short_tokens:
        tail_tokens = local_short_tokens
    else:
        tail_tokens = []
        for j in range(idx + 1, min(idx + 10, len(seq))):
            t = seq[j].text
            if t == "Part 1":
                break
            if t in TRIVIAL_TEXT:
                continue
            tail_tokens.append(t)

    near_tokens = [seq[j].text for j in range(idx + 1, min(idx + 24, len(seq)))]
    if lib_path == "":
        for t in near_tokens:
            if ".eli" in t and (("\\" in t) or ("/" in t)):
                lib_path = t
                break

    value, base_ref, base_name = _parse_component_tail_tokens(ref, tail_tokens, part_name)

    if data is not None:
        head = _extract_component_head_fields_be(data, ref=ref, ref_offset_hint=ref_offset, part_name_hint=part_name)
        if head is not None:
            pn_be, value_be, base_ref_be, base_name_be = head
            if pn_be != "":
                part_name = pn_be
            if value_be != "":
                value = value_be
            if base_ref_be != "":
                base_ref = base_ref_be
            if base_name_be != "":
                base_name = base_name_be
    part_name_from_base = 0
    if NET_PORT_RE.match(ref):
        base_ref = ""
        if tail_tokens:
            base_name = tail_tokens[0]
    elif part_name == "UNKNOWN":
        # Some records carry value/ref/base-name only in the nearby short stream.
        # Promote a credible base-name to part_name so the component survives
        # later quality filters.
        if len(base_name) >= 2 and not PART_REF_RE.match(base_name) and not NET_NAME_RE.match(base_name):
            part_name = base_name
            part_name_from_base = 1

    pn_start = _part_name_block_start(ref_offset, part_name)

    x = 0.0
    y = 0.0
    orientation = 0
    angle = 0.0
    type_value = 0
    page = 0
    part_type = 0
    show_name = 0
    show_refdes = 0
    show_value = 0
    show_numbers = 2
    width = 9.0
    height = 9.0

    has_non_primary_part = any(t.startswith("Part ") and t != "Part 1" for t in tail_tokens) or any(
        t.startswith("Part ") and t != "Part 1" for t in near_tokens
    )

    if data is not None:
        gx, gy, gori, gangle = _decode_component_geometry(data, ref_offset, part_name)
        if gx is not None and gy is not None:
            x = gx
            y = gy
        if gori is not None:
            orientation = gori
        if gangle is not None:
            angle = gangle
        meta = _decode_component_meta_with_context(data, pn_start, ref, value, has_non_primary_part)
        type_value = int(meta["type"])
        page = int(meta["page"])
        part_type = int(meta["part_type"])
        show_name = int(meta["show_name"])
        show_refdes = int(meta["show_refdes"])
        show_value = int(meta["show_value"])
        show_numbers = int(meta.get("show_numbers", 2))
        if not NET_PORT_RE.match(ref) and show_value:
            b_suppress = _decode_u8(data, pn_start + META_SHOW_VALUE_SUPPRESS_FROM_PART_NAME_BLOCK)
            if b_suppress is not None and (b_suppress & 0x20):
                show_value = 0
        gw = _decode_be24_with_bias(data, pn_start + META_WIDTH_FROM_PART_NAME_BLOCK)
        gh = _decode_be24_with_bias(data, pn_start + META_HEIGHT_FROM_PART_NAME_BLOCK)
        if gw is not None:
            width = gw
        if gh is not None:
            height = gh

    return {
        "refdes": ref,
        "base_refdes": base_ref,
        "part_name": part_name,
        "part_name_from_base": int(part_name_from_base),
        "base_name": base_name,
        "value": value,
        "x": x,
        "y": y,
        "page": page,
        "type": type_value,
        "orientation": orientation,
        "angle": angle,
        "part_type": part_type,
        "show_name": show_name,
        "show_refdes": show_refdes,
        "show_value": show_value,
        "show_numbers": show_numbers,
        "width": width,
        "height": height,
        "lib_path": lib_path,
        "lib_path_variable": lib_path,
        "ref_offset": ref_offset,
        "part_name_start": pn_start,
        "tail_tokens": tail_tokens,
    }


def _pick_component_occurrence(items: list[dict[str, Any]]) -> dict[str, Any]:
    # Keep precision high: first gate on original confidence score.
    cand = [it for it in items if int(it["score"]) >= 3]
    if not cand:
        # Relay/connector multi-gate symbols can miss explicit Part N tags.
        cand = [
            it
            for it in items
            if int(it["score"]) >= 2 and bool(it["has_path"]) and bool(BASE_REF_RE.match(str(it["next"])))
        ]
    if not cand:
        return {}

    # Geometry-bearing records consistently carry lib-path-like tokens.
    path_cand = [it for it in cand if bool(it["has_path"])]
    if path_cand:
        cand = path_cand

    # For multi-part symbols, prefer the part-tagged records.
    part_cand = [it for it in cand if bool(it["has_part"])]
    if part_cand:
        cand = part_cand

    # Pin-name aliases can look like refdes; they are often surrounded by numbers.
    non_numeric_neighbors = [
        it for it in cand if not (_is_numeric_token(str(it["prev"])) and _is_numeric_token(str(it["next"])))
    ]
    if non_numeric_neighbors:
        cand = non_numeric_neighbors

    # Among equivalent candidates, later offset is the stable geometry owner.
    return max(cand, key=lambda it: (int(it["offset"]), int(it["index"])))


def infer_component_records_from_stream(
    seq: list[SeqRecord], short_seq: list[SeqRecord] | None = None, data: bytes | None = None
) -> list[dict]:
    if not seq:
        return []
    if short_seq is None:
        short_seq = []

    by_ref: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for i, rec in enumerate(seq):
        ref = rec.text
        if not PART_REF_RE.match(ref):
            continue
        prev = seq[i - 1].text if i > 0 else ""
        nxt = seq[i + 1].text if i + 1 < len(seq) else ""
        near = [seq[j].text for j in range(i + 1, min(i + 24, len(seq)))]

        score = 0
        if "Part 1" in near:
            score += 3
        if _good_text_payload(prev):
            score += 1
        if _good_text_payload(nxt):
            score += 1
        if PART_REF_RE.match(nxt):
            score -= 3
        if NET_PORT_RE.match(nxt):
            score -= 2

        has_part = any(t.startswith("Part ") for t in near)
        has_path = any(("\\" in t or "/" in t) for t in near)
        by_ref[ref].append(
            {
                "ref": ref,
                "score": score,
                "index": i,
                "offset": rec.offset,
                "has_part": has_part,
                "has_path": has_path,
                "prev": prev,
                "next": nxt,
            }
        )

    chosen: list[tuple[int, str, int]] = []
    for ref, items in by_ref.items():
        pick = _pick_component_occurrence(items)
        if not pick:
            continue
        chosen.append((int(pick["offset"]), ref, int(pick["index"])))
    chosen.sort(key=lambda t: t[0])

    lib_hint_by_ref: dict[str, str] = {}
    for ref, items in by_ref.items():
        for it in sorted(items, key=lambda x: int(x["offset"])):
            _, lib = _extract_local_short_fields(ref, int(it["offset"]), short_seq)
            if lib:
                lib_hint_by_ref[ref] = lib
                break

    pending: list[dict] = []
    parsed_occ_cache: dict[tuple[str, int], dict[str, Any]] = {}

    def _get_occ(ref_key: str, idx_key: int) -> dict[str, Any]:
        key = (ref_key, idx_key)
        cached = parsed_occ_cache.get(key)
        if cached is not None:
            return cached
        parsed = _parse_component_occurrence(seq, short_seq, data, ref_key, idx_key)
        parsed_occ_cache[key] = parsed
        return parsed

    for _, ref, idx in chosen:
        occ = _get_occ(ref, idx)

        if not NET_PORT_RE.match(ref) and occ["value"] == "":
            best_alt: dict[str, Any] | None = None
            for it in sorted(by_ref.get(ref, []), key=lambda x: int(x["offset"])):
                alt_idx = int(it["index"])
                if alt_idx == idx:
                    continue
                alt = _get_occ(ref, alt_idx)
                if alt["part_name"] != occ["part_name"]:
                    continue
                if alt["value"] == "" or _looks_base_ref_token(str(alt["value"])):
                    continue
                best_alt = alt
            if best_alt is not None:
                occ = best_alt

        all_starts: list[int] = []
        for it in by_ref.get(ref, []):
            alt_idx = int(it["index"])
            alt = _get_occ(ref, alt_idx)
            a = int(alt.get("part_name_start", -1))
            if a >= 0:
                all_starts.append(a)
        occ["all_part_name_starts"] = sorted(set(all_starts)) if all_starts else []

        if occ["lib_path"] == "" and ref in lib_hint_by_ref:
            occ["lib_path"] = lib_hint_by_ref[ref]
            occ["lib_path_variable"] = lib_hint_by_ref[ref]

        if not NET_PORT_RE.match(ref):
            # Drop obvious pin-label aliases that slip through as fake refs.
            if occ["part_name"] == "UNKNOWN":
                continue
            if _is_numeric_token(str(occ["part_name"])):
                continue
            if _is_numeric_token(str(occ["value"])) and _is_numeric_token(str(occ["base_name"])):
                continue
            if (("\\" in str(occ["base_name"])) or ("/" in str(occ["base_name"]))) and not occ["lib_path"]:
                continue
            if occ["base_refdes"] == "" and len(str(occ["part_name"])) <= 5 and PART_REF_RE.match(str(occ["part_name"])):
                continue
            if float(occ["y"]) <= -900.0:
                continue

        pending.append(dict(occ))

    refset = {c["refdes"] for c in pending}
    filtered: list[dict] = []
    for c in pending:
        if not NET_PORT_RE.match(c["refdes"]) and c["part_name"] in refset:
            continue
        filtered.append(c)

    out: list[dict] = []
    for num, c in enumerate(filtered):
        row = dict(c)
        row["anchor_ref_offset"] = int(row.get("ref_offset", -1))
        row["anchor_part_name_start"] = int(row.get("part_name_start", -1))
        row["number"] = num
        row.pop("ref_offset", None)
        row.pop("part_name_start", None)
        row.pop("tail_tokens", None)
        out.append(row)
    return out


def infer_component_records(hits, aggressive_names: bool = False) -> list[dict]:
    refs = [h for h in hits if PART_REF_RE.match(h.text)]
    candidates = [h for h in hits if PART_NAME_RE.match(h.text)]
    out: list[dict] = []

    # build index by offset for fast local search
    by_bucket: dict[int, list] = defaultdict(list)
    for h in candidates:
        by_bucket[h.offset // 512].append(h)

    for i, r in enumerate(refs):
        buckets = {(r.offset // 512) + k for k in (-1, 0, 1)}
        local = []
        for b in buckets:
            local.extend(by_bucket.get(b, []))
        local.sort(key=lambda h: abs(h.offset - r.offset))
        part_name = "UNKNOWN"
        value = ""
        if aggressive_names:
            for h in local:
                if h.text == r.text:
                    continue
                if NET_NAME_RE.match(h.text):
                    continue
                if PART_REF_RE.match(h.text):
                    continue
                if h.text in {"DTSCHEM", "Part 1", "Page", "NetPort"}:
                    continue
                if part_name == "UNKNOWN" and len(h.text) >= 2:
                    part_name = h.text
                    continue
                if value == "" and VALUE_RE.match(h.text):
                    value = h.text
                    break
        out.append(
            {
                "refdes": r.text,
                "base_refdes": "",
                "part_name": part_name,
                "value": value,
                "x": 0.0,
                "y": float(i) * 2.54,
                "page": 0,
                "orientation": 0,
                "number": i,
            }
        )
    # de-dup by refdes keep earliest
    seen = set()
    dedup = []
    for c in out:
        if c["refdes"] in seen:
            continue
        seen.add(c["refdes"])
        dedup.append(c)
    return dedup


def recover_line_geometry_from_binary(
    data: bytes,
    components: list[dict[str, Any]],
    net_count: int,
    page_count: int,
    coord_pad: float = 150.0,
    max_chain_len: int = 64,
) -> list[dict[str, Any]]:
    strict_rows = _recover_line_geometry_tok42(
        data=data,
        components=components,
        coord_pad=coord_pad,
        max_chain_len=max(128, max_chain_len),
    )
    heuristic_rows = _recover_line_geometry_heuristic(
        data=data,
        components=components,
        net_count=net_count,
        page_count=page_count,
        coord_pad=coord_pad,
        max_chain_len=max_chain_len,
    )

    if not strict_rows:
        return heuristic_rows
    if len(strict_rows) >= len(heuristic_rows):
        strict_rows.sort(
            key=lambda r: (
                int(r.get("line_net_number", r.get("net_guess_mod64", -1))),
                int(r.get("line_number", r.get("line_number_guess_mod64", -1))),
                int(r.get("base_offset", -1)),
            )
        )
        for idx, row in enumerate(strict_rows):
            row["index"] = idx
        return strict_rows

    def _line_key(row: dict[str, Any]) -> tuple[int, int, tuple[tuple[float, float], ...]]:
        points = row.get("points", [])
        geom = tuple(
            (round(float(p.get("x", 0.0)), 4), round(float(p.get("y", 0.0)), 4))
            for p in points
            if isinstance(p, dict)
        )
        net_no = int(row.get("line_net_number", row.get("net_guess_mod64", -1)))
        line_no = int(row.get("line_number", row.get("line_number_guess_mod64", -1)))
        return net_no, line_no, geom

    strict_keys = {_line_key(r) for r in strict_rows}
    merged: list[dict[str, Any]] = list(strict_rows)
    for row in heuristic_rows:
        if _line_key(row) in strict_keys:
            continue
        merged.append(row)

    merged.sort(
        key=lambda r: (
            int(r.get("line_net_number", r.get("net_guess_mod64", -1))),
            int(r.get("line_number", r.get("line_number_guess_mod64", -1))),
            int(r.get("base_offset", -1)),
        )
    )
    for idx, row in enumerate(merged):
        row["index"] = idx
    return merged


def _recover_line_geometry_tok42(
    data: bytes,
    components: list[dict[str, Any]],
    coord_pad: float = 150.0,
    max_chain_len: int = 256,
) -> list[dict[str, Any]]:
    if not components:
        return []

    xs = [float(c.get("x", 0.0)) for c in components]
    ys = [float(c.get("y", 0.0)) for c in components]
    if not xs or not ys:
        return []

    min_x = min(xs) - coord_pad
    max_x = max(xs) + coord_pad
    min_y = min(ys) - coord_pad
    max_y = max(ys) + coord_pad

    point_base: dict[int, tuple[float, float, int]] = {}
    for i in range(0, len(data) - 8):
        x = _decode_be24_with_bias(data, i)
        y = _decode_be24_with_bias(data, i + LINE_XY_DELTA)
        ptype = _decode_tok42_value(data, i + 7)
        if x is None or y is None or ptype is None:
            continue
        if x < min_x or x > max_x or y < min_y or y > max_y:
            continue
        ptype_i = int(ptype)
        if ptype_i not in (-1, 0, 1):
            continue
        point_base[i] = (round(x, 4), round(y, 4), ptype_i)

    field_off = {
        "connect1": -41,
        "connect2": -38,
        "connectl1": -35,
        "connectl2": -32,
        "connectb1": -29,
        "connectb2": -26,
        "page": -23,
        "connectmode1": -20,
        "connectmode2": -17,
        "line_net_number": -14,
        "region": -11,
        "line_number": -8,
    }

    out: list[dict[str, Any]] = []
    seen_sig: set[tuple] = set()
    for start in sorted(point_base):
        vals: dict[str, int] = {}
        ok = True
        for k, off in field_off.items():
            v = _decode_tok4x_value(data, start + off)
            if v is None:
                ok = False
                break
            vals[k] = int(v)
        if not ok:
            continue
        if vals["page"] < 0 or vals["region"] < 0 or vals["line_number"] < 0 or vals["line_net_number"] < 0:
            continue
        if vals["page"] > 63 or vals["region"] > 8191 or vals["line_number"] > 16383 or vals["line_net_number"] > 8191:
            continue
        if not (-1 <= vals["connect1"] <= 16383 and -1 <= vals["connect2"] <= 16383):
            continue
        if not (-1 <= vals["connectl1"] <= 16383 and -1 <= vals["connectl2"] <= 16383):
            continue
        if not (-1 <= vals["connectb1"] <= 16383 and -1 <= vals["connectb2"] <= 16383):
            continue
        if vals["connectmode1"] not in (-1, 0, 1, 2, 3, 4, 5, 6, 7):
            continue
        if vals["connectmode2"] not in (-1, 0, 1, 2, 3, 4, 5, 6, 7):
            continue

        points: list[dict[str, Any]] = []
        cur = start
        while cur in point_base and len(points) < max_chain_len:
            x, y, ptype = point_base[cur]
            points.append({"x": x, "y": y, "ptype": int(ptype)})
            cur += LINE_POINT_STRIDE
        if len(points) < 2:
            continue

        sig = (
            vals["line_net_number"],
            vals["page"],
            vals["region"],
            vals["line_number"],
            vals["connect1"],
            vals["connect2"],
            vals["connectl1"],
            vals["connectl2"],
            vals["connectb1"],
            vals["connectb2"],
            vals["connectmode1"],
            vals["connectmode2"],
            tuple((float(p["x"]), float(p["y"]), int(p["ptype"])) for p in points),
        )
        if sig in seen_sig:
            continue
        seen_sig.add(sig)

        net_no = int(vals["line_net_number"])
        region = int(vals["region"])
        line_no = int(vals["line_number"])
        cb1 = int(vals["connectb1"])
        cb2 = int(vals["connectb2"])
        cm1 = int(vals["connectmode1"])
        cm2 = int(vals["connectmode2"])
        out.append(
            {
                "index": len(out),
                "decoder": "tok42",
                "base_offset": int(start),
                "point_stride": LINE_POINT_STRIDE,
                "xy_delta": LINE_XY_DELTA,
                "line_net_number": net_no,
                "page": int(vals["page"]),
                "region": region,
                "line_number": line_no,
                "connect1": int(vals["connect1"]),
                "connect2": int(vals["connect2"]),
                "connectl1": int(vals["connectl1"]),
                "connectl2": int(vals["connectl2"]),
                "connectb1": cb1,
                "connectb2": cb2,
                "connectmode1": cm1,
                "connectmode2": cm2,
                # Backward-compatible keys consumed by model_to_asc.
                "net_guess_raw_u8": net_no if 0 <= net_no <= 255 else -1,
                "net_guess_mod16": net_no if net_no >= 0 else -1,
                "net_guess_mod64": net_no,
                "net_guess_mod_count": net_no,
                "page_guess": int(vals["page"]),
                "region_guess_mod32": region,
                "region_guess_mod64": region,
                "line_number_guess_mod32": line_no,
                "line_number_guess_mod64": line_no,
                "connect1_guess_mod64": int(vals["connect1"]),
                "connect2_guess_mod64": int(vals["connect2"]),
                "connectL1_guess_mod64": int(vals["connectl1"]),
                "connectL2_guess_mod64": int(vals["connectl2"]),
                "connectB1_guess_mod64": cb1,
                "connectB2_guess_mod64": cb2,
                "connectB1_guess_s8": cb1,
                "connectB2_guess_s8": cb2,
                "connectB1_guess_norm": cb1,
                "connectB2_guess_norm": cb2,
                "connect_mode1_guess_mod8": cm1,
                "connect_mode2_guess_mod8": cm2,
                "points": points,
            }
        )
    return out


def _recover_line_geometry_heuristic(
    data: bytes,
    components: list[dict[str, Any]],
    net_count: int,
    page_count: int,
    coord_pad: float = 150.0,
    max_chain_len: int = 64,
) -> list[dict[str, Any]]:
    if not components:
        return []

    xs = [float(c.get("x", 0.0)) for c in components]
    ys = [float(c.get("y", 0.0)) for c in components]
    if not xs or not ys:
        return []

    min_x = min(xs) - coord_pad
    max_x = max(xs) + coord_pad
    min_y = min(ys) - coord_pad
    max_y = max(ys) + coord_pad

    point_base: dict[int, tuple[float, float]] = {}
    for i in range(0, len(data) - 7):
        x = _decode_be24_with_bias(data, i)
        y = _decode_be24_with_bias(data, i + LINE_XY_DELTA)
        if x is None or y is None:
            continue
        if x < min_x or x > max_x or y < min_y or y > max_y:
            continue
        if not (_is_0p01_grid(x) and _is_0p01_grid(y)):
            continue
        point_base[i] = (round(x, 2), round(y, 2))

    chains: list[tuple[int, tuple[tuple[float, float], ...]]] = []
    for start in sorted(point_base):
        if (start - LINE_POINT_STRIDE) in point_base:
            continue
        chain_bases = [start]
        cur = start + LINE_POINT_STRIDE
        while cur in point_base and len(chain_bases) < max_chain_len:
            chain_bases.append(cur)
            cur += LINE_POINT_STRIDE
        if len(chain_bases) < 2:
            continue

        pts = [point_base[b] for b in chain_bases]
        compressed: list[tuple[float, float]] = [pts[0]]
        for p in pts[1:]:
            if p != compressed[-1]:
                compressed.append(p)
        if len(compressed) < 2:
            continue
        if max(max(abs(x), abs(y)) for x, y in compressed) < 2.0:
            continue
        if len(set(compressed)) < 2:
            continue

        chains.append((start, tuple(compressed)))

    # Deduplicate by point geometry.
    unique: list[tuple[int, tuple[tuple[float, float], ...]]] = []
    seen_geom: set[tuple[tuple[float, float], ...]] = set()
    for start, pts in chains:
        if pts in seen_geom:
            continue
        seen_geom.add(pts)
        unique.append((start, pts))

    # Keep dominant offset clusters and remove sparse outlier bins.
    bin_counts: dict[int, int] = defaultdict(int)
    for start, _ in unique:
        bin_counts[start // 0x2000] += 1
    if bin_counts:
        mx = max(bin_counts.values())
        threshold = max(3, int(round(mx * 0.15)))
        keep_bins = {b for b, c in bin_counts.items() if c >= threshold}
        unique = [(start, pts) for start, pts in unique if (start // 0x2000) in keep_bins]

    out: list[dict[str, Any]] = []
    for idx, (start, pts) in enumerate(sorted(unique, key=lambda t: t[0])):
        b_net = _decode_u8(data, start + LINE_NET_GUESS_FROM_POINT_BASE)
        b_page = _decode_u8(data, start + LINE_PAGE_GUESS_FROM_POINT_BASE)
        b_region = _decode_u8(data, start + LINE_REGION_GUESS_FROM_POINT_BASE)
        b_number = _decode_u8(data, start + LINE_NUMBER_GUESS_FROM_POINT_BASE)
        b_c1 = _decode_u8(data, start + LINE_CONNECT1_GUESS_FROM_POINT_BASE)
        b_c2 = _decode_u8(data, start + LINE_CONNECT2_GUESS_FROM_POINT_BASE)
        b_cl1 = _decode_u8(data, start + LINE_CONNECTL1_GUESS_FROM_POINT_BASE)
        b_cl2 = _decode_u8(data, start + LINE_CONNECTL2_GUESS_FROM_POINT_BASE)
        b_cb1 = _decode_u8(data, start + LINE_CONNECTB1_GUESS_FROM_POINT_BASE)
        b_cb2 = _decode_u8(data, start + LINE_CONNECTB2_GUESS_FROM_POINT_BASE)
        b_cm1 = _decode_u8(data, start + LINE_CONNECTMODE1_GUESS_FROM_POINT_BASE)
        b_cm2 = _decode_u8(data, start + LINE_CONNECTMODE2_GUESS_FROM_POINT_BASE)
        s_cb1 = _decode_s8(data, start + LINE_CONNECTB1_GUESS_FROM_POINT_BASE)
        s_cb2 = _decode_s8(data, start + LINE_CONNECTB2_GUESS_FROM_POINT_BASE)

        _ = page_count
        page_guess = int((b_page % 8) if b_page is not None else 0)
        net_guess_raw = int(b_net) if b_net is not None else -1
        net_guess_mod16 = int((net_guess_raw % 16) if net_guess_raw >= 0 else -1)
        net_guess_mod64 = int((net_guess_raw % 64) if net_guess_raw >= 0 else -1)
        net_guess_mod_count = int((net_guess_raw % net_count) if net_count > 0 and net_guess_raw >= 0 else -1)
        region_guess_mod32 = int((b_region % 32) if b_region is not None else 0)
        region_guess_mod64 = int((b_region % 64) if b_region is not None else 0)
        number_guess_mod32 = int((b_number % 32) if b_number is not None else idx)
        number_guess_mod64 = int((b_number % 64) if b_number is not None else idx)
        connect1_guess_mod64 = int((b_c1 % 64) if b_c1 is not None else -1)
        connect2_guess_mod64 = int((b_c2 % 64) if b_c2 is not None else -1)
        connectL1_guess_mod64 = int((b_cl1 % 64) if b_cl1 is not None else -1)
        connectL2_guess_mod64 = int((b_cl2 % 64) if b_cl2 is not None else -1)
        connectB1_guess_mod64 = int((b_cb1 % 64) if b_cb1 is not None else -1)
        connectB2_guess_mod64 = int((b_cb2 % 64) if b_cb2 is not None else -1)
        connectB1_guess_s8 = int(s_cb1) if s_cb1 is not None else -1
        connectB2_guess_s8 = int(s_cb2) if s_cb2 is not None else -1
        connectB1_guess_norm = _decode_branch_index_guess(b_cb1)
        connectB2_guess_norm = _decode_branch_index_guess(b_cb2)
        cm1_guess_mod8 = int((b_cm1 % 8) if b_cm1 is not None else 0)
        cm2_guess_mod8 = int((b_cm2 % 8) if b_cm2 is not None else 0)

        points = []
        for pi, (x, y) in enumerate(pts):
            ptype = 0 if (pi == 0 or pi == len(pts) - 1) else 1
            points.append({"x": x, "y": y, "ptype": ptype})

        out.append(
            {
                "index": idx,
                "base_offset": start,
                "point_stride": LINE_POINT_STRIDE,
                "xy_delta": LINE_XY_DELTA,
                "net_guess_raw_u8": net_guess_raw,
                "net_guess_mod16": net_guess_mod16,
                "net_guess_mod64": net_guess_mod64,
                "net_guess_mod_count": net_guess_mod_count,
                "page_guess": page_guess,
                "region_guess_mod32": region_guess_mod32,
                "region_guess_mod64": region_guess_mod64,
                "line_number_guess_mod32": number_guess_mod32,
                "line_number_guess_mod64": number_guess_mod64,
                "connect1_guess_mod64": connect1_guess_mod64,
                "connect2_guess_mod64": connect2_guess_mod64,
                "connectL1_guess_mod64": connectL1_guess_mod64,
                "connectL2_guess_mod64": connectL2_guess_mod64,
                "connectB1_guess_mod64": connectB1_guess_mod64,
                "connectB2_guess_mod64": connectB2_guess_mod64,
                "connectB1_guess_s8": connectB1_guess_s8,
                "connectB2_guess_s8": connectB2_guess_s8,
                "connectB1_guess_norm": connectB1_guess_norm,
                "connectB2_guess_norm": connectB2_guess_norm,
                "connect_mode1_guess_mod8": cm1_guess_mod8,
                "connect_mode2_guess_mod8": cm2_guess_mod8,
                "points": points,
            }
        )
    return out


def decode_model(dch_path: Path, aggressive_names: bool = False, recover_lines: bool = True) -> dict:
    data = read_bytes(dch_path)
    hits = extract_strings(data, min_len=3)
    texts = [h.text for h in hits]
    texts_set = set(texts)
    lstr = extract_len16_utf16_stream(data, min_len=1, max_len=256)
    lstr_short = extract_len16_utf16_noterm_stream(data, min_len=1, max_len=256)
    nstr = extract_3f_len16_stream(data, min_len=1, max_len=256)

    signature = "DTSCHEM" if any(t == "DTSCHEM" for t in texts) else "UNKNOWN"
    nets = decode_net_rows_from_name_stream(data, nstr)
    if not nets:
        net_names = sorted(set(t for t in texts if NET_NAME_RE.match(t)))
        nets = [{"name": n, "number": i, "active_line": -1, "active_point": -1} for i, n in enumerate(net_names)]
    components = infer_component_records_from_stream(lstr, lstr_short, data=data)
    if not components:
        components = infer_component_records(hits, aggressive_names=aggressive_names)
    components = decode_component_hidden_id_guesses(data, components)
    pin_records = detect_pin_records_from_binary(data)
    components = assign_pins_to_components(components, pin_records)
    components = infer_component_origin_from_pins(components)
    components = detect_shape_records_from_binary(data, components)
    components = detect_pattern_records_from_binary(data, components)
    global_pattern_meta = detect_global_pattern_metadata_by_name(data, components)
    merged_global_pattern_meta = 0
    for c in components:
        pat = c.get("pattern")
        if not isinstance(pat, dict):
            continue
        pname = str(pat.get("name", ""))
        if pname == "":
            continue
        meta = global_pattern_meta.get(pname)
        if not isinstance(meta, dict):
            continue
        if not _global_pattern_meta_is_plausible(pat, meta):
            continue
        for k in (
            "mounting",
            "pattern_category_name",
            "pattern_category_index",
            "pattern_category_types",
            "pattern_type_entries",
            "possible_names",
        ):
            if k in meta:
                pat[k] = meta[k]
        if "source_offset" in meta:
            pat["global_metadata_offset"] = int(meta["source_offset"])
        merged_global_pattern_meta += 1
    shape_records_total = sum(len(c.get("shapes", [])) for c in components)
    pattern_records_total = sum(1 for c in components if isinstance(c.get("pattern"), dict))
    pattern_shapes_total = sum(
        len(c.get("pattern", {}).get("shapes", []))
        for c in components
        if isinstance(c.get("pattern"), dict) and isinstance(c.get("pattern", {}).get("shapes", []), list)
    )
    max_page = max((int(c.get("page", 0)) for c in components), default=0)
    expected_pages = max_page + 1 if components else None
    page_names = infer_page_names_from_short_header(lstr_short, expected_count=expected_pages)
    if not page_names:
        # fallback: terminated stream carries classic "Sheet N" labels in some files
        page_names = sorted(set(h.text for h in hits if h.offset < 0x6000 and SHEET_RE.match(h.text)))
    if not page_names:
        page_names = [f"Sheet {i + 1}" for i in range(expected_pages or 1)]
    units = infer_units_from_asc_hint(texts)
    project_dir = extract_project_dir_from_binary(data)

    recovered_lines: list[dict[str, Any]] = []
    if recover_lines:
        recovered_lines = recover_line_geometry_from_binary(
            data=data,
            components=components,
            net_count=len(nets),
            page_count=len(page_names),
        )

    model = {
        "source": str(dch_path),
        "file_size": len(data),
        "signature": signature,
        "units": units,
        "project_dir": project_dir,
        "pages": [{"name": n, "index": idx + 1} for idx, n in enumerate(page_names)] or [{"name": "Sheet 1", "index": 1}],
        "nets": nets,
        "components": components,
        "recovered_lines": recovered_lines,
        "stats": {
            "extracted_strings": len(texts),
            "unique_strings": len(texts_set),
            "len16_stream_records": len(lstr),
            "len16_noterm_stream_records": len(lstr_short),
            "tag3f_stream_records": len(nstr),
            "net_candidates": len(nets),
            "component_candidates": len(components),
            "pin_candidates": len(pin_records),
            "shape_candidates": int(shape_records_total),
            "pattern_candidates": int(pattern_records_total),
            "pattern_shape_candidates": int(pattern_shapes_total),
            "pattern_global_metadata_names": len(global_pattern_meta),
            "pattern_global_metadata_merged_components": int(merged_global_pattern_meta),
            "page_candidates": len(page_names),
            "recovered_line_candidates": len(recovered_lines),
        },
        "confidence": {
            "signature": "known" if signature == "DTSCHEM" else "unknown",
            "pages": "low-medium",
            "nets": "medium-high",
            "components": "medium-high",
        },
        "notes": [
            "Prototype direct decoder using two observed length-prefixed text streams.",
            "Component refs/names/values and net labels are inferred; topology remains undecoded.",
            "Component X/Y and Orientation are decoded from stable local binary fields relative to ref records.",
            "Pin records are decoded from repeating compact token blocks and assigned by component-anchor ranges.",
            "Shape records are decoded with component-local scans; trailing style/layout fields remain partly heuristic.",
            "Pattern scalar headers are decoded from fixed offsets around BE-len16 pattern-name records.",
            "Line recovery decodes polyline geometry heuristically from recurring be24 x/y pairs.",
        ],
    }
    return model


def main() -> int:
    ap = argparse.ArgumentParser(description="Decode DipTrace DCH into intermediate model (prototype).")
    ap.add_argument("dch")
    ap.add_argument("--out", required=True)
    ap.add_argument("--aggressive-names", action="store_true", help="Infer likely part names/values from nearby strings.")
    ap.add_argument("--no-recover-lines", action="store_true", help="Disable heuristic line-geometry recovery.")
    args = ap.parse_args()

    dch_path = Path(args.dch)
    out_path = Path(args.out)
    model = decode_model(dch_path, aggressive_names=args.aggressive_names, recover_lines=not args.no_recover_lines)
    out_path.write_text(json.dumps(model, indent=2), encoding="utf-8")
    print(f"wrote={out_path}")
    print(
        f"signature={model['signature']} nets={len(model['nets'])} components={len(model['components'])} "
        f"pages={len(model['pages'])} recovered_lines={len(model.get('recovered_lines', []))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
