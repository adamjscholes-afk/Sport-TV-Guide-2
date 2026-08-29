#!/usr/bin/env python3
import json,re
from collections import Counter
from pathlib import Path

p=Path('data/guide.json')
d=json.loads(p.read_text())

REGIONAL_WORDS = r'(?:london|granada|central|anglia|meridian|tyne(?:\s*tees)?|tees|yorkshire|border|westcountry|west|wales|channel|north|south|scotland|england|east|midlands|ulster|ni|northern\s*ireland)'
ITV_REGIONAL = re.compile(r'^itv\s*(?:1|\+\s*1)?\b.*' + REGIONAL_WORDS, re.I)


def norm(s):
    s=' '.join(s.split()).strip()
    l=s.lower()

    # BBC One regional feeds are one logical channel in this guide.
    if re.search(r'\bbbc\s*(?:one|1)\b', l):
        return 'BBC One'

    # ITV1 and ITV+1 regional feeds are consolidated into their logical
    # national channel.  Keep ITV2/3/4/Be and ITVX as separate services.
    if re.match(r'^itv\s*1(?:\s*\+\s*1)?(?:\s+hd)?$', l) or ITV_REGIONAL.search(l):
        return 'ITV1'

    # STV/UTV regional or technical variants are one logical channel.
    if re.match(r'^stv(?:\b|\s)', l):
        return 'STV'
    if re.match(r'^utv(?:\b|\s)', l):
        return 'UTV'

    return s

for e in d['events']:
    e['channel']=norm(e['channel'])

u={}
for e in d['events']:
    k=(e['channel'].lower(),e['title'].strip().lower(),e['start'])
    if k not in u or e.get('confidence',0)>u[k].get('confidence',0):
        u[k]=e

d['events']=sorted(u.values(),key=lambda e:e['start'])
d['channels']=sorted(set(e['channel'] for e in d['events']))
d['channel_count']=len(d['channels'])
d['event_count']=len(d['events'])
d['sport_counts']=dict(sorted(Counter(e['sport'] for e in d['events']).items()))
p.write_text(json.dumps(d,indent=2)+'\n')
print('normalised channels:',d['channel_count'])
