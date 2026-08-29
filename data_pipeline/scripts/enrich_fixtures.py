#!/usr/bin/env python3
"""Enrich EPG events with structured team/fixture information."""
from __future__ import annotations
import json, re, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "data" / "guide.json"
TEAMS = {
    "AFC Wimbledon":["AFC Wimbledon","Wimbledon"],"Birmingham City":["Birmingham","Birmingham City"],"Blackburn Rovers":["Blackburn","Blackburn Rovers"],"Bolton Wanderers":["Bolton","Bolton Wanderers"],"Bristol City":["Bristol City"],"Burnley":["Burnley"],"Cardiff City":["Cardiff","Cardiff City"],"Charlton Athletic":["Charlton","Charlton Athletic"],"Coventry City":["Coventry","Coventry City"],"Derby County":["Derby","Derby County"],"Hull City":["Hull","Hull City"],"Ipswich Town":["Ipswich","Ipswich Town"],"Leicester City":["Leicester","Leicester City"],"Lincoln City":["Lincoln","Lincoln City"],"Millwall":["Millwall","Millwall FC"],"Middlesbrough":["Middlesbrough"],"Norwich City":["Norwich","Norwich City"],"Oxford United":["Oxford","Oxford United"],"Portsmouth":["Portsmouth","Portsmouth FC"],"Preston North End":["Preston","Preston North End"],"Queens Park Rangers":["QPR","Queens Park Rangers"],"Reading":["Reading"],"Sheffield United":["Sheffield United"],"Sheffield Wednesday":["Sheffield Wednesday"],"Southampton":["Southampton"],"Stoke City":["Stoke","Stoke City"],"Swansea City":["Swansea","Swansea City"],"Watford":["Watford","Watford FC"],"West Bromwich Albion":["West Brom","West Bromwich Albion"],"Wrexham":["Wrexham","Wrexham AFC"],"Wolverhampton Wanderers":["Wolves","Wolverhampton","Wolverhampton Wanderers"],"Arsenal":["Arsenal"],"Aston Villa":["Aston Villa"],"Bournemouth":["Bournemouth"],"Brentford":["Brentford"],"Brighton & Hove Albion":["Brighton","Brighton & Hove Albion"],"Chelsea":["Chelsea"],"Crystal Palace":["Crystal Palace"],"Everton":["Everton"],"Fulham":["Fulham"],"Leeds United":["Leeds","Leeds United"],"Liverpool":["Liverpool"],"Manchester City":["Man City","Manchester City"],"Manchester United":["Man Utd","Manchester United"],"Newcastle United":["Newcastle","Newcastle United"],"Nottingham Forest":["Nottingham Forest","Nottm Forest"],"Sunderland":["Sunderland"],"Tottenham Hotspur":["Spurs","Tottenham","Tottenham Hotspur"]
}
SEPARATOR_RE=re.compile(r"\s+(?:v|vs\.?|versus)\s+|\s+[-–—]\s+",re.I)
VENUES={"molineux":"Wolverhampton Wanderers","pride park":"Derby County","riverside stadium":"Middlesbrough","toughsheet community stadium":"Bolton Wanderers","ashton gate":"Bristol City","cardiff city stadium":"Cardiff City","carrow road":"Norwich City","st mary's":"Southampton","vicarage road":"Watford","the valley":"Charlton Athletic","ewood park":"Blackburn Rovers"}
LEAGUES={"eng.1":"Premier League","eng.2":"Championship","eng.3":"League One","eng.4":"League Two"}
TSDB_LEAGUES={"Premier League":4328,"Championship":4329}
FIXTURE_DOWNLOAD_URLS={"Championship":"https://fixturedownload.com/view/json/championship-2026"}

def find_teams(text):
    low=text.lower(); found=[]
    for canonical,aliases in TEAMS.items():
        if any(re.search(r"(?<![a-z0-9])"+re.escape(a.lower())+r"(?![a-z0-9])",low) for a in aliases): found.append(canonical)
    return found

