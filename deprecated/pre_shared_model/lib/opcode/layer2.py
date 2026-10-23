from __future__ import annotations

"""Strict layer2 recordizer for DipTrace DCH opcode tokens.

This module consumes only layer1/layer1-derived tokens and emits a
lossless semantic record stream:
- preamble token fragments
- contiguous record spans
- stable semantic signature
- decomposed signature fields
- carried prefix byte and tail class

It does not decode record payload meaning into application objects.
"""

# TODO(layer2):
# The stable record signature likely decomposes more cleanly than the current

#   01 <class_byte> 0f 42 <record_code_raw> <tail_hi> <tail_lo>
# where:
#   - record_code_raw is an OP0F/0F42-family encoded small integer
#   - record_code = record_code_raw - 0x40
#   - the trailing two bytes act as a role/tail class
# This is why OpcodeLayer2Record now exposes class_byte, record_code_raw, and
# record_code. Keep exact signature matching for now, but prefer investigating
# future family grouping and descriptor matching in terms of:
#   (class_byte, record_code, tail_class)
# rather than treating the whole middle as anonymous header bytes.

from dataclasses import dataclass
from typing import Any

from apps.deprecated.pre_shared_model.lib.opcode.layer1 import OpcodeToken, encode_dch_header, encode_opcode_token_fragment


ROOT_TAILS = {"0f 42"}
ATTACH_TAILS = {"00 0f", "01 0f"}
SPECIAL_TAILS = {"00 01"}

LAYER2_RULESET_ID = "2026-04-08-dsync-reduced34"


