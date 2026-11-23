"""Structural checks for the manuscript. No TeX engine required."""
import re
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parent.parent
p = root / "multi_tier_agri_ecological_optimization_framework.tex"
s = p.read_text(encoding="utf-8")
t = re.sub(r"(?m)^%.*$", "", s)

cites = set(re.findall(r"\\cite\{([^}]+)\}", t))
bibs = set(re.findall(r"\\bibitem\{([^}]+)\}", t))
refs = set(re.findall(r"\\(?:ref|eqref)\{([^}]+)\}", t))
labels = set(re.findall(r"\\label\{([^}]+)\}", t))
b = Counter(re.findall(r"\\begin\{([^}]+)\}", t))
e = Counter(re.findall(r"\\end\{([^}]+)\}", t))
imgs = re.findall(r"\\includegraphics\[[^\]]*\]\{([^}]+)\}", t)

print(f"cites/bibs: {len(cites)}/{len(bibs)}  orphans: {sorted(cites ^ bibs)}")
print(f"refs/labels: {len(refs)}/{len(labels)}  missing: {sorted(refs - labels)}  unused: {sorted(labels - refs)}")
print(f"brace balance: {s.count('{') - s.count('}')}")
print(f"env mismatch: {dict((k, (b[k], e[k])) for k in set(b) | set(e) if b[k] != e[k])}")
print(f"non-ascii chars: {sorted(set(ch for ch in s if ord(ch) > 127))}")
print(f"figures referenced: {imgs}")
available = {x.name for x in (root / "figures").glob("*.png")}
missing = [f for f in imgs if f.replace("\\_", "_").split("/")[-1] not in available]
print(f"missing figure files: {missing}")

inputs = re.findall(r"\\input\{([^}]+)\}", s)
missing_inputs = [f for f in inputs if not (root / f).is_file()]
print(f"generated tables referenced: {inputs}  missing: {missing_inputs}")
included = "\n".join((root / f).read_text(encoding="utf-8") for f in inputs if (root / f).is_file())
refs |= set(re.findall(r"\\(?:ref|eqref)\{([^}]+)\}", included))
labels |= set(re.findall(r"\\label\{([^}]+)\}", included))
print(f"refs/labels including generated tables: {len(refs)}/{len(labels)}  missing: {sorted(refs - labels)}")

stale = ["four policies", "32.3", "29.5", "all 80 per-seed records", "status-quo comparator used in earlier drafts"]
found = [x for x in stale if x in s]
print(f"stale manuscript text: {found}")

assert not (cites ^ bibs) and not (refs - labels)
assert s.count("{") == s.count("}") and b == e
assert not missing and not missing_inputs and not found
