#!/usr/bin/env python3
"""Patch the static UI so fixtures and long channel names are visible."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
path=ROOT/"index.html"
s=path.read_text(encoding="utf-8")
replacements={
    "grid-template-columns:112px 1fr":"grid-template-columns:220px 1fr",
    "<strong>${e.title||'Sport'}</strong>":"<strong>${e.fixture||e.title||'Sport'}</strong>",
    "<div class=\"eventtitle\">${e.title||'Sport'}</div>":"<div class=\"eventtitle\">${e.fixture||e.title||'Sport'}</div>",
}
changed=0
for old,new in replacements.items():
    n=s.count(old)
    if n:
        s=s.replace(old,new); changed+=n
if s.count("grid-template-columns:220px 1fr")<2:
    raise SystemExit("channel column patch did not update both Guide row definitions")
if sum(s.count(x) for x in ["${e.fixture||e.title||'Sport'}"] )<3:
    raise SystemExit("fixture display patch is incomplete")
path.write_text(s,encoding="utf-8")
print(f"UI patch OK: {changed} replacements; channel column 220px; fixture rendering present in Guide/Sports/Tonight")