# Tuple shape:
#   (b2_hex, mode_hex, b7_hex, prev3_kind, prev2_kind, prev1_kind, intra_orun_offset, next1_kind, next2_kind, next3_kind)
PURE_REDUCED_SIGNATURES = {
    ('00', '0f', '42', 'OP3B24', 'OP3B24', 'ZRUN', 0, 'ZRUN', 'OP0F', 'OP0F'),
    ('00', '00', '0f', 'STR16BE_LEN16', 'OP0F', 'ZRUN', 0, 'ZRUN', 'OP0F', 'ZRUN'),
    ('00', '0f', '42', 'ORUN', 'OP3B24', 'OP3B24', 0, 'ZRUN', 'OP0F', 'OP0F'),
    ('00', '01', '0f', 'OP0F', 'OP0F', 'ZRUN', 0, 'ZRUN', 'OP0F', 'ORUN'),
    ('00', '00', '0f', 'OP0F', 'STR16BE_LEN16', 'OP0F', 1, 'ZRUN', 'OP0F', 'ZRUN'),
    ('00', '0f', '42', 'ZRUN', 'OP3B24', 'OP3B24', 0, 'ZRUN', 'OP0F', 'OP0F'),
    ('00', '0f', '42', 'OP0F', 'OP0F', 'ZRUN', 0, 'ZRUN', 'OP0F', 'OP0F'),
    ('00', '0f', '42', 'ZRUN', 'ORUN', 'ZRUN', 0, 'ZRUN', 'OP0F', 'OP0F'),
    ('01', '0f', '42', 'OP0F', 'OP0F', 'ZRUN', 0, 'OP0F', 'OP0F', 'OP3B24'),
    ('01', '01', '0f', 'OP0F', 'OP0F', 'ZRUN', 0, 'OP0F', 'ORUN', 'OP0F'),
    ('01', '0f', '42', 'STR16BE_LEN16', 'OP0F', 'ZRUN', 0, 'OP0F', 'OP0F', 'ZRUN'),
    ('01', '0f', '42', 'OP3B24', 'OP3B24', 'ZRUN', 0, 'OP0F', 'OP0F', 'OP0F'),
    ('01', '0f', '42', 'OP3B24', 'OP3B24', 'OP3B24', 0, 'OP0F', 'OP0F', 'STR16BE_LEN16'),
    ('00', '00', '0f', 'ORUN', 'ZRUN', 'OP0F', 2, 'ZRUN', 'OP0F', 'ZRUN'),
    ('01', '00', '0f', 'OP0F', 'ORUN', 'OP0F', 2, 'OP0F', 'ZRUN', 'OP0F'),
    ('00', '00', '01', 'OP0F', 'ORUN', 'ZRUN', 0, 'ZRUN', 'OP0F', 'ZRUN'),
    ('00', '0f', '42', 'OP3B24', 'IMM_BE', 'OP0F', 0, 'ZRUN', 'OP0F', 'OP0F'),
    ('00', '0f', '42', 'OP0F', 'ORUN', 'ZRUN', 0, 'ZRUN', 'OP0F', 'OP0F'),
    ('00', '00', '0f', 'ZRUN', 'OP0F', 'ZRUN', 0, 'ZRUN', 'OP0F', 'ZRUN'),
    ('01', '0f', '42', 'ORUN', 'OP3B24', 'OP3B24', 0, 'OP0F', 'OP0F', 'OP0F'),
    ('01', '0f', '42', 'STR16BE_LEN16', 'OP0F', 'ZRUN', 1, 'OP0F', 'OP0F', 'ZRUN'),
    ('00', '0f', '42', 'OP3B24', 'OP3B24', 'ZRUN', 1, 'ZRUN', 'OP0F', 'OP0F'),
    ('00', '01', '0f', 'OP3B24', 'OP3B24', 'ZRUN', 0, 'ZRUN', 'OP0F', 'ORUN'),
    ('00', '00', '0f', 'OP0F', 'ZRUN', 'OP0F', 1, 'ZRUN', 'OP0F', 'ZRUN'),
    ('00', '0f', '42', 'IMM_BE', 'IMM_BE', 'OP0F', 0, 'ZRUN', 'OP0F', 'OP0F'),
    ('00', '0f', '42', 'IMM_BE', 'OP3B24', 'IMM_BE', 0, 'ZRUN', 'OP0F', 'OP0F'),
    ('01', '0f', '42', 'ZRUN', 'OP0F', 'ZRUN', 0, 'OP0F', 'OP0F', 'ZRUN'),
    ('00', '0f', '42', 'ORUN', 'OP3B24', 'OP3B24', 1, 'ZRUN', 'OP0F', 'OP0F'),
    ('00', '0f', '42', 'ZRUN', 'IMM_BE', 'OP0F', 0, 'ZRUN', 'OP0F', 'OP0F'),
    ('01', '0f', '42', 'OP0F', 'STR16BE_LEN16', 'OP0F', 2, 'OP0F', 'OP0F', 'ZRUN'),
    ('01', '0f', '42', 'ZRUN', 'OP3B24', 'OP3B24', 0, 'OP0F', 'OP0F', 'OP0F'),
    ('00', '00', '01', 'OP0F', 'OP0F', 'ZRUN', 0, 'ZRUN', 'OP0F', 'ZRUN'),
    ('01', '0f', '42', 'IMM_BE', 'IMM_BE', 'OP0F', 0, 'OP0F', 'OP0F', 'OP0F'),
    ('01', '0f', '42', 'OP0F', 'OP0F', 'ZRUN', 0, 'OP0F', 'OP0F', 'ZRUN'),
}


@dataclass(frozen=True)
class TokenFragment:
    token_index: int
    start_trim: int
    end_trim: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "token_index": int(self.token_index),
            "start_trim": int(self.start_trim),
            "end_trim": int(self.end_trim),
        }


@dataclass(frozen=True)
class OpcodeTokenSlice:
    token_index: int
    kind: str
    start: int
    end: int
    start_trim: int
    end_trim: int
    value: int | None = None
    text: str | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "token_index": int(self.token_index),
            "kind": str(self.kind),
            "start": int(self.start),
            "end": int(self.end),
            "start_trim": int(self.start_trim),
            "end_trim": int(self.end_trim),
            "length": int(self.end - self.start),
        }
        if self.value is not None:
            out["value"] = int(self.value)
        if self.text is not None:
            out["text"] = self.text
        return out


