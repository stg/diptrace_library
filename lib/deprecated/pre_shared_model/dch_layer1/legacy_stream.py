from __future__ import annotations

"""Legacy framing helpers for early stream experiments.

This module is exploratory baggage only. The live opcode pipeline uses:
- lib.deprecated.pre_shared_model.lib.opcode.layer1
- lib.deprecated.pre_shared_model.lib.opcode.layer2
"""

from dataclasses import dataclass
from typing import Any


COMMON_LEADS = {
    0x40,
    0x41,
    0x42,
    0x43,
    0x44,
    0x45,
    0x46,
    0x47,
    0x48,
    0x49,
    0x4A,
    0x4B,
    0x4F,
    0x50,
    0x58,
}


@dataclass(frozen=True)
class OpcodeStart:
    offset: int
    b0: int
    b1: int
    b2: int
    lead: int
    mode: int
    b7: int
    score: int
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "offset": int(self.offset),
            "b0": int(self.b0),
            "b1": int(self.b1),
            "b2": int(self.b2),
            "lead": int(self.lead),
            "mode": int(self.mode),
            "b7": int(self.b7),
            "score": int(self.score),
            "reason": self.reason,
            "start8_hex": f"{self.b0:02x} {self.b1:02x} {self.b2:02x} 0f 42 {self.lead:02x} {self.mode:02x} {self.b7:02x}",
        }


@dataclass(frozen=True)
class OpcodeFrame:
    index: int
    start: int
    end: int
    length: int
    start_marker: OpcodeStart
    family: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": int(self.index),
            "start": int(self.start),
            "end": int(self.end),
            "length": int(self.length),
            "family": self.family,
            "start_marker": self.start_marker.as_dict(),
        }


@dataclass(frozen=True)
class OpcodeLayer1:
    core_frames: list[OpcodeFrame]
    extension_frames: list[OpcodeFrame]
    typed_frames: list[OpcodeFrame]
    aux_frames: list[OpcodeFrame]
    variant_frames: list[OpcodeFrame]
    all_strong_frames: list[OpcodeFrame]


def _mode_next_ok(mode: int, b7: int) -> bool:
    if mode == 0x0F:
        return b7 == 0x42
    if mode == 0x01:
        return b7 == 0x0F
    if mode == 0x00:
        return b7 in (0x0F, 0x01)
    return False


def classify_start_family(s: OpcodeStart) -> str:
    if (
        s.b0 in (0x00, 0x0C, 0x01, 0x10, 0x42)
        and s.b1 == 0x01
        and s.b2 in (0x00, 0x01)
        and _mode_next_ok(s.mode, s.b7)
    ):
        return "core"
    if s.b0 == 0x40 and s.b1 == 0x01 and s.b2 == 0x01 and s.lead == 0x41 and s.mode == 0x0F and s.b7 == 0x42:
        return "extension"
    if s.b1 == 0x01 and s.b2 in (0x00, 0x01) and _mode_next_ok(s.mode, s.b7):
        if s.mode == 0x01 and s.b2 == 0x00:
            return "typed"
        return "aux"
    return "variant"


def detect_opcode_starts(data: bytes) -> list[OpcodeStart]:
    out: list[OpcodeStart] = []
    n = len(data)
    for i in range(0, n - 7):
        if not (
            data[i + 1] == 0x01
            and data[i + 2] in (0x00, 0x01)
            and data[i + 3] == 0x0F
            and data[i + 4] == 0x42
        ):
            continue
        b0 = int(data[i])
        b1 = int(data[i + 1])
        b2 = int(data[i + 2])
        lead = int(data[i + 5])
        mode = int(data[i + 6])
        b7 = int(data[i + 7])

        score = 4
        reasons = ["sig"]
        if _mode_next_ok(mode, b7):
            score += 3
            reasons.append("mode-next")
        if lead in COMMON_LEADS:
            score += 1
            reasons.append("common-lead")
        if b0 in (0x00, 0x0C, 0x01, 0x10, 0x42, 0x40):
            score += 1
            reasons.append("common-b0")

        out.append(
            OpcodeStart(
                offset=i,
                b0=b0,
                b1=b1,
                b2=b2,
                lead=lead,
                mode=mode,
                b7=b7,
                score=score,
                reason=",".join(reasons),
            )
        )
    return out


