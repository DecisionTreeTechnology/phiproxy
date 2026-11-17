"""Build src/phiproxy/data/places_ca_us.tsv from GeoNames.

    curl -O https://download.geonames.org/export/dump/cities15000.zip && unzip cities15000.zip
    pip install wordfreq
    python scripts/build_places.py cities15000.txt [/usr/share/dict/words]

Keeps Canadian and US places with more than 15,000 people (name and ASCII name).
A place whose every word is also a common lowercase English word ("Normal",
"Mobile", "Back Bay") is marked ambiguous: it is matched only when written with
a capital letter. "Common" means listed in lowercase in the system dictionary
and frequent in English text (wordfreq Zipf >= 3.8), so "kitchener" (a stove,
but rare) is not ambiguous.

GeoNames data is licensed CC BY 4.0 (https://www.geonames.org/), see NOTICE.
"""

from __future__ import annotations

import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src" / "phiproxy" / "data" / "places_ca_us.tsv"


def main() -> None:
    src = Path(sys.argv[1])
    words_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/usr/share/dict/words")
    from wordfreq import zipf_frequency

    dictionary = {w.strip() for w in words_path.read_text().splitlines() if w.strip().islower()}

    def common(word: str) -> bool:
        return word in dictionary and zipf_frequency(word, "en") >= 3.8

    names: dict[str, str] = {}
    for line in src.read_text(encoding="utf-8").splitlines():
        f = line.split("\t")
        if f[8] not in ("CA", "US"):
            continue
        for n in {f[1], f[2]}:
            n = n.strip()
            if len(n) < 3:
                continue
            key = n.lower()
            if key not in names:
                names[key] = n
    rows = []
    for key, n in sorted(names.items()):
        ambiguous = all(common(w) for w in key.replace("-", " ").split())
        rows.append(f"{n}\t{'1' if ambiguous else '0'}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("# GeoNames cities15000, CA+US, CC BY 4.0. name<TAB>ambiguous\n" + "\n".join(rows) + "\n",
                   encoding="utf-8")
    print(f"{len(rows)} names, {sum(r.endswith('1') for r in rows)} ambiguous -> {OUT}")


if __name__ == "__main__":
    main()