@dataclass(frozen=True)
class OpcodeLayer2Record:
    index: int
    raw_start: int
    semantic_start: int
    raw_end: int
    prefix_byte: int
    signature_hex: str
    tail_class: str
    fragments: tuple[TokenFragment, ...]

    @property
    def signature_parts(self) -> tuple[int, ...]:
        parts = tuple(int(part, 16) for part in str(self.signature_hex).split())
        if len(parts) != 7:
            raise ValueError(f"expected 7-byte signature, got {self.signature_hex!r}")
        return parts

    @property
    def class_byte(self) -> int:
        return int(self.signature_parts[1])

    @property
    def record_code_raw(self) -> int:
        return int(self.signature_parts[4])

    @property
    def record_code(self) -> int:
        return int(self.record_code_raw - 0x40)

    @property
    def semantic_length(self) -> int:
        return int(self.raw_end - self.semantic_start)

    @property
    def raw_length(self) -> int:
        return int(self.raw_end - self.raw_start)

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": int(self.index),
            "raw_start": int(self.raw_start),
            "semantic_start": int(self.semantic_start),
            "raw_end": int(self.raw_end),
            "raw_length": self.raw_length,
            "semantic_length": self.semantic_length,
            "prefix_byte_hex": f"{self.prefix_byte:02x}",
            "signature_hex": self.signature_hex,
            "class_byte_hex": f"{self.class_byte:02x}",
            "record_code": int(self.record_code),
            "record_code_hex": f"{self.record_code_raw:02x}",
            "tail_class": self.tail_class,
            "fragments": [f.as_dict() for f in self.fragments],
        }


@dataclass(frozen=True)
class OpcodeLayer2Stream:
    header_text: str
    header_end: int
    preamble_fragments: tuple[TokenFragment, ...]
    records: tuple[OpcodeLayer2Record, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "header_text": self.header_text,
            "header_end": int(self.header_end),
            "preamble_fragments": [f.as_dict() for f in self.preamble_fragments],
            "records": [r.as_dict() for r in self.records],
        }


def _tail_class_from_signature(signature_hex: str) -> str:
    parts = signature_hex.split()
    if len(parts) < 7:
        return "unknown"
    tail = f"{parts[5]} {parts[6]}"
    if tail in ROOT_TAILS:
        return "root_like"
    if tail in ATTACH_TAILS:
        return "attach_like"
    if tail in SPECIAL_TAILS:
        return "special"
    return "unknown"


def _token_bytes(token: OpcodeToken) -> bytes:
    return encode_opcode_token_fragment(token)


def _materialize_token_body(tokens: list[OpcodeToken]) -> tuple[int, bytes]:
    if not tokens:
        return 0, b""
    return int(tokens[0].start), b"".join(_token_bytes(token) for token in tokens)


def _byte_at_offset(tokens: list[OpcodeToken], offset: int) -> int:
    for token in tokens:
        if int(token.start) <= offset < int(token.end):
            raw = _token_bytes(token)
            return raw[offset - int(token.start)]
    raise ValueError(f"no token covers offset {offset}")


def _bytes_at(tokens: list[OpcodeToken], start: int, length: int) -> bytes:
    if length <= 0:
        return b""
    end = start + length
    chunks: list[bytes] = []
    cursor = start
    for token in tokens:
        t_start = int(token.start)
        t_end = int(token.end)
        if t_end <= cursor:
            continue
        if t_start >= end:
            break
        raw = _token_bytes(token)
        rel_start = max(cursor, t_start) - t_start
        rel_end = min(end, t_end) - t_start
        if rel_end > rel_start:
            chunks.append(raw[rel_start:rel_end])
            cursor = min(end, t_end)
        if cursor >= end:
            break
    if cursor != end:
        raise ValueError(f"incomplete token window {start}:{end}")
    return b"".join(chunks)


