"""Convert the blind set from inline markup to offset spans.

    python benchmark/blind/convert.py                  # v1
    python benchmark/blind/convert.py v2               # benchmark/blind/blind_v2.source.jsonl

Source lines look like ``"text": "hi its [[NAME|jess]] ..."``. The output has the
markup stripped and character offsets in ``spans``, the same format as v0.

If ``audit_<version>.jsonl`` exists, its corrections from a second annotator
are applied: ``add`` a missing label, ``remove`` a wrong one, ``retype`` one.
Each names the exact surface text and which occurrence of it in the message.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).parent
MARK = re.compile(r"\[\[([A-Z_]+)\|(.*?)\]\]", re.S)


def convert(marked: str) -> tuple[str, list[dict]]:
    out, spans, pos = [], [], 0
    length = 0
    for m in MARK.finditer(marked):
        before = marked[pos : m.start()]
        out.append(before)
        length += len(before)
        surface = m.group(2)
        spans.append({"start": length, "end": length + len(surface), "type": m.group(1)})
        out.append(surface)
        length += len(surface)
        pos = m.end()
    out.append(marked[pos:])
    text = "".join(out)
    if "[[" in text or "]]" in text:
        raise ValueError(f"unbalanced markup in: {marked[:80]!r}")
    return text, spans


def _nth(text: str, surface: str, n: int) -> tuple[int, int]:
    pos = -1
    for _ in range(n):
        pos = text.find(surface, pos + 1)
        if pos < 0:
            raise ValueError(f"occurrence {n} of {surface!r} not found")
    return pos, pos + len(surface)


def apply_audit(rows: list[dict], audit_path: Path) -> dict[str, int]:
    by_id = {r["id"]: r for r in rows}
    counts = {"add": 0, "remove": 0, "retype": 0, "skipped": 0}
    for line in audit_path.read_text().splitlines():
        if not line.strip():
            continue
        a = json.loads(line)
        r = by_id[a["id"]]
        start, end = _nth(r["text"], a["surface"], int(a.get("occurrence", 1)))
        overlapping = [s for s in r["spans"] if s["start"] < end and start < s["end"]]
        if a["action"] == "add":
            if overlapping:
                counts["skipped"] += 1
                continue
            r["spans"].append({"start": start, "end": end, "type": a["type"]})
        elif a["action"] == "remove":
            if not overlapping:
                counts["skipped"] += 1
                continue
            for s_ in overlapping:
                r["spans"].remove(s_)
        elif a["action"] == "retype":
            if not overlapping:
                counts["skipped"] += 1
                continue
            for s_ in overlapping:
                s_["type"] = a["type"]
        counts[a["action"]] += 1
        r["spans"].sort(key=lambda s_: s_["start"])
    return counts


def main() -> None:
    import sys

    version = sys.argv[1] if len(sys.argv) > 1 else "v1"
    src = HERE / f"blind_{version}.source.jsonl"
    out_path = HERE.parent / "data" / f"patient_comms_blind_{version}.jsonl"
    rows = []
    for line in src.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        text, spans = convert(r["text"])
        for s in spans:
            assert text[s["start"] : s["end"]].strip(), r["id"]
        rows.append({"id": r["id"], "channel": r["channel"], "lang": r["lang"], "text": text,
                     "spans": spans, "known": r.get("known") or {}})
    audit = HERE / f"audit_{version}.jsonl"
    if audit.exists():
        print("audit:", apply_audit(rows, audit))
    out_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"wrote {len(rows)} rows, {sum(len(r['spans']) for r in rows)} spans -> {out_path}")


if __name__ == "__main__":
    main()
