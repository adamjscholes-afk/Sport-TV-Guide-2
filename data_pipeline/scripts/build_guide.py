#!/usr/bin/env python3
"""Build a 72-hour sports TV guide from public XMLTV feeds.

The adapters are intentionally small and isolated. A failed source is recorded
and does not erase the previous good guide. This first version ingests the
public Freeview/Rytec XMLTV endpoints; premium/streaming adapters can be added
without changing the output contract.
"""
from __future__ import annotations

import gzip, hashlib, json, os, re, sys, tempfile, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data"
OUT.mkdir(exist_ok=True)

# Public/open XMLTV endpoints. Keep a list so one mirror can fail independently.
SOURCES = {
    "freeview": [
        "https://raw.githubusercontent.com/dp247/Freeview-EPG/master/epg.xml.gz",
    ],
    "rytec": [
        "https://rytec.oe-alliance.com/epglistxml/rytecUK_SportsMovies.xml.gz",
        "https://rytec.oe-alliance.com/epglistxml/rytecUK_Sky.xml.gz",
    ],
}

SPORT_TERMS = {
    "football": ["premier league", "championship", "league one", "league two", "fa cup", "uefa", "europa league", "champions league", "football", "soccer"],
    "rugby": ["rugby", "six nations", "premiership rugby", "rugby championship"],
    "boxing": ["boxing", "fight night", "heavyweight"],
    "ufc": ["ufc", "ultimate fighting championship"],
    "tennis": ["tennis", "atp", "wta", "grand slam", "wimbledon", "us open", "french open", "australian open"],
    "golf": ["golf", "pga", "lpga", "ryder cup", "masters tournament"],
    "cricket": ["cricket", "test match", "t20", "odi", "the hundred"],
    "f1": ["formula 1", "formula one", "f1", "grand prix"],
    "f2": ["formula 2", "f2"],
    "f3": ["formula 3", "f3"],
    "darts": ["darts", "pdc"],
    "snooker": ["snooker", "world snooker"],
    "cycling": ["cycling", "tour de france", "giro d'italia", "vuelta"],
    "motorsport": ["motorsport", "motogp", "nascar", "indycar", "wrc"],
    "nfl": ["nfl", "super bowl"],
    "nba": ["nba", "basketball"],
    "baseball": ["mlb", "baseball"],
    "ice hockey": ["nhl", "ice hockey"],
    "horse racing": ["horse racing", "racing from", "kempton", "ascot", "cheltenham", "aintree", "newmarket"],
    "wrestling": ["wwe", "aew", "wrestling"],
}

# Explicit sports channels are high-confidence sports destinations.
SPORT_CHANNEL_RE = re.compile(r"sky sports|tnt sports|premier sports|bt sport|eurosport|racing tv|sky f1|sky golf", re.I)


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "SportTVGuide/0.1 EPG collector"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def xml_bytes(raw: bytes) -> bytes:
    return gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw


def parse_dt(value: str) -> datetime:
    m = re.match(r"(\d{14})\s*([+-]\d{4})?", value or "")
    if not m:
        raise ValueError(value)
    dt = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    off = m.group(2)
    if off:
        sign = 1 if off[0] == "+" else -1
        minutes = int(off[1:3]) * 60 + int(off[3:5])
        dt = dt.replace(tzinfo=timezone(sign * timedelta(minutes=minutes)))
        return dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=timezone.utc)


def text(el):
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def classify(title: str, desc: str, channel: str):
    hay = f"{title} {desc}".lower()
    scores = {}
    for sport, terms in SPORT_TERMS.items():
        score = sum(1 for term in terms if term in hay)
        if score:
            scores[sport] = score
    if scores:
        sport = max(scores, key=scores.get)
        return sport, min(0.99, 0.65 + 0.1 * scores[sport])
    if SPORT_CHANNEL_RE.search(channel):
        return "other", 0.70
    return None, 0.0


def ingest(source_name, urls, start, end):
    last_error = None
    for url in urls:
        try:
            raw = download(url)
            root = ET.fromstring(xml_bytes(raw))
            channels = {c.attrib.get("id", ""): text(c.find("display-name")) for c in root.findall("channel")}
            programmes = []
            for p in root.findall("programme"):
                try:
                    s, e = parse_dt(p.attrib.get("start", "")), parse_dt(p.attrib.get("stop", ""))
                except Exception:
                    continue
                if e <= start or s >= end:
                    continue
                channel = channels.get(p.attrib.get("channel", ""), p.attrib.get("channel", ""))
                title = text(p.find("title"))
                desc = text(p.find("desc"))
                sport, confidence = classify(title, desc, channel)
                if sport:
                    programmes.append({"channel": channel, "channel_id": p.attrib.get("channel", ""), "title": title, "description": desc, "start": s.isoformat().replace("+00:00", "Z"), "end": e.isoformat().replace("+00:00", "Z"), "sport": sport, "confidence": confidence, "source": source_name})
            if programmes:
                return programmes, {"ok": True, "url": url, "programmes": len(programmes), "sha256": hashlib.sha256(raw).hexdigest()}
            last_error = "feed parsed but contained no sports programmes"
        except Exception as exc:
            last_error = str(exc)
    return [], {"ok": False, "error": last_error or "unknown error"}


def main():
    now = datetime.now(timezone.utc)
    start = now
    end = now + timedelta(hours=72)
    all_events, health = [], {}
    for name, urls in SOURCES.items():
        events, status = ingest(name, urls, start, end)
        health[name] = status
        all_events.extend(events)

    # Deduplicate identical programme broadcasts across sources.
    unique = {}
    for e in all_events:
        key = (e["channel"].lower(), e["title"].lower(), e["start"])
        old = unique.get(key)
        if old is None or e["confidence"] > old["confidence"]:
            unique[key] = e

    events = sorted(unique.values(), key=lambda x: x["start"])
    previous = OUT / "guide.json"
    if not events and previous.exists():
        health["publish"] = {"ok": False, "reason": "no valid events; retained previous guide"}
    else:
        payload = {"generated_at": now.isoformat().replace("+00:00", "Z"), "window_start": start.isoformat().replace("+00:00", "Z"), "window_end": end.isoformat().replace("+00:00", "Z"), "timezone": "UTC", "events": events}
        (OUT / "guide.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        health["publish"] = {"ok": True, "events": len(events)}
    (OUT / "health.json").write_text(json.dumps({"checked_at": now.isoformat().replace("+00:00", "Z"), "sources": health}, indent=2), encoding="utf-8")
    print(json.dumps(health, indent=2))

if __name__ == "__main__":
    main()
