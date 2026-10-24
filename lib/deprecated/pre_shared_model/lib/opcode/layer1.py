from __future__ import annotations

"""Strict layer1 lexer for DipTrace DCH bytes.

This module intentionally stops at atomic byte-form tokenization:
- opcode families (`OP0F`, `OP3B24`)
- repeated-byte runs (`ZRUN`, `ORUN`, `REPRUN`)
- string forms (`STR*`)
- generic big-endian immediates (`IMM_BE`)

It does not assign record semantics or tree structure.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


VALID_DCH_HEADERS = frozenset({"DTSCHEM", "DTSCHEM2.21", "DTSCHEM2.22"})


@dataclass(frozen=True)
class L1Event:
    kind: str
    start: int
    end: int
    value: int | None = None
    text: str | None = None

    def as_dict(self) -> dict[str, Any]:
        out = {
            "kind": self.kind,
            "start": int(self.start),
            "end": int(self.end),
            "length": int(self.end - self.start),
        }
        if self.value is not None:
            out["value"] = int(self.value)
        if self.text is not None:
            out["text"] = self.text
        return out


OpcodeToken = L1Event


def read_bytes(path: str | Path) -> bytes:
    return Path(path).read_bytes()


def tokenize_opcode_layer(data: bytes) -> list[OpcodeToken]:
    return parse_layer1_events(data)


def encode_dch_header(header_text: str) -> bytes:
    raw = header_text.encode("ascii")
    if len(raw) > 255:
        raise ValueError("header text too long")
    return bytes([len(raw)]) + raw


def encode_opcode_token(token: OpcodeToken) -> bytes:
    length = int(token.end - token.start)
    value = token.value
    text = token.text
    if token.kind == "ZRUN":
        return b"\x00" * length
    if token.kind == "ORUN":
        return b"\x01" * length
    if token.kind == "REPRUN":
        if not isinstance(value, int):
            raise ValueError("REPRUN missing value")
        return bytes([value & 0xFF]) * length
    if token.kind == "OP0F":
        if value == 0:
            return b"\x0f\x00"
        if not isinstance(value, int):
            raise ValueError("OP0F missing value")
        hi = (value >> 8) & 0xFF
        lo = value & 0xFF
        return bytes([0x0F, hi, lo])
    if token.kind == "OP3B24":
        if not isinstance(value, int):
            raise ValueError("OP3B24 missing value")
        return bytes([0x3B, (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF])
    if token.kind == "IMM_BE":
        if not isinstance(value, int):
            raise ValueError("IMM_BE missing value")
        return int(value).to_bytes(length, "big", signed=False)
    if token.kind == "STR16BE_LEN16":
        if text is None:
            raise ValueError("STR16BE_LEN16 missing text")
        raw = text.encode("utf-16-be")
        return int(len(text)).to_bytes(2, "big") + raw
    if token.kind == "STR16LE_LEN16":
        if text is None:
            raise ValueError("STR16LE_LEN16 missing text")
        raw = text.encode("utf-16-le")
        return int(len(text)).to_bytes(2, "little") + raw
    if token.kind == "STR16LE_LEN16_TAIL8":
        if text is None or not text:
            raise ValueError("STR16LE_LEN16_TAIL8 missing text")
        body = text[:-1].encode("utf-16-le")
        tail_cp = ord(text[-1])
        if not 0 <= tail_cp <= 0xFF:
            raise ValueError("STR16LE_LEN16_TAIL8 final char must fit in 8 bits")
        return int(len(text)).to_bytes(2, "little") + body + bytes([tail_cp])
    if token.kind == "STR16LE_RAW":
        if text is None:
            raise ValueError("STR16LE_RAW missing text")
        return text.encode("utf-16-le")
    raise ValueError(f"unsupported opcode token kind {token.kind!r}")


def encode_opcode_token_fragment(token: OpcodeToken, start_trim: int = 0, end_trim: int | None = None) -> bytes:
    raw = encode_opcode_token(token)
    end = len(raw) if end_trim is None else int(end_trim)
    return raw[int(start_trim) : end]


def _read_dch_header(data: bytes) -> tuple[int, str]:
    parsed = _try_pstr8_ascii(data, 0)
    if parsed is None:
        window = data[:16].hex(" ")
        raise ValueError(f"invalid DCH header at BOF: {window}")
    end, text = parsed
    if text not in VALID_DCH_HEADERS:
        raise ValueError(f"unsupported DCH header {text!r}")
    return end, text


def read_dch_header(data: bytes) -> tuple[int, str]:
    return _read_dch_header(data)


def _is_text_char(ch: str) -> bool:
    cp = ord(ch)
    if ch in ("\t", "\n", "\r"):
        return True
    if 32 <= cp <= 126:
        return True
    if 0x00A0 <= cp <= 0x00FF:
        return True
    if 0x0370 <= cp <= 0x03FF:
        return True
    if 0x2010 <= cp <= 0x203A:
        return True
    return False


def _is_text_string(text: str) -> bool:
    if not text:
        return False
    return all(_is_text_char(ch) for ch in text)


def _try_len16_utf16(
    data: bytes,
    pos: int,
    *,
    byteorder: str,
    encoding: str,
    max_chars: int = 256,
) -> tuple[int, str] | None:
    if pos + 2 > len(data):
        return None
    n = int.from_bytes(data[pos : pos + 2], byteorder)
    if n <= 0 or n > max_chars:
        return None
    end = pos + 2 + 2 * n
    if end > len(data):
        return None
    try:
        text = data[pos + 2 : end].decode(encoding)
    except UnicodeDecodeError:
        return None
    if not _is_text_string(text):
        return None
    return end, text


def _try_len16le_utf16le_tail8(data: bytes, pos: int, max_chars: int = 256) -> tuple[int, str] | None:
    if pos + 2 > len(data):
        return None
    n = data[pos] | (data[pos + 1] << 8)
    if n < 2 or n > max_chars:
        return None
    end = pos + 2 + (2 * n - 1)
    if end > len(data):
        return None
    raw = data[pos + 2 : end]
    if len(raw) < 1:
        return None
    body = raw[:-1]
    tail = raw[-1]
    if len(body) % 2 != 0:
        return None
    if not body:
        return None
    try:
        text = body.decode("utf-16-le") + chr(tail)
    except UnicodeDecodeError:
        return None
    if not _is_text_string(text):
        return None
    return end, text


def _try_ascii_utf16le_pairs(data: bytes, pos: int, min_chars: int = 3, max_chars: int = 512) -> int | None:
    i = pos
    chars = 0
    n = len(data)
    while i + 1 < n and chars < max_chars:
        lo = data[i]
        hi = data[i + 1]
        if hi != 0x00:
            break
        if lo < 32 or lo > 126:
            break
        chars += 1
        i += 2
    if chars < min_chars:
        return None
    return i


def _try_run(data: bytes, pos: int, byte: int, min_len: int = 1) -> int | None:
    if pos >= len(data) or data[pos] != byte:
        return None
    i = pos + 1
    while i < len(data) and data[i] == byte:
        i += 1
    return i if i - pos >= min_len else None


def _try_repeat_run(data: bytes, pos: int, min_len: int = 3) -> int | None:
    if pos >= len(data):
        return None
    byte = data[pos]
    if byte in (0x00, 0x01):
        return None
    return _try_run(data, pos, byte, min_len=min_len)


def _try_runbyte_token(data: bytes, pos: int) -> L1Event | None:
    if pos >= len(data):
        return None
    byte = data[pos]
    if byte == 0x00:
        end = _try_run(data, pos, byte)
        assert end is not None
        return L1Event(kind="ZRUN", start=pos, end=end, value=0)
    if byte == 0x01:
        end = _try_run(data, pos, byte)
        assert end is not None
        return L1Event(kind="ORUN", start=pos, end=end, value=1)
    end = _try_repeat_run(data, pos)
    if end is None:
        return None
    return L1Event(kind="REPRUN", start=pos, end=end, value=int(byte))


def _try_pstr8_ascii(data: bytes, pos: int, min_len: int = 1, max_len: int = 32) -> tuple[int, str] | None:
    if pos >= len(data):
        return None
    n = data[pos]
    if n < min_len or n > max_len:
        return None
    end = pos + 1 + n
    if end > len(data):
        return None
    raw = data[pos + 1 : end]
    if not raw:
        return None
    if any(b < 32 or b > 126 for b in raw):
        return None
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        return None
    return end, text


def _try_0f_opcode(data: bytes, pos: int) -> L1Event | None:
    if pos + 2 >= len(data) or data[pos] != 0x0F:
        return None
    b1 = data[pos + 1]
    b2 = data[pos + 2]
    if b1 == 0x00:
        return L1Event(kind="OP0F", start=pos, end=pos + 2, value=0)
    if 0x41 <= b1 <= 0x4F:
        return L1Event(kind="OP0F", start=pos, end=pos + 3, value=(int(b1) << 8) | int(b2))
    return None


def _build_scalar_chain_checker(n: int, begins_base_token):
    @lru_cache(maxsize=None)
    def can_end_in_base(pos: int) -> bool:
        if pos >= n:
            return pos == n
        if begins_base_token(pos):
            return True
        for width in (4, 3, 2, 1):
            end = pos + width
            if end > n:
                continue
            if any(begins_base_token(pos + k) for k in range(width)):
                continue
            if can_end_in_base(end):
                return True
        return False

    return can_end_in_base


def _try_scalar_token(data: bytes, pos: int, begins_base_token, can_end_in_base) -> L1Event | None:
    n = len(data)
    for width in (4, 3, 2, 1):
        end = pos + width
        if end > n:
            continue
        if any(begins_base_token(pos + k) for k in range(width)):
            continue
        if not can_end_in_base(end):
            continue
        return L1Event(kind="IMM_BE", start=pos, end=end, value=int.from_bytes(data[pos:end], "big"))
    return None


def _try_opcode_token(data: bytes, pos: int) -> L1Event | None:
    n = len(data)
    op0f = _try_0f_opcode(data, pos)
    if op0f is not None:
        return op0f
    b0 = data[pos]
    if b0 == 0x3B and pos + 3 < n:
        raw = (data[pos + 1] << 16) | (data[pos + 2] << 8) | data[pos + 3]
        return L1Event(kind="OP3B24", start=pos, end=pos + 4, value=int(raw))
    return None


def _try_string_token(data: bytes, pos: int) -> L1Event | None:
    be = _try_len16_utf16(data, pos, byteorder="big", encoding="utf-16-be")
    if be is not None:
        end, text = be
        return L1Event(kind="STR16BE_LEN16", start=pos, end=end, value=end - pos, text=text)
    le = _try_len16_utf16(data, pos, byteorder="little", encoding="utf-16-le")
    if le is not None:
        end, text = le
        return L1Event(kind="STR16LE_LEN16", start=pos, end=end, value=end - pos, text=text)
    le_nt = _try_len16le_utf16le_tail8(data, pos)
    if le_nt is not None:
        end, text = le_nt
        return L1Event(kind="STR16LE_LEN16_TAIL8", start=pos, end=end, value=end - pos, text=text)
    le_pairs_end = _try_ascii_utf16le_pairs(data, pos)
    if le_pairs_end is not None:
        text = data[pos:le_pairs_end].decode("utf-16-le")
        return L1Event(kind="STR16LE_RAW", start=pos, end=le_pairs_end, value=le_pairs_end - pos, text=text)
    return None


def _try_non_scalar_token(data: bytes, pos: int) -> L1Event | None:
    ev = _try_opcode_token(data, pos)
    if ev is not None:
        return ev
    ev = _try_string_token(data, pos)
    if ev is not None:
        return ev
    return _try_runbyte_token(data, pos)


def parse_layer1_events(data: bytes) -> list[L1Event]:
    """Strict byte-cursor parser for the first opcode layer.

    This parser is intentionally semantics-free:
    - no record typing
    - no tree/depth inference
    - no scan-to-next-record behavior
    """
    out: list[L1Event] = []
    n = len(data)
    body_start, _header = _read_dch_header(data)
    i = body_start

    @lru_cache(maxsize=None)
    def non_scalar_token_at(pos: int) -> L1Event | None:
        if pos >= n:
            return None
        return _try_non_scalar_token(data, pos)

    @lru_cache(maxsize=None)
    def begins_base_token(pos: int) -> bool:
        return non_scalar_token_at(pos) is not None

    can_end_in_base = _build_scalar_chain_checker(n, begins_base_token)
    while i < n:
        ev = _try_scalar_token(data, i, begins_base_token, can_end_in_base)
        if ev is None:
            ev = non_scalar_token_at(i)
        if ev is None:
            window = data[i : min(i + 16, n)].hex(" ")
            raise ValueError(f"unlexed byte at offset {i}: {window}")

        out.append(ev)
        i = ev.end
    return out


def verify_full_coverage(data: bytes, events: list[L1Event]) -> tuple[bool, str]:
    if len(data) == 0:
        return False, "empty"
    try:
        body_start, _header = _read_dch_header(data)
    except Exception as e:  # noqa: BLE001
        return False, repr(e)
    if not events:
        return (body_start == len(data), "ok" if body_start == len(data) else "no events")
    if int(events[0].start) != body_start:
        return False, f"first event starts at {events[0].start}, expected {body_start}"
    prev_end = body_start
    for idx, ev in enumerate(events):
        if int(ev.start) != prev_end:
            return False, f"gap/overlap before event {idx}: start={ev.start}, prev_end={prev_end}"
        if int(ev.end) <= int(ev.start):
            return False, f"non-positive event length at {idx}"
        prev_end = int(ev.end)
    if prev_end != len(data):
        return False, f"last end={prev_end}, size={len(data)}"
    return True, "ok"
