#!/usr/bin/env python3
"""Backfill fixtures for EPG entries whose sport classifier missed football."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from enrich_fixtures import fetch_tsdb, fetch_fixturedownload, canonical_team, find_teams

ROOT=Path(__file__).resolve().parents[2]
GUIDE=ROOT/"data"/"guide.json"
COMPETITION_RE=re.compile(r"\b(?:EFL|Championship|League One|League Two|Premier League)\b",re.I)
NON_FOOTBALL_RE=re.compile(r"\b(?:cricket|test match|t20|odi|the hundred|golf|tennis|cycling|formula\s*[123]?|motogp|motorsport|wrc|boxing|ufc|rugby|darts|snooker|horse racing|baseball|nfl|nba|basketball|wrestling)\b",re.I)

def is_football_candidate(e):
    text=f"{e.get('title','')} {e.get('description','')}"
    return bool(COMPETITION_RE.search(text)) and not NON_FOOTBALL_RE.search(text)

def main():
    data=json.loads(GUIDE.read_text(encoding="utf-8")); dates={}
    for e in data.get("events",[]):
        if e.get("fixture") or not is_football_candidate(e): continue
        day=datetime.fromisoformat(e["start"].replace("Z","+00:00")).strftime("%Y-%m-%d")
        dates.setdefault(day, None)
    for day in dates:
        fixtures=fetch_tsdb(day)+fetch_fixturedownload(day)
        # Deduplicate fixture sources by canonical teams and kickoff.
        dedup={(canonical_team(f['home']),canonical_team(f['away']),f['start']):f for f in fixtures}
        dates[day]=list(dedup.values())
    enriched=0
    for e in data.get("events",[]):
        if e.get("fixture") or not is_football_candidate(e): continue
        dt=datetime.fromisoformat(e["start"].replace("Z","+00:00")); candidates=[f for f in dates.get(dt.strftime('%Y-%m-%d'),[]) if abs((f['start']-dt).total_seconds())<=90*60]
        mentioned=set(find_teams(f"{e.get('title','')} {e.get('description','')}"))
        if mentioned:
            candidates=[f for f in candidates if len({canonical_team(f['home']),canonical_team(f['away'])}&mentioned)>=1]
        if len(candidates)==1:
            f=candidates[0]; home,away=canonical_team(f['home']),canonical_team(f['away'])
            e['home_team'],e['away_team'],e['fixture']=home,away,f"{home} v {away}"; enriched+=1
    data['fixture_enriched_count']=sum(bool(e.get('fixture')) for e in data.get('events',[]))
    GUIDE.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"Fixture backfill: added {enriched}; total fixture-enriched events {data['fixture_enriched_count']}")

if __name__=="__main__": main()