def _byte_at_body(body_start: int, body: bytes, offset: int) -> int:
    rel = int(offset - body_start)
    if rel < 0 or rel >= len(body):
        raise ValueError(f"offset {offset} outside token body")
    return body[rel]


def _bytes_at_body(body_start: int, body: bytes, start: int, length: int) -> bytes:
    if length <= 0:
        return b""
    rel = int(start - body_start)
    end = rel + int(length)
    if rel < 0 or end > len(body):
        raise ValueError(f"window {start}:{start + length} outside token body")
    return body[rel:end]


def _offset_range_to_fragments_from_index(
    tokens: list[OpcodeToken],
    start: int,
    end: int,
    token_index: int,
) -> tuple[tuple[TokenFragment, ...], int]:
    if end < start:
        raise ValueError("invalid fragment range")
    if end == start:
        return (), int(token_index)
    out: list[TokenFragment] = []
    cursor = int(start)
    i = max(0, int(token_index))
    while i < len(tokens):
        token = tokens[i]
        t_start = int(token.start)
        t_end = int(token.end)
        if t_end <= cursor:
            i += 1
            continue
        if t_start >= end:
            break
        rel_start = max(cursor, t_start) - t_start
        rel_end = min(end, t_end) - t_start
        if rel_end > rel_start:
            out.append(TokenFragment(token_index=i, start_trim=rel_start, end_trim=rel_end))
            cursor = min(end, t_end)
        if cursor >= end:
            break
        i += 1
    if cursor != end:
        raise ValueError(f"range {start}:{end} not fully covered by tokens")
    while i > 0 and int(tokens[i - 1].end) > cursor:
        i -= 1
    return tuple(out), i


def encode_layer2_record(record: OpcodeLayer2Record, tokens: list[OpcodeToken]) -> bytes:
    out = bytearray([int(record.prefix_byte) & 0xFF])
    for fragment in record.fragments:
        out.extend(
            encode_opcode_token_fragment(
                tokens[int(fragment.token_index)],
                start_trim=int(fragment.start_trim),
                end_trim=int(fragment.end_trim),
            )
        )
    return bytes(out)


def encode_layer2_stream(stream: OpcodeLayer2Stream, tokens: list[OpcodeToken]) -> bytes:
    out = bytearray(encode_dch_header(stream.header_text))
    for fragment in stream.preamble_fragments:
        out.extend(
            encode_opcode_token_fragment(
                tokens[int(fragment.token_index)],
                start_trim=int(fragment.start_trim),
                end_trim=int(fragment.end_trim),
            )
        )
    for record in stream.records:
        out.extend(encode_layer2_record(record, tokens))
    return bytes(out)


def resolve_token_fragments(
    fragments: tuple[TokenFragment, ...],
    tokens: list[OpcodeToken],
) -> tuple[OpcodeTokenSlice, ...]:
    out: list[OpcodeTokenSlice] = []
    for fragment in fragments:
        token = tokens[int(fragment.token_index)]
        token_start = int(token.start) + int(fragment.start_trim)
        token_end = int(token.start) + int(fragment.end_trim)
        out.append(
            OpcodeTokenSlice(
                token_index=int(fragment.token_index),
                kind=str(token.kind),
                start=token_start,
                end=token_end,
                start_trim=int(fragment.start_trim),
                end_trim=int(fragment.end_trim),
                value=token.value,
                text=token.text,
            )
        )
    return tuple(out)


def record_token_slices(record: OpcodeLayer2Record, tokens: list[OpcodeToken]) -> tuple[OpcodeTokenSlice, ...]:
    return resolve_token_fragments(record.fragments, tokens)


def preamble_token_slices(stream: OpcodeLayer2Stream, tokens: list[OpcodeToken]) -> tuple[OpcodeTokenSlice, ...]:
    return resolve_token_fragments(stream.preamble_fragments, tokens)


