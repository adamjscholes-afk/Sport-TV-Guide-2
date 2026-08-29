#!/usr/bin/env python3
import json,re
from collections import Counter
from pathlib import Path
p=Path('data/guide.json'); d=json.loads(p.read_text())
REGIONAL_ITV=re.compile(r'^itv(?:\s*1)?\s+(?:hd\s+)?(?:london|granada|central|anglia|meridian|tyne\s*tees|yorkshire|border|westcountry|west|wales|channel)(?:\s+hd)?$',re.I)
def norm(s):
 s=' '.join(s.split()).strip()
 l=s.lower()
 if re.search(r'\bbbc\s*(?:one|1)\b',l): return 'BBC One'
 if re.match(r'^itv\s*1(?:\s+hd)?$',l) or REGIONAL_ITV.match(s): return 'ITV1'
 if re.match(r'^stv(?:\s+.*)?$',s,re.I): return 'STV'
 if re.match(r'^utv(?:\s+.*)?$',s,re.I): return 'UTV'
 return s
for e in d['events']: e['channel']=norm(e['channel'])
u={}
for e in d['events']:
 k=(e['channel'].lower(),e['title'].strip().lower(),e['start'])
 if k not in u or e.get('confidence',0)>u[k].get('confidence',0): u[k]=e
d['events']=sorted(u.values(),key=lambda e:e['start']); d['channels']=sorted(set(e['channel'] for e in d['events'])); d['channel_count']=len(d['channels']); d['event_count']=len(d['events']); d['sport_counts']=dict(sorted(Counter(e['sport'] for e in d['events']).items()))
p.write_text(json.dumps(d,indent=2)+'\n')
print('normalised channels:',d['channel_count'])