def explicit_fixture(title,description):
    for part in (title,description):
        pieces=SEPARATOR_RE.split(part or "",maxsplit=1)
        if len(pieces)==2:
            a,b=find_teams(pieces[0]),find_teams(pieces[1])
            if len(a)==1 and len(b)==1 and a[0]!=b[0]: return a[0],b[0]
    return None

def parse_tsdb_time(ev):
    stamp=ev.get("strTimestamp")
    if stamp:
        try:return datetime.fromisoformat(stamp.replace("Z","+00:00")).astimezone(timezone.utc)
        except Exception:pass
    date=ev.get("dateEvent"); tm=ev.get("strTime")
    if date and tm:
        try:return datetime.fromisoformat(f"{date}T{tm[:8]}+00:00")
        except Exception:pass
    return None

def fetch_tsdb(date_str):
    out=[]
    for league_name,league_id in TSDB_LEAGUES.items():
        url=f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={date_str}&l={league_id}"
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"SportTVGuide/0.7"})
            with urllib.request.urlopen(req,timeout=20) as r: payload=json.load(r)
            for ev in payload.get("events") or []:
                home=ev.get("strHomeTeam"); away=ev.get("strAwayTeam"); start=parse_tsdb_time(ev)
                if home and away and start: out.append({"home":home,"away":away,"start":start,"venue":ev.get("strVenue","") or "","league":league_name})
        except Exception as exc: print(f"fixture source warning TheSportsDB {league_name}: {exc}")
    return out

def fetch_fixturedownload(date_str):
    out=[]
    for league_name,url in (("Championship",FIXTURE_DOWNLOAD_URLS["Championship"]),):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"SportTVGuide/0.7"})
            with urllib.request.urlopen(req,timeout=20) as r: payload=json.load(r)
            for ev in payload:
                if not ev.get("DateUtc","").startswith(date_str): continue
                home=ev.get("HomeTeam"); away=ev.get("AwayTeam")
                if not home or not away: continue
                start=datetime.fromisoformat(ev["DateUtc"].replace("Z","+00:00")).astimezone(timezone.utc)
                out.append({"home":home,"away":away,"start":start,"venue":ev.get("Location","") or "","league":league_name})
        except Exception as exc: print(f"fixture source warning FixtureDownload {league_name}: {exc}")
    return out

def fetch_fixtures(date_str):
    date_key=date_str.replace('-',''); out=[]; espn_ok=False
    for league in LEAGUES:
        url=f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={urllib.parse.quote(date_key)}"
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"SportTVGuide/0.7"})
            with urllib.request.urlopen(req,timeout=20) as r: payload=json.load(r)
            espn_ok=True
            for ev in payload.get("events",[]):
                comp=(ev.get("competitions") or [{}])[0]; teams={}
                for c in comp.get("competitors",[]):
                    name=(c.get("team") or {}).get("displayName")
                    if name: teams["home" if c.get("homeAway")=="home" else "away"]=name
                start=ev.get("date")
                if teams.get("home") and teams.get("away") and start:
                    out.append({"home":teams["home"],"away":teams["away"],"start":datetime.fromisoformat(start.replace('Z','+00:00')).astimezone(timezone.utc),"venue":((comp.get("venue") or {}).get("fullName") or ""),"league":LEAGUES[league]})
        except Exception as exc: print(f"fixture source warning {league}: {exc}")
    if not espn_ok:
        out.extend(fetch_tsdb(date_str))
        out.extend(fetch_fixturedownload(date_str))
    dedup={}
    for f in out:
        key=(canonical_team(f["home"]),canonical_team(f["away"]),f["start"])
        dedup[key]=f
    return list(dedup.values())

def canonical_team(name):
    low=name.lower()
    for canonical,aliases in TEAMS.items():
        if low==canonical.lower() or low in [a.lower() for a in aliases]: return canonical
    return name

def channel_family(channel):
    low=channel.lower().replace(" ","")
    if "skysp+" in low or "skysports+" in low or "skysparena" in low: return "skyplus"
    if "skyspfball" in low or "skysportsfootball" in low: return "skyfootball"
    if low.startswith("itv") or low.startswith("utv") or low.startswith("stv"): return "itv"
    if "cbs sports network" in low: return "cbs"
    return re.sub(r"\d+|-|hd|uhd", "", low)

