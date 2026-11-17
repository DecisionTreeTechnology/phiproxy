"""Score PHI detection on a labelled JSONL set.

    python benchmark/score.py                      # default set, all available configs
    python benchmark/score.py --data path.jsonl --config regex+known

A labelled span counts as caught when detected spans cover at least 80% of
its characters (any type: catching a phone as an ID still protects it).
Scoring uses the default policy, so clinician names (PROVIDER) pass through:
PROVIDER labels are not counted in recall, and masking one counts as a false
positive. A detected span counts as correct when it overlaps a labelled
identifier. "Clean messages masked" is the share of messages with no
identifiers in which something was masked anyway.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from phiproxy import KnownEntities, Masker, Policy, RegexDetector

DEFAULT_DATA = Path(__file__).parent / "data" / "patient_comms_v0.jsonl"
COVER = 0.8


def configs() -> dict:
    out = {
        "regex": (lambda: [RegexDetector()], False),
        "regex+known": (lambda: [RegexDetector()], True),
    }
    try:
        from phiproxy.detectors.presidio import PresidioDetector

        PresidioDetector()  # needs presidio + a spaCy model
        out["regex+known+presidio"] = (lambda: [RegexDetector(), PresidioDetector()], True)
    except Exception:
        pass
    try:
        from phiproxy.detectors.gliner import GlinerDetector

        g = GlinerDetector()  # needs phiproxy[gliner] and the model download
        out["regex+gliner"] = (lambda: [RegexDetector(), g], False)
        out["regex+known+gliner"] = (lambda: [RegexDetector(), g], True)
    except Exception:
        pass
    return out


def score(rows: list[dict], detectors, use_known: bool, allow: tuple[str, ...] = ()) -> dict:
    m = Masker(detectors=detectors, policy=Policy(allow=allow))  # clinician names pass
    by_type = defaultdict(lambda: [0, 0])  # type -> [caught, total]
    by_channel = defaultdict(lambda: [0, 0])
    by_lang = defaultdict(lambda: [0, 0])
    clean = clean_masked = 0
    tp = fp = 0
    leaked_chars = total_chars = 0
    misses = []
    fps = []
    for r in rows:
        known = KnownEntities.from_dict(r["known"]) if use_known else None
        found = m.detect(r["text"], known)
        covered = set()
        for e in found:
            covered.update(range(e.start, e.end))
        spans = [s for s in r["spans"] if s["type"] != "PROVIDER"]
        if not spans:
            clean += 1
            clean_masked += bool(found)
        for s in spans:
            chars = set(range(s["start"], s["end"]))
            hit = len(chars & covered) / len(chars) >= COVER
            by_type[s["type"]][0] += hit
            by_type[s["type"]][1] += 1
            by_channel[r["channel"]][0] += hit
            by_channel[r["channel"]][1] += 1
            by_lang[r.get("lang", "en")][0] += hit
            by_lang[r.get("lang", "en")][1] += 1
            leaked_chars += len(chars - covered)
            total_chars += len(chars)
            if not hit:
                misses.append((r["id"], s["type"], r["text"][s["start"] : s["end"]]))
        gold = [set(range(s["start"], s["end"])) for s in spans]
        for e in found:
            span = set(range(e.start, e.end))
            if any(span & g for g in gold):
                tp += 1
            else:
                fp += 1
                fps.append((r["id"], e.type.value, e.source, e.text))
    caught = sum(v[0] for v in by_type.values())
    total = sum(v[1] for v in by_type.values())
    return {
        "recall": caught / total if total else 1.0,
        "precision": tp / (tp + fp) if tp + fp else 1.0,
        "spans": total,
        "missed": total - caught,
        "leaked_char_rate": leaked_chars / total_chars if total_chars else 0.0,
        "by_type": {k: v[0] / v[1] for k, v in sorted(by_type.items())},
        "by_channel": {k: v[0] / v[1] for k, v in sorted(by_channel.items())},
        "by_lang": {k: v[0] / v[1] for k, v in sorted(by_lang.items())},
        "clean_messages": clean,
        "clean_masked_rate": clean_masked / clean if clean else 0.0,
        "false_positives": fp,
        "misses": misses,
        "fps": fps,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--config", default=None)
    ap.add_argument("--show-misses", type=int, default=0, help="print N missed spans per config")
    ap.add_argument("--allow", type=Path, default=None,
                    help="JSON list of the clinic's own details to pass unmasked (Policy.allow)")
    ap.add_argument("--show-false-positives", type=int, default=0,
                    help="print N falsely masked spans per config")
    ap.add_argument("--json", type=Path, default=None, help="write results here")
    ap.add_argument("--min-recall", type=float, default=None,
                    help="exit non-zero if any config's recall is below this (for CI)")
    a = ap.parse_args()
    rows = [json.loads(line) for line in a.data.read_text().splitlines() if line.strip()]
    cfgs = configs()
    if a.config:
        cfgs = {a.config: cfgs[a.config]}
    results = {}
    for name, (make, use_known) in cfgs.items():
        allow = tuple(json.loads(a.allow.read_text())) if a.allow else ()
        results[name] = score(rows, make(), use_known, allow)

    types = sorted({t for r in results.values() for t in r["by_type"]})
    channels = sorted({c for r in results.values() for c in r["by_channel"]})
    print(f"\n{a.data.name}: {len(rows)} messages, {next(iter(results.values()))['spans']} labelled spans\n")
    print("| config | recall | precision | missed | false positives | clean messages masked |")
    print("|---|---|---|---|---|---|")
    for n, r in results.items():
        print(f"| {n} | {r['recall']:.1%} | {r['precision']:.1%} | {r['missed']} | {r['false_positives']} "
              f"| {r['clean_masked_rate']:.0%} of {r['clean_messages']} |")
    print("\n| recall by type | " + " | ".join(results) + " |")
    print("|---|" + "---|" * len(results))
    for t in types:
        print(f"| {t} | " + " | ".join(f"{r['by_type'].get(t, 0):.0%}" for r in results.values()) + " |")
    print("\n| recall by channel | " + " | ".join(results) + " |")
    print("|---|" + "---|" * len(results))
    for c in channels:
        print(f"| {c} | " + " | ".join(f"{r['by_channel'].get(c, 0):.0%}" for r in results.values()) + " |")
    langs = sorted({g for r in results.values() for g in r["by_lang"]})
    if len(langs) > 1:
        print("\n| recall by language | " + " | ".join(results) + " |")
        print("|---|" + "---|" * len(results))
        for g in langs:
            print(f"| {g} | " + " | ".join(f"{r['by_lang'].get(g, 0):.0%}" for r in results.values()) + " |")
    if a.show_misses:
        for n, r in results.items():
            print(f"\nmisses ({n}):")
            for mid, t, txt in r["misses"][: a.show_misses]:
                print(f"  {mid:<12} {t:<12} {txt!r}")
    if a.show_false_positives:
        for n, r in results.items():
            print(f"\nfalse positives ({n}):")
            for fid, t, src, txt in r["fps"][: a.show_false_positives]:
                print(f"  {fid:<16} {t:<12} {src:<7} {txt!r}")
    if a.json:
        a.json.write_text(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("misses", "fps")}
                                      for k, v in results.items()}, indent=2) + "\n")
    if a.min_recall is not None:
        low = {n: r["recall"] for n, r in results.items() if r["recall"] < a.min_recall}
        if low:
            raise SystemExit(f"recall below {a.min_recall:.0%}: {low}")


if __name__ == "__main__":
    main()
