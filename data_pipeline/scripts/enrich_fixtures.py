#!/usr/bin/env python3
"""Enrich EPG events with structured team/fixture information."""
from __future__ import annotations
import json, re, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "data" / "guide.json"

TEAMS = {
    "AFC Wimbledon": ["AFC Wimbledon", "Wimbledon"], "Birmingham City": ["Birmingham", "Birmingham City"],
    "Blackburn Rovers": ["Blackburn", "Blackburn Rovers"], "Bolton Wanderers": ["Bolton", "Bolton Wanderers"],
    "Bristol City": ["Bristol City"], "Burnley": ["Burnley"], "Cardiff City": ["Cardiff", "Cardiff City"],
    "Charlton Athletic": ["Charlton", "Charlton Athletic"], "Coventry City": ["Coventry", "Coventry City"],
    "Derby County": ["Derby", "Derby County"], "Hull City": ["Hull", "Hull City"], "Ipswich Town": ["Ipswich", "Ipswich Town"],
    "Leicester City": ["Leicester", "Leicester City"], "Lincoln City": ["Lincoln", "Lincoln City"], "Millwall": ["Millwall"],
    "Middlesbrough": ["Middlesbrough"], "Norwich City": ["Norwich", "Norwich City"], "Oxford United": ["Oxford", "Oxford United"],
    "Portsmouth": ["Portsmouth"], "Preston North End": ["Preston", "Preston North End"],
    "Queens Park Rangers": ["QPR", "Queens Park Rangers"], "Reading": ["Reading"], "Sheffield United": ["Sheffield United"],
    "Sheffield Wednesday": ["Sheffield Wednesday"], "Southampton": ["Southampton"], "Stoke City": ["Stoke", "Stoke City"],
    "Swansea City": ["Swansea", "Swansea City"], "Watford": ["Watford"], "West Bromwich Albion": ["West Brom", "West Bromwich Albion"],
    "Wrexham": ["Wrexham"], "Wolverhampton Wanderers": ["Wolves", "Wolverhampton", "Wolverhampton Wanderers"],
    "Arsenal": ["Arsenal"], "Aston Villa": ["Aston Villa"], "Bournemouth": ["Bournemouth"], "Brentford": ["Brentford"],
    "Brighton & Hove Albion": ["Brighton", "Brighton & Hove Albion"], "Chelsea": ["Chelsea"], "Crystal Palace": ["Crystal Palace"],
    "Everton": ["Everton"], "Fulham": ["Fulham"], "Leeds United": ["Leeds", "Leeds United"], "Liverpool": ["Liverpool"],
    "Manchester City": ["Man City", "Manchester City"], "Manchester United": ["Man Utd", "Manchester United"],
    "Newcastle United": ["Newcastle", "Newcastle United"], "Nottingham Forest": ["Nottingham Forest", "Nottm Forest"],
    "Sunderland": ["Sunderland"], "Tottenham Hotspur": ["Spurs", "Tottenham", "Tottenham Hotspur"],
}
SEPARATOR_RE = re.compile(r"\s+(?:v|vs\.?|versus)\s+|\s+[-–—]\s+", re.I)
VENUES = {"molineux": "Wolverhampton Wanderers", "pride park": "Derby County", "riverside stadium": "Middlesbrough"}
LEAGUES = {"eng.1": "Premier League", "eng.2": "Championship", "eng.3": "League One", "eng.4": "League Two"}

def find_teams(text: str) -> list[str]:
    low = text.lower(); found=[]
    for canonical, aliases in TEAMS.items():
        if any(re.search(r"(?<![a-z0-9])"+re.escape(a.lower())+r"(?![a-z0-9])", low) for a in aliases): found.append(canonical)
    return found

def explicit_fixture(title: str, description: str):
    for part in (title, description):
        pieces = SEPARATOR_RE.split(part or "", maxsplit=1)
        if len(pieces)==2:
            a,b=find_teams(pieces[0]),find_teams(pieces[1])
            if len(a)==1 and len(b)==1 and a[0]!=b[0]: return a[0],b[0]
    return None

def fetch_fixtures(date_str: str):
    date_key=date_str.replace('-',''); out=[]
    for league in LEAGUES:
        url=f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={urllib.parse.quote(date_key)}"
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"SportTVGuide/0.5"})
            with urllib.request.urlopen(req,timeout=20) as r: payload=json.load(r)
            for ev in payload.get("events",[]):
                comp=(ev.get("competitions") or [{}])[0]; teams={}
                for c in comp.get("competitors",[]):
                    name=(c.get("team") or {}).get("displayName")
                    if name: teams["home" if c.get("homeAway")=="home" else "away"]=name
                if not teams.get("home") or not teams.get("away"): continue
                start=ev.get("date")
                if not start: continue
                venue=((comp.get("venue") or {}).get("fullName") or "")
                out.append({"home":teams["home"],"away":teams["away"],"start":datetime.fromisoformat(start.replace('Z','+00:00')).astimezone(timezone.utc),"venue":venue,"league":LEAGUES[league]})
        except Exception as exc:
            print(f"fixture source warning {league}: {exc}")
    return out

def canonical_team(name: str):
    low=name.lower()
    for canonical, aliases in TEAMS.items():
        if low==canonical.lower() or low in [a.lower() for a in aliases]: return canonical
    return name

def main():
    data=json.loads(GUIDE.read_text(encoding="utf-8")); cache={}; enriched=0; ambiguous=0
    for event in data.get("events",[]):
        title=event.get("title",""); desc=event.get("description",""); text=f"{title} {desc}"; sport=event.get("sport","").lower()
        pair=explicit_fixture(title,desc)
        if pair:
            home,away=pair
        elif sport=="football":
            dt=datetime.fromisoformat(event["start"].replace('Z','+00:00')); key=dt.strftime('%Y-%m-%d')
            if key not in cache: cache[key]=fetch_fixtures(key)
            candidates=[f for f in cache[key] if abs((f["start"]-dt).total_seconds())<=35*60]
            mentioned=set(find_teams(text))
            candidates=[f for f in candidates if len({canonical_team(f['home']),canonical_team(f['away'])}&mentioned)>=2]
            if not candidates:
                venue_team=next((team for venue,team in VENUES.items() if venue in text.lower()),None)
                if venue_team: candidates=[f for f in cache[key] if abs((f["start"]-dt).total_seconds())<=35*60 and canonical_team(f['home'])==venue_team]
            if len(candidates)==1:
                home,away=canonical_team(candidates[0]["home"]),canonical_team(candidates[0]["away"])
            else:
                if len(candidates)>1: ambiguous+=1
                continue
        else:
            continue
        if home!=away:
            event["home_team"]=home; event["away_team"]=away; event["fixture"]=f"{home} v {away}"; enriched+=1
    data["fixture_enriched_count"]=enriched; data["fixture_ambiguous_count"]=ambiguous
    GUIDE.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"Fixture enrichment: {enriched}/{len(data.get('events',[]))} events identified; {ambiguous} ambiguous football listings left unguessed")

if __name__=="__main__": main()