def build_layer2_stream_from_semantic_starts(
    *,
    header_text: str,
    header_end: int,
    tokens: list[OpcodeToken],
    semantic_starts: list[int],
) -> OpcodeLayer2Stream:
    ordered_starts = sorted(int(s) for s in semantic_starts)
    if not ordered_starts:
        return OpcodeLayer2Stream(header_text=header_text, header_end=header_end, preamble_fragments=(), records=())

    body_start, body = _materialize_token_body(tokens)
    raw_starts = [int(s - 1) for s in ordered_starts]
    token_index = 0
    preamble_fragments, token_index = _offset_range_to_fragments_from_index(
        tokens,
        int(header_end),
        int(raw_starts[0]),
        token_index,
    )
    file_end = int(tokens[-1].end) if tokens else int(header_end)

    records: list[OpcodeLayer2Record] = []
    for i, semantic_start in enumerate(ordered_starts):
        raw_start = raw_starts[i]
        raw_end = raw_starts[i + 1] if i + 1 < len(raw_starts) else file_end
        prefix_byte = _byte_at_body(body_start, body, raw_start)
        signature_hex = _bytes_at_body(body_start, body, semantic_start, 7).hex(" ")
        fragments, token_index = _offset_range_to_fragments_from_index(
            tokens,
            semantic_start,
            raw_end,
            token_index,
        )
        records.append(
            OpcodeLayer2Record(
                index=i,
                raw_start=raw_start,
                semantic_start=semantic_start,
                raw_end=raw_end,
                prefix_byte=prefix_byte,
                signature_hex=signature_hex,
                tail_class=_tail_class_from_signature(signature_hex),
                fragments=fragments,
            )
        )
    return OpcodeLayer2Stream(
        header_text=header_text,
        header_end=int(header_end),
        preamble_fragments=preamble_fragments,
        records=tuple(records),
    )


def _ctx_token(tokens: list[OpcodeToken], index: int) -> OpcodeToken | None:
    if 0 <= index < len(tokens):
        return tokens[index]
    return None


def _candidate_signature(
    tokens: list[OpcodeToken],
    token_index: int,
    semantic_start: int,
    *,
    body_start: int,
    body: bytes,
) -> tuple[Any, ...]:
    token = tokens[token_index]
    prev3 = _ctx_token(tokens, token_index - 3)
    prev2 = _ctx_token(tokens, token_index - 2)
    prev1 = _ctx_token(tokens, token_index - 1)
    next1 = _ctx_token(tokens, token_index + 1)
    next2 = _ctx_token(tokens, token_index + 2)
    next3 = _ctx_token(tokens, token_index + 3)
    return (
        _bytes_at_body(body_start, body, semantic_start, 7).hex(" "),
        "" if prev3 is None else str(prev3.kind),
        "" if prev2 is None else str(prev2.kind),
        "" if prev1 is None else str(prev1.kind),
        int(semantic_start - int(token.start)),
        "" if next1 is None else str(next1.kind),
        "" if next2 is None else str(next2.kind),
        "" if next3 is None else str(next3.kind),
    )


def _reduced_signature(signature: tuple[Any, ...]) -> tuple[Any, ...]:
    record_signature = str(signature[0]).split()
    b2_hex = record_signature[1] if len(record_signature) >= 2 else ""
    mode_hex = record_signature[5] if len(record_signature) >= 6 else ""
    b7_hex = record_signature[6] if len(record_signature) >= 7 else ""
    return (
        b2_hex,
        mode_hex,
        b7_hex,
        signature[1],
        signature[2],
        signature[3],
        signature[4],
        signature[5],
        signature[6],
        signature[7],
    )


