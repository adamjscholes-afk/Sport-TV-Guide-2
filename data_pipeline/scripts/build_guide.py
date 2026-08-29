#!/usr/bin/env python3
"""Build a rolling 72-hour sports EPG from public XMLTV feeds."""
from __future__ import annotations
import gzip, hashlib, json, lzma, re, urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/"data"; OUT.mkdir(exist_ok=True)
SOURCES={"freeview":["https://raw.githubusercontent.com/dp247/Freeview-EPG/master/epg.xml"],"curated_uk":["https://raw.githubusercontent.com/farleyflex/epg-guide/main/epg.xml"],"rytec_uk_basic":["http://www.xmltvepg.nl/rytecUK_Basic.xz","http://rytecepg.wanwizard.eu/rytecUK_Basic.xz","http://epg.vuplus-community.net/rytecUK_Basic.xz"],"rytec_uk_sky":["http://www.xmltvepg.nl/rytecUK_SkyLive.xz","http://rytecepg.wanwizard.eu/rytecUK_SkyLive.xz","http://epg.vuplus-community.net/rytecUK_SkyLive.xz"],"rytec_uk_sport":["http://www.xmltvepg.nl/rytecUK_SportMovies.xz","http://rytecepg.wanwizard.eu/rytecUK_SportMovies.xz","http://epg.vuplus-community.net/rytecUK_SportMovies.xz"]}
SPORT_TERMS={"football":["premier league","championship","league one","league two","fa cup","uefa","europa league","champions league","football","soccer"],"rugby":["rugby","six nations","premiership rugby","rugby championship"],"boxing":["boxing","fight night","heavyweight"],"ufc":["ufc","ultimate fighting championship"],"tennis":["tennis","atp","wta","grand slam","wimbledon","us open","french open","australian open"],"golf":["golf","pga","lpga","ryder cup","masters tournament"],"cricket":["cricket","test match","t20","odi","the hundred"],"f1":["formula 1","formula one","f1","grand prix"],"f2":["formula 2","f2"],"f3":["formula 3","f3"],"darts":["darts","pdc"],"snooker":["snooker","world snooker"],"cycling":["cycling","tour de france","giro d'italia","vuelta"],"motorsport":["motorsport","motogp","nascar","indycar","wrc"],"nfl":["nfl","super bowl"],"nba":["nba","basketball"],"baseball":["mlb","baseball"],"ice hockey":["nhl","ice hockey"],"horse racing":["horse racing","racing from","kempton","ascot","cheltenham","aintree","newmarket"],"wrestling":["wwe","aew","wrestling"]}
SPORT_CHANNEL_RE=re.compile(r"sky\s*sp|sky sports|tnt sport|premier sports|bt sport|eurosport|racing tv|sky f1|sky golf|skysp",re.I)
RADIO_CHANNEL_RE=re.compile(r"talksport|talk sport|bbc radio|bbc sounds|radio [0-9]|absolute radio|capital fm|heart fm|kiss fm|smooth radio|lbc|magic radio|virgin radio|greatest hits radio|radio x|classic fm|gold radio",re.I)
# Collapse every BBC One / BBC 1 / BBC1 regional, HD and nation variant into one guide row.
BBC_ONE_RE=re.compile(r"\bbbc\s*(?:one|1)\b",re.I)
PROMO_RE=re.compile(r"^(this is |welcome to |channel |coming up|programming on |schedule$)",re.I); NEWS_RE=re.compile(r"sports news|sky sports news|live at the races",re.I)
def normalise_channel(channel):
 c=' '.join(channel.split()).strip()
 if BBC_ONE_RE.match(c): return 'BBC One'
 return c
def download(url):
 req=urllib.request.Request(url,headers={"User-Agent":"SportTVGuide/0.3"})
 with urllib.request.urlopen(req,timeout=30) as r:return r.read()
def xml_bytes(raw,url):
 if raw[:2]==b"\x1f\x8b" or url.endswith('.gz'):return gzip.decompress(raw)
 if raw[:6]==b"\xfd7zXZ\x00" or url.endswith('.xz'):return lzma.decompress(raw)
 return raw
