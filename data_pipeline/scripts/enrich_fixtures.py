#!/usr/bin/env python3
"""Enrich EPG events with structured team/fixture information when the listing identifies it."""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "data" / "guide.json"

# Common EPG abbreviations/variants. Long names are preferred in output.
TEAMS = {
    "AFC Wimbledon": ["AFC Wimbledon", "Wimbledon"],
    "Birmingham City": ["Birmingham", "Birmingham City"],
    "Blackburn Rovers": ["Blackburn", "Blackburn Rovers"],
    "Bolton Wanderers": ["Bolton", "Bolton Wanderers"],
    "Bristol City": ["Bristol City"],
    "Burnley": ["Burnley"],
    "Cardiff City": ["Cardiff", "Cardiff City"],
    "Charlton Athletic": ["Charlton", "Charlton Athletic"],
    "Coventry City": ["Coventry", "Coventry City"],
    "Derby County": ["Derby", "Derby County"],
    "Hull City": ["Hull", "Hull City"],
    "Ipswich Town": ["Ipswich", "Ipswich Town"],
    "Leicester City": ["Leicester", "Leicester City"],
    "Lincoln City": ["Lincoln", "Lincoln City"],
    "Millwall": ["Millwall"],
    "Middlesbrough": ["Middlesbrough"],
    "Norwich City": ["Norwich", "Norwich City"],
    "Oxford United": ["Oxford", "Oxford United"],
    "Portsmouth": ["Portsmouth"],
    "Preston North End": ["Preston", "Preston North End"],
    "Queens Park Rangers": ["QPR", "Queens Park Rangers"],
    "Reading": ["Reading"],
    "Sheffield United": ["Sheffield United"],
    "Sheffield Wednesday": ["Sheffield Wednesday"],
    "Southampton": ["Southampton"],
    "Stoke City": ["Stoke", "Stoke City"],
    "Swansea City": ["Swansea", "Swansea City"],
    "Watford": ["Watford"],
    "West Bromwich Albion": ["West Brom", "West Bromwich Albion"],
    "Wrexham": ["Wrexham"],
    "Wolverhampton Wanderers": ["Wolves", "Wolverhampton", "Wolverhampton Wanderers"],
    "Arsenal": ["Arsenal"], "Aston Villa": ["Aston Villa"], "Bournemouth": ["Bournemouth"],
    "Brentford": ["Brentford"], "Brighton & Hove Albion": ["Brighton", "Brighton & Hove Albion"],
    "Chelsea": ["Chelsea"], "Crystal Palace": ["Crystal Palace"], "Everton": ["Everton"],
    "Fulham": ["Fulham"], "Leeds United": ["Leeds", "Leeds United"], "Liverpool": ["Liverpool"],
    "Manchester City": ["Man City", "Manchester City"], "Manchester United": ["Man Utd", "Manchester United"],
    "Newcastle United": ["Newcastle", "Newcastle United"], "Nottingham Forest": ["Nottingham Forest", "Nottm Forest"],
    "Sunderland": ["Sunderland"], "Tottenham Hotspur": ["Spurs", "Tottenham", "Tottenham Hotspur"],
}

# Match explicit fixture syntax used by TV listings: "Team v Team", "Team vs Team", "Team - Team".
SEPARATOR_RE = re.compile(r"\s+(?:v|vs\.?|versus)\s+|\s+[-–—]\s+", re.I)

def find_teams(text: str) -> list[str]:
    found = []
    low = text.lower()
    for canonical, aliases in TEAMS.items():
        for alias in aliases:
            if re.search(r"(?<![a-z0-9])" + re.escape(alias.lower()) + r"(?![a-z0-9])", low):
                found.append(canonical)
                break
    return found

def extract_fixture(title: str, description: str) -> tuple[str | None, str | None, str | None]:
    combined = " ".join(x for x in (title, description) if x)
    # Prefer a direct v/vs fixture because it establishes home/away order.
    for part in (title, description):
        if not part:
            continue
        pieces = SEPARATOR_RE.split(part, maxsplit=1)
        if len(pieces) == 2:
            left, right = pieces
            lt = find_teams(left)
            rt = find_teams(right)
            if len(lt) == 1 and len(rt) == 1 and lt[0] != rt[0]:
                return lt[0], rt[0], f"{lt[0]} v {rt[0]}"
    teams = find_teams(combined)
    if len(teams) == 2 and teams[0] != teams[1]:
        return teams[0], teams[1], f"{teams[0]} v {teams[1]}"
    return None, None, None

def main() -> None:
    data = json.loads(GUIDE.read_text(encoding="utf-8"))
    enriched = 0
    for event in data.get("events", []):
        home, away, fixture = extract_fixture(event.get("title", ""), event.get("description", ""))
        if home and away:
            event["home_team"] = home
            event["away_team"] = away
            event["fixture"] = fixture
            enriched += 1
    data["fixture_enriched_count"] = enriched
    GUIDE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Fixture enrichment: {enriched}/{len(data.get('events', []))} events identified with home/away teams")

if __name__ == "__main__":
    main()
