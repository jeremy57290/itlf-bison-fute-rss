#!/usr/bin/env python3
"""ITLF: snapshot DATEX II SituationPublication -> RSS 2.0. Python 3.10+."""
import hashlib, json, logging, os, re, sys, tempfile
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

SOURCE = os.getenv('ITLF_DATEX_URL', 'https://tipi.bison-fute.gouv.fr/bison-fute-ouvert/publicationsDIR/Evenementiel-DIR/grt/RRN/content.xml')
OUTPUT = Path(os.getenv('ITLF_RSS_PATH', 'rss.xml'))
STATE = Path(os.getenv('ITLF_STATE_PATH', 'state.json'))
# French departments only. Foreign roads require a separate compatible source.
DEPTS = {'54','55','57','88'}
# conservative approximate bbox for Lorraine; department check takes priority
BBOX = (47.7, 4.7, 49.7, 7.7)
MAX_MISSES = 2
LABELS = {'accident':'🚨 Accident','closure':'⛔ Fermeture','jam':'🚗 Bouchon', 'works':'🚧 Travaux','obstacle':'⚠️ Obstacle'}

def local(tag): return tag.rsplit('}', 1)[-1]
def walk(node, *names):
    names = set(names)
    return [x for x in node.iter() if local(x.tag) in names]
def first(node, *names):
    for x in walk(node, *names):
        if x.text and x.text.strip(): return x.text.strip()
    return ''
def safe(s): return escape(str(s or ''))
def utc_date(value):
    if value:
        try:
            d = datetime.fromisoformat(value.replace('Z','+00:00'))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError: pass
    return datetime.now(timezone.utc)
def download(url):
    req = Request(url, headers={'User-Agent':'ITLF-RSS/1.0 (+https://www.bison-fute.gouv.fr/)', 'Accept':'application/xml,text/xml,*/*'})
    with urlopen(req, timeout=35) as r:
        raw = r.read(20_000_001)
        if len(raw)>20_000_000: raise ValueError('XML too large')
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper(): raise ValueError('DTD forbidden')
    return ET.fromstring(raw)
def category(record):
    types = ' '.join((local(x.tag) + ' ' + str(x.attrib.get('{http://www.w3.org/2001/XMLSchema-instance}type',''))) for x in record.iter()).lower()
    # Avoid classifying a whole situation on its generic metadata.
    if any(x in types for x in ('accident','collision')): return 'accident'
    if any(x in types for x in ('roadclosed','roadclosure','carriagewayclosure','lanesclosed','roadorcarriagewayorlanemanagement','closure','closed')): return 'closure'
    if any(x in types for x in ('abnormaltraffic','trafficcongestion','queuingtraffic','trafficjam')): return 'jam'
    if any(x in types for x in ('roadworks','constructionworks','maintenanceworks','works')): return 'works'
    if any(x in types for x in ('obstruction','vehicleobstruction','animalpresence','objectontheroad','hazard','breakdown','obstacle')): return 'obstacle'
    return None

def location(record):
    # Strict department evidence. Coordinates accepted only when in broad Lorraine bbox.
    dept = ''
    for el in walk(record, 'administrativeAreaOfLinearSection','administrativeAreaOfPoint','county','department','departmentCode'):
        val = (el.text or '').strip()
        if val in DEPTS: dept = val
    for el in record.iter():
        for k,v in el.attrib.items():
            if local(k).lower() in ('department','departmentcode','departement') and v.strip() in DEPTS: dept=v.strip()
    lat,lon = first(record,'latitude'),first(record,'longitude')
    coords = False
    try: coords = BBOX[0]<=float(lat)<=BBOX[2] and BBOX[1]<=float(lon)<=BBOX[3]
    except (TypeError,ValueError): pass
    # Do not accept a location based solely on a route number: A31 also runs outside Lorraine.
    if not (dept or coords): return None
    road = first(record,'roadNumber','roadName','roadIdentifier')
    town = first(record,'townName','city','localityName')
    direction = first(record,'directionBoundOnLinearSection','directionRelativeOnLinearSection','directionRelativeAtPoint')
    return {'department':dept,'road':road,'town':town,'direction':direction,'lat':lat if coords else '', 'lon':lon if coords else ''}