def parse_dt(v):
 m=re.match(r"(\d{14})\s*([+-]\d{4})?",v or '')
 if not m:raise ValueError(v)
 d=datetime.strptime(m.group(1),'%Y%m%d%H%M%S');o=m.group(2)
 if o:
  sign=1 if o[0]=='+' else -1; mins=int(o[1:3])*60+int(o[3:5]);return d.replace(tzinfo=timezone(sign*timedelta(minutes=mins))).astimezone(timezone.utc)
 return d.replace(tzinfo=timezone.utc)
def text(el):return ' '.join(''.join(el.itertext()).split()) if el is not None else ''
def classify(title,desc,channel,categories):
 if RADIO_CHANNEL_RE.search(channel):return None,0.0
 tl=title.lower().strip(); category_text=' '.join(categories).lower(); hay=f"{tl} {category_text}"
 if NEWS_RE.search(tl):return None,0.0
 if PROMO_RE.search(tl) and not any(t in tl for t in ['premier league','champions league','rugby','boxing','ufc','tennis','golf','cricket','formula','grand prix']):return None,0.0
 scores={s:sum(1 for t in ts if t in hay) for s,ts in SPORT_TERMS.items()};scores={k:v for k,v in scores.items() if v}
 if scores:
  sport=max(scores,key=scores.get);return sport,min(.99,.75+.08*scores[sport])
 if SPORT_CHANNEL_RE.search(channel):return 'other',.70
 return None,0.0
def ingest(name,urls,start,end):
 errors=[]
 for url in urls:
  try:
   raw=download(url);root=ET.fromstring(xml_bytes(raw,url));chs={c.attrib.get('id',''):normalise_channel(text(c.find('display-name'))) for c in root.findall('channel')};ps=[]
   for p in root.findall('programme'):
    try:s,e=parse_dt(p.attrib.get('start','')),parse_dt(p.attrib.get('stop',''))
    except Exception:continue
    if e<=start or s>=end:continue
    cid=p.attrib.get('channel','');ch=chs.get(cid,normalise_channel(cid));title,desc=text(p.find('title')),text(p.find('desc'));cats=[text(x) for x in p.findall('category')];sport,conf=classify(title,desc,ch,cats)
    if sport:ps.append({'channel':ch,'channel_id':cid,'title':title,'description':desc,'categories':cats,'start':s.isoformat().replace('+00:00','Z'),'end':e.isoformat().replace('+00:00','Z'),'sport':sport,'confidence':conf,'source':name})
   if ps:return ps,{'ok':True,'url':url,'programmes':len(ps),'sha256':hashlib.sha256(raw).hexdigest()}
   errors.append(f'{url}: parsed but no sports programmes')
  except Exception as ex:errors.append(f'{url}: {ex}')
 return [],{'ok':False,'errors':errors}
def main():
 now=datetime.now(timezone.utc);start=now.replace(minute=0 if now.minute<30 else 30,second=0,microsecond=0);end=start+timedelta(hours=72);all_events=[];health={}
 for n,u in SOURCES.items():
  es,st=ingest(n,u,start,end);health[n]=st;all_events.extend(es)
 unique={}
 for e in all_events:
  k=(e['channel'].strip().lower(),e['title'].strip().lower(),e['start']);old=unique.get(k)
  if old is None or e['confidence']>old['confidence']:unique[k]=e
 events=sorted(unique.values(),key=lambda x:x['start']);cc=Counter(e['channel'] for e in events);sc=Counter(e['sport'] for e in events)
 payload={'generated_at':now.isoformat().replace('+00:00','Z'),'window_start':start.isoformat().replace('+00:00','Z'),'window_end':end.isoformat().replace('+00:00','Z'),'timezone':'UTC','event_count':len(events),'channel_count':len(cc),'channels':sorted(cc),'sport_counts':dict(sorted(sc.items())),'events':events}
 if events:(OUT/'guide.json').write_text(json.dumps(payload,indent=2),encoding='utf-8');health['publish']={'ok':True,'events':len(events),'channels':len(cc)}
 else:health['publish']={'ok':False,'reason':'no valid sports events; previous guide retained if present'}
 (OUT/'health.json').write_text(json.dumps({'checked_at':now.isoformat().replace('+00:00','Z'),'window_start':start.isoformat().replace('+00:00','Z'),'window_end':end.isoformat().replace('+00:00','Z'),'sources':health,'channel_count':len(cc),'sport_counts':dict(sorted(sc.items()))},indent=2),encoding='utf-8')
 print(json.dumps(health,indent=2))
if __name__=='__main__':main()