def _candidate_values(
    tokens: list[OpcodeToken],
    token_index: int,
    semantic_start: int,
    *,
    body_start: int,
    body: bytes,
) -> dict[str, Any]:
    prev3 = _ctx_token(tokens, token_index - 3)
    prev2 = _ctx_token(tokens, token_index - 2)
    prev1 = _ctx_token(tokens, token_index - 1)
    prefix_byte = _byte_at_body(body_start, body, semantic_start - 1) if semantic_start > 0 else -1
    return {
        "signature_hex": _bytes_at_body(body_start, body, semantic_start, 7).hex(" "),
        "prefix_byte_hex": f"{prefix_byte:02x}" if prefix_byte >= 0 else "",
        "prev3_value": None if prev3 is None else prev3.value,
        "prev2_value": None if prev2 is None else prev2.value,
        "prev1_value": None if prev1 is None else prev1.value,
    }


def _accept_semantic_start(signature: tuple[Any, ...], values: dict[str, Any]) -> bool:
    reduced = _reduced_signature(signature)
    if reduced in PURE_REDUCED_SIGNATURES:
        return True

    record_signature = str(values.get("signature_hex", ""))
    prefix = values.get("prefix_byte_hex")
    prev3_value = values.get("prev3_value")
    prev2_value = values.get("prev2_value")
    prev1_value = values.get("prev1_value")

    if reduced == ("00", "0f", "42", "OP3B24", "ZRUN", "OP0F", 0, "ZRUN", "OP0F", "OP0F"):
        return prefix == "42" and prev1_value == 16962

    if reduced == ("00", "0f", "42", "OP0F", "OP0F", "OP0F", 0, "ZRUN", "OP0F", "OP0F"):
        return prefix == "42" and prev1_value == 16962

    if reduced == ("00", "0f", "42", "ZRUN", "OP0F", "OP0F", 0, "ZRUN", "OP0F", "OP0F"):
        return prefix == "42" and prev1_value == 16962

    if reduced == ("00", "0f", "42", "STR16BE_LEN16", "ZRUN", "OP0F", 0, "ZRUN", "OP0F", "OP0F"):
        return prefix == "42" and prev1_value == 16962

    if reduced == ("00", "0f", "42", "OP3B24", "OP0F", "OP0F", 0, "ZRUN", "OP0F", "OP0F"):
        if record_signature == "01 00 0f 42 43 0f 42" and prefix == "41" and prev3_value == 10134256 and prev2_value == 16960 and prev1_value == 16961:
            return True
        if prev1_value == 16961:
            return False
        if prev1_value == 16963:
            return prev3_value == 10134256
        return True

    if reduced == ("01", "0f", "42", "OP3B24", "OP3B24", "OP3B24", 0, "OP0F", "OP0F", "ZRUN"):
        return prefix == "00" and prev2_value == 10144256 and prev1_value == 10144256

    if reduced == ("01", "0f", "42", "OP3B24", "OP0F", "OP0F", 0, "OP0F", "OP0F", "OP0F"):
        return prev1_value not in {16961, 16963, 16984}

    if reduced == ("01", "0f", "42", "ZRUN", "OP0F", "OP0F", 0, "OP0F", "OP0F", "OP0F"):
        return prefix == "42" and prev1_value == 16962

    if (
        record_signature.startswith("01 00 0f 42 ")
        and record_signature.endswith(" 0f 42")
        and signature[4] == 0
        and signature[5] == "ZRUN"
        and signature[6] == "OP0F"
        and signature[7] == "OP0F"
        and prefix == "42"
        and prev1_value == 16962
    ):
        return True

    if signature == ("01 01 0f 42 41 0f 42", "OP3B24", "OP3B24", "OP3B24", 0, "OP0F", "OP0F", "ZRUN"):
        return (
            prefix == "00"
            and prev2_value == 10144256
            and prev1_value == 10144256
        )

    if signature == ("01 00 0f 42 40 0f 42", "OP3B24", "OP0F", "OP0F", 0, "ZRUN", "OP0F", "OP0F"):
        if prev1_value == 16963:
            return prev3_value == 10134256
        return prev1_value != 16961

    if signature == ("01 01 0f 42 40 0f 42", "OP3B24", "OP0F", "OP0F", 0, "OP0F", "OP0F", "OP0F"):
        return prev1_value not in {16961, 16963, 16984}

    if signature == ("01 01 0f 42 40 0f 42", "ZRUN", "OP0F", "OP0F", 0, "OP0F", "OP0F", "OP0F"):
        return prefix == "42" and prev1_value == 16962

    if signature == ("01 00 0f 42 40 0f 42", "OP0F", "ZRUN", "OP0F", 0, "ZRUN", "OP0F", "OP0F"):
        return prefix == "42" and prev1_value == 16962

    return False