def fixture_key(home,away): return (canonical_team(home),canonical_team(away))

def choose_candidate(candidates, mentioned, venue_text=""):
    if mentioned:
        matched=[f for f in candidates if len({canonical_team(f['home']),canonical_team(f['away'])}&mentioned)>=2]
        if len(matched)==1: return matched[0]
        one=[f for f in candidates if len({canonical_team(f['home']),canonical_team(f['away'])}&mentioned)==1]
        if len(one)==1: return one[0]
    low=venue_text.lower()
    for venue,team in VENUES.items():
        if venue in low:
            matched=[f for f in candidates if canonical_team(f['home'])==team or canonical_team(f['away'])==team]
            if len(matched)==1:return matched[0]
    return None

def main():
    data=json.loads(GUIDE.read_text(encoding="utf-8")); cache={}; enriched=0; ambiguous=0
    unresolved=[]
    for event in data.get("events",[]):
        title=event.get("title",""); desc=event.get("description",""); text=f"{title} {desc}"; sport=event.get("sport","").lower()
        pair=explicit_fixture(title,desc)
        if pair:
            event["home_team"],event["away_team"]=pair; event["fixture"]=f"{pair[0]} v {pair[1]}"; enriched+=1; continue
        if sport!="football": continue
        dt=datetime.fromisoformat(event["start"].replace('Z','+00:00')); key=dt.strftime('%Y-%m-%d')
        if key not in cache: cache[key]=fetch_fixtures(key)
        candidates=[f for f in cache[key] if abs((f["start"]-dt).total_seconds())<=35*60]
        mentioned=set(find_teams(text))
        chosen=choose_candidate(candidates,mentioned,text)
        if chosen:
            home,away=canonical_team(chosen["home"]),canonical_team(chosen["away"])
            event["home_team"]=home; event["away_team"]=away; event["fixture"]=f"{home} v {away}"; enriched+=1
        else:
            unresolved.append((event,candidates,dt))

    # Second pass: use the EPG itself as a broadcast cross-check. Detailed channel
    # variants often identify the match while the generic channel listing does not.
    slot_fixtures={}
    family_fixtures={}
    for event,candidates,dt in unresolved + [(e,cache.get(datetime.fromisoformat(e['start'].replace('Z','+00:00')).strftime('%Y-%m-%d'),[]),datetime.fromisoformat(e['start'].replace('Z','+00:00'))) for e in data.get('events',[]) if e.get('fixture')]:
        if not event.get('fixture'): continue
        slot=event["start"][:16]
        fk=fixture_key(event["home_team"],event["away_team"])
        slot_fixtures.setdefault(slot,set()).add(fk)
        family_fixtures.setdefault((slot,channel_family(event.get("channel", ""))),set()).add(fk)

    still_ambiguous=0
    for event,candidates,dt in unresolved:
        if event.get("fixture"): continue
        slot=event["start"][:16]; family=channel_family(event.get("channel",""))
        known_family=family_fixtures.get((slot,family),set())
        available=[]
        for f in candidates:
            fk=fixture_key(f["home"],f["away"])
            if fk not in known_family: available.append(f)
        # If exactly one fixture remains after accounting for already identified
        # broadcasts in the same channel family/slot, it is a safe deduction.
        if len(available)==1:
            f=available[0]; home,away=canonical_team(f["home"]),canonical_team(f["away"])
            event["home_team"]=home; event["away_team"]=away; event["fixture"]=f"{home} v {away}"; enriched+=1
        else:
            still_ambiguous+=1

    ambiguous=still_ambiguous
    data["fixture_enriched_count"]=enriched; data["fixture_ambiguous_count"]=ambiguous
    GUIDE.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"Fixture enrichment: {enriched}/{len(data.get('events',[]))} events identified; {ambiguous} ambiguous football listings left unguessed")

if __name__=="__main__": main()
