#!/usr/bin/env python3
"""Patch the static UI so enriched fixtures are shown to users."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
path = ROOT / "index.html"
s = path.read_text(encoding="utf-8")
replacements = {
    "<strong>${e.title||'Sport'}</strong>": "<strong>${e.fixture||e.title||'Sport'}</strong>",
    "<div class=\"eventtitle\">${e.title||'Sport'}</div>": "<div class=\"eventtitle\">${e.fixture||e.title||'Sport'}</div>",
}
changed = 0
for old, new in replacements.items():
    n = s.count(old)
    if n:
        s = s.replace(old, new)
        changed += n
if changed and changed != 3:
    raise SystemExit(f"fixture UI patch expected 3 replacements, made {changed}")
if changed == 0 and sum(s.count(new) for new in replacements.values()) < 3:
    raise SystemExit("fixture UI patch found neither source nor all 3 target patterns")
path.write_text(s, encoding="utf-8")
print(f"Fixture UI patch OK: {changed} replacements applied")