def recognize_semantic_starts(tokens: list[OpcodeToken]) -> list[int]:
    out: list[int] = []
    body_start, body = _materialize_token_body(tokens)
    for token_index, token in enumerate(tokens):
        if str(token.kind) != "ORUN":
            continue
        for semantic_start in range(int(token.start), int(token.end)):
            if _bytes_at_body(body_start, body, semantic_start, 1) != b"\x01":
                continue
            if _bytes_at_body(body_start, body, semantic_start + 2, 2) != b"\x0f\x42":
                continue
            sig = _candidate_signature(tokens, token_index, semantic_start, body_start=body_start, body=body)
            vals = _candidate_values(tokens, token_index, semantic_start, body_start=body_start, body=body)
            if _accept_semantic_start(sig, vals):
                out.append(int(semantic_start))
    return out


def build_layer2_stream_from_tokens(*, header_text: str, header_end: int, tokens: list[OpcodeToken]) -> OpcodeLayer2Stream:
    return build_layer2_stream_from_semantic_starts(
        header_text=header_text,
        header_end=header_end,
        tokens=tokens,
        semantic_starts=recognize_semantic_starts(tokens),
    )


def build_stream_attachment_tree(records: list[OpcodeLayer2Record]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    roots: list[int] = []
    parent_of: dict[int, int | None] = {}
    summary = {
        "node_count": 0,
        "root_count": 0,
        "attached_count": 0,
        "orphan_attach_count": 0,
        "tail_class_counts": {},
    }
    tail_class_counts: dict[str, int] = {}
    current_owner_idx: int | None = None

    for seq, record in enumerate(records):
        tail_class = str(record.tail_class)
        signature_hex = str(record.signature_hex)
        prefix_byte = f"{record.prefix_byte:02x}"
        start = int(record.raw_start)
        end = int(record.raw_end)
        length = int(record.raw_length)
        index = int(record.index)
        decoded_type_hint = ""

        tail_class_counts[tail_class] = tail_class_counts.get(tail_class, 0) + 1
        node = {
            "index": index,
            "sequence": int(seq),
            "start": start,
            "end": end,
            "length": length,
            "signature_hex": signature_hex,
            "prefix_byte": prefix_byte,
            "tail_class": tail_class,
            "decoded_type_hint": decoded_type_hint,
            "children": [],
        }
        nodes.append(node)

        parent: int | None = None
        if tail_class in {"root_like", "special"}:
            current_owner_idx = len(nodes) - 1
        elif tail_class == "attach_like":
            if current_owner_idx is not None:
                parent = current_owner_idx
                nodes[current_owner_idx]["children"].append(len(nodes) - 1)
                summary["attached_count"] += 1
            else:
                summary["orphan_attach_count"] += 1
        else:
            current_owner_idx = None

        parent_of[len(nodes) - 1] = parent
        if parent is None:
            roots.append(len(nodes) - 1)

    for idx, node in enumerate(nodes):
        node["depth"] = 0 if parent_of[idx] is None else 1

    summary["node_count"] = len(nodes)
    summary["root_count"] = len(roots)
    summary["tail_class_counts"] = tail_class_counts
    return {"roots": roots, "nodes": nodes, "summary": summary}