def build_opcode_frames(data: bytes, starts: list[OpcodeStart]) -> list[OpcodeFrame]:
    strong = [s for s in starts if s.score >= 8]
    strong.sort(key=lambda x: x.offset)
    out: list[OpcodeFrame] = []
    for i, s in enumerate(strong):
        st = int(s.offset)
        en = int(strong[i + 1].offset) if i + 1 < len(strong) else len(data)
        if en <= st:
            continue
        fam = classify_start_family(s)
        out.append(
            OpcodeFrame(
                index=len(out),
                start=st,
                end=en,
                length=en - st,
                start_marker=s,
                family=fam,
            )
        )
    return out


def is_core_start(data: bytes, i: int) -> bool:
    if not (
        i + 7 < len(data)
        and data[i] in (0x00, 0x0C, 0x01, 0x10, 0x42)
        and data[i + 1] == 0x01
        and data[i + 2] in (0x00, 0x01)
        and data[i + 3] == 0x0F
        and data[i + 4] == 0x42
    ):
        return False
    return _mode_next_ok(int(data[i + 6]), int(data[i + 7]))


def find_next_core_start(data: bytes, start: int) -> int:
    i = max(0, start)
    limit = len(data) - 6
    while i < limit:
        if is_core_start(data, i):
            return i
        i += 1
    return -1


def find_first_core_start(data: bytes) -> int:
    first_strict = find_next_core_start(data, 0)
    if first_strict < 0:
        return -1
    i = 0
    while i + 6 < first_strict:
        if (
            data[i] not in (0x00, 0x0C)
            and data[i + 1] == 0x01
            and data[i + 2] in (0x00, 0x01)
            and data[i + 3] == 0x0F
            and data[i + 4] == 0x42
            and data[i + 6] == 0x0F
        ):
            return i
        i += 1
    return first_strict


def build_core_frames_from_stream(data: bytes) -> list[OpcodeFrame]:
    out: list[OpcodeFrame] = []
    s = find_first_core_start(data)
    while s >= 0:
        n = find_next_core_start(data, s + 1)
        e = n if n >= 0 else len(data)
        if e <= s:
            break
        sm = OpcodeStart(
            offset=int(s),
            b0=int(data[s]),
            b1=int(data[s + 1]),
            b2=int(data[s + 2]),
            lead=int(data[s + 5]),
            mode=int(data[s + 6]),
            b7=int(data[s + 7]),
            score=999,
            reason="core-seq",
        )
        out.append(
            OpcodeFrame(
                index=len(out),
                start=int(s),
                end=int(e),
                length=int(e - s),
                start_marker=sm,
                family="core",
            )
        )
        if n < 0:
            break
        s = n
    return out


def build_layer1(data: bytes) -> OpcodeLayer1:
    starts = detect_opcode_starts(data)
    all_strong_frames = build_opcode_frames(data, starts)
    core_frames = build_core_frames_from_stream(data)
    core_offsets = {int(f.start) for f in core_frames}
    ext_frames = [f for f in all_strong_frames if int(f.start) not in core_offsets and str(f.family) == "extension"]
    typed_frames = [f for f in all_strong_frames if int(f.start) not in core_offsets and str(f.family) == "typed"]
    aux_frames = [f for f in all_strong_frames if int(f.start) not in core_offsets and str(f.family) == "aux"]
    var_frames = [f for f in all_strong_frames if int(f.start) not in core_offsets and str(f.family) == "variant"]
    return OpcodeLayer1(
        core_frames=core_frames,
        extension_frames=ext_frames,
        typed_frames=typed_frames,
        aux_frames=aux_frames,
        variant_frames=var_frames,
        all_strong_frames=all_strong_frames,
    )