def parse(root):
    publications = walk(root,'payloadPublication')
    if not publications or not any('SituationPublication' in p.attrib.get('{http://www.w3.org/2001/XMLSchema-instance}type','') or walk(p,'situation') for p in publications):
        raise ValueError('Not a DATEX II SituationPublication snapshot; refusing to clear existing feed')
    items={}
    for situation in walk(root,'situation'):
        sid=situation.attrib.get('id','')
        for record in walk(situation,'situationRecord'):
            cat=category(record)
            if not cat: continue
            loc=location(record)
            if not loc: continue
            rid=record.attrib.get('id','')
            if not sid and not rid: continue
            status=first(record,'validityStatus').lower()
            if status in ('suspended','definedbyvaliditytime', 'inactive','cancelled','canceled'): continue
            end=first(record,'overallEndTime','endOfPeriod')
            if end and utc_date(end) <= datetime.now(timezone.utc): continue
            key='bison:'+sid+':'+rid
            comment=first(record,'value','comment','commentText','situationRecordVersionTime')
            label=LABELS[cat]
            place=' – '.join(p for p in [loc['road'],loc['town']] if p) or 'Lorraine'
            title=f'{label} – {place}'
            desc=' | '.join(p for p in [title, ('Département '+loc['department']) if loc['department'] else '', ('Sens : '+loc['direction']) if loc['direction'] else '',comment] if p)
            when=first(record,'situationRecordCreationTime','situationRecordFirstSupplierVersionTime','overallStartTime')
            items[key]={'title':title,'description':desc,'date':when or datetime.now(timezone.utc).isoformat(),'category':cat}
    return items

def write_atomic(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.itlf-')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f: f.write(data)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def rss(items):
    lines=['<?xml version="1.0" encoding="UTF-8"?>','<rss version="2.0"><channel>', '<title>ITLF – Alertes trafic Lorraine et frontières</title>', '<link>https://www.bison-fute.gouv.fr/</link>', '<description>Événements routiers en cours – données Bison Futé / DIR (Licence Ouverte 2.0)</description>', '<language>fr-FR</language>',f'<lastBuildDate>{format_datetime(datetime.now(timezone.utc))}</lastBuildDate>']
    for key,obj in sorted(items.items(),key=lambda x:x[1]['date'],reverse=True):
        guid='urn:itlf:'+hashlib.sha256(key.encode()).hexdigest()
        lines.extend(['<item>',f'<title>{safe(obj["title"])}</title>',f'<description>{safe(obj["description"])}</description>',f'<guid isPermaLink="false">{guid}</guid>',f'<pubDate>{format_datetime(utc_date(obj["date"]))}</pubDate>',f'<category>{safe(obj["category"])}</category>','</item>'])
    return '\n'.join(lines+['</channel></rss>'])+'\n'

def run():
    root=download(SOURCE)
    fresh=parse(root)
    old={}
    if STATE.exists(): old=json.loads(STATE.read_text(encoding='utf-8'))
    merged={}
    for key,item in fresh.items():
        # Preserve publication date for unchanged events.
        if key in old: item['date']=old[key]['date']
        item['misses']=0
        merged[key]=item
    for key,item in old.items():
        if key not in fresh and item.get('misses',0)+1<MAX_MISSES:
            item['misses']=item.get('misses',0)+1
            merged[key]=item
    write_atomic(OUTPUT,rss(merged))
    write_atomic(STATE,json.dumps(merged,ensure_ascii=False,indent=2))
    print(f'RSS: {len(merged)} events ({len(fresh)} present in source)')

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    try: run()
    except Exception as exc:
        logging.exception('Update failed; previous RSS preserved')
        sys.exit(1)
