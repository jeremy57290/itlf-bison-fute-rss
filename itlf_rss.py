#!/usr/bin/env python3
"""ITLF – DATEX II SituationPublication snapshot to RSS 2.0 (Python 3.10+)."""
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

SOURCE = os.getenv('ITLF_DATEX_URL', 'https://tipi.bison-fute.gouv.fr/bison-fute-ouvert/publicationsDIR/Evenementiel-DIR/grt/RRN/content.xml')
OUTPUT = Path(os.getenv('ITLF_RSS_PATH', 'rss.xml'))
STATE = Path(os.getenv('ITLF_STATE_PATH', 'state.json'))
DEPTS = {'54', '55', '57', '88'}
# Bounding box is only a fallback, not proof of a French department.
BBOX = (47.7, 4.7, 49.7, 7.7)
MAX_MISSES = 2
LOCAL_TZ = ZoneInfo('Europe/Paris')
LABELS = {'accident': '🚨 Accident', 'closure': '⛔ Fermeture', 'jam': '🚗 Bouchon', 'works': '🚧 Travaux', 'obstacle': '⚠️ Obstacle'}
XSI_TYPE = '{http://www.w3.org/2001/XMLSchema-instance}type'

def local(tag):
    return tag.rsplit('}', 1)[-1]

def walk(node, *names):
    wanted = set(names)
    return [x for x in node.iter() if local(x.tag) in wanted]

def first(node, *names):
    for x in walk(node, *names):
        if x.text and x.text.strip():
            return x.text.strip()
    return ''

def dt(value):
    if not value:
        return None
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result if result.tzinfo else result.replace(tzinfo=LOCAL_TZ)
    except ValueError:
        return None

def utc_date(value):
    return dt(value) or datetime.now(timezone.utc)

def download(url):
    req = Request(url, headers={'User-Agent': 'ITLF-RSS/2.0', 'Accept': 'application/xml,text/xml,*/*'})
    with urlopen(req, timeout=35) as response:
        raw = response.read(20_000_001)
    if len(raw) > 20_000_000:
        raise ValueError('XML too large')
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('DTD forbidden')
    return ET.fromstring(raw)

def category(record):
    # Match semantic DATEX II record types, not arbitrary free-text comments.
    types = ' '.join(local(x.tag) + ' ' + x.attrib.get(XSI_TYPE, '').split(':')[-1] for x in record.iter()).lower()
    for name, terms in (
        ('accident', ('accident', 'collision')),
        ('closure', ('roadclosed', 'roadclosure', 'carriagewayclosure', 'lanesclosed', 'closure')),
        ('jam', ('abnormaltraffic', 'trafficcongestion', 'queuingtraffic', 'trafficjam')),
        ('works', ('roadworks', 'constructionworks', 'maintenanceworks')),
        ('obstacle', ('obstruction', 'vehicleobstruction', 'animalpresence', 'objectontheroad', 'breakdown', 'hazard')),
    ):
        if any(term in types for term in terms):
            return name
    return None

def normalize_road(value):
    value = (value or '').strip()
    match = re.fullmatch(r'([ANDE])\s*0*(\d+)(.*)', value, re.I)
    return f'{match.group(1).upper()}{int(match.group(2))}{match.group(3)}' if match else value

def location(record):
    dept = ''
    for element in walk(record, 'administrativeAreaOfLinearSection', 'administrativeAreaOfPoint', 'county', 'department', 'departmentCode'):
        value = (element.text or '').strip()
        if value in DEPTS:
            dept = value
    for element in record.iter():
        for key, value in element.attrib.items():
            if local(key).lower() in ('department', 'departmentcode', 'departement') and value.strip() in DEPTS:
                dept = value.strip()
    coords = []
    for element in record.iter():
        children = {local(child.tag): (child.text or '').strip() for child in element}
        if 'latitude' in children and 'longitude' in children:
            try:
                lat, lon = float(children['latitude']), float(children['longitude'])
                coords.append((lat, lon))
            except ValueError:
                pass
    in_bbox = [(lat, lon) for lat, lon in coords if BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]]
    # Department evidence wins; a coarse bounding box is fallback only.
    if not dept and not in_bbox:
        return None
    road = normalize_road(first(record, 'roadNumber', 'roadName', 'roadIdentifier'))
    town = first(record, 'townName', 'city', 'localityName')
    direction = first(record, 'directionBoundOnLinearSection', 'directionRelativeOnLinearSection', 'directionRelativeAtPoint')
    point = in_bbox[0] if in_bbox else None
    return {'department': dept, 'road': road, 'town': town, 'direction': direction, 'point': point}

def valid(record, now):
    status = first(record, 'validityStatus').lower()
    if status in ('suspended', 'inactive', 'cancelled', 'canceled'):
        return False
    # definedByValidityTime is a DATEX status, not a cancellation.
    starts = [dt(e.text.strip()) for e in walk(record, 'overallStartTime') if e.text]
    ends = [dt(e.text.strip()) for e in walk(record, 'overallEndTime') if e.text]
    if starts and starts[0] and starts[0] > now:
        return False
    if ends and ends[0] and ends[0] <= now:
        return False
    # Do not guess validity from unspecified recurring periods.
    return True

def comment_text(record):
    for element in walk(record, 'comment', 'generalPublicComment', 'nonGeneralPublicComment'):
        value = first(element, 'value', 'commentText')
        if value:
            return value
    return ''

def parse(root):
    publications = walk(root, 'payloadPublication')
    if not publications or not any('SituationPublication' in p.attrib.get(XSI_TYPE, '') or walk(p, 'situation') for p in publications):
        raise ValueError('Not a DATEX II SituationPublication; existing RSS preserved')
    now = datetime.now(timezone.utc)
    items = {}
    for situation in walk(root, 'situation'):
        sid = situation.attrib.get('id', '')
        for record in walk(situation, 'situationRecord'):
            cat = category(record)
            if not cat or not valid(record, now):
                continue
            loc = location(record)
            if not loc:
                continue
            rid = record.attrib.get('id', '')
            if not sid and not rid:
                continue
            key = 'bison:' + sid + ':' + rid
            place = ' – '.join(x for x in (loc['road'], loc['town']) if x) or 'Lorraine'
            title = f'{LABELS[cat]} – {place}'
            parts = [title]
            if loc['department']:
                parts.append('Département ' + loc['department'])
            if loc['direction']:
                if loc['direction'] in ('aligned', 'opposite'):
                    parts.append('Sens DATEX : ' + loc['direction'] + ' (direction géographique non déterminée)')
                else:
                    parts.append('Direction : ' + loc['direction'])
            note = comment_text(record)
            if note:
                parts.append(note)
            when = first(record, 'situationRecordCreationTime', 'situationRecordFirstSupplierVersionTime', 'overallStartTime')
            items[key] = {'title': title, 'description': ' | '.join(parts), 'date': utc_date(when).isoformat(), 'category': cat, 'misses': 0}
    return items

def write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.itlf-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def rss(items):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>',
             '<title>ITLF – Alertes trafic Lorraine et frontières</title>',
             '<link>https://www.bison-fute.gouv.fr/</link>',
             '<description>Événements routiers issus de Bison Futé / DIR – Licence Ouverte 2.0</description>',
             '<language>fr-FR</language>',
             f'<lastBuildDate>{format_datetime(datetime.now(timezone.utc))}</lastBuildDate>']
    for key, obj in sorted(items.items(), key=lambda pair: utc_date(pair[1]['date']), reverse=True):
        guid = 'urn:itlf:' + hashlib.sha256(key.encode()).hexdigest()
        lines.extend(['<item>', f'<title>{escape(obj["title"])}</title>',
                      f'<description>{escape(obj["description"])}</description>',
                      f'<guid isPermaLink="false">{guid}</guid>',
                      f'<pubDate>{format_datetime(utc_date(obj["date"]))}</pubDate>',
                      f'<category>{escape(obj["category"])}</category>', '</item>'])
    return '\n'.join(lines + ['</channel></rss>']) + '\n'

def run():
    root = download(SOURCE)
    fresh = parse(root)
    old = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    merged = {}
    for key, item in fresh.items():
        if key in old:
            item['date'] = old[key].get('date', item['date'])
        merged[key] = item
    for key, item in old.items():
        if key not in fresh and item.get('misses', 0) + 1 < MAX_MISSES:
            item['misses'] = item.get('misses', 0) + 1
            merged[key] = item
    write_atomic(OUTPUT, rss(merged))
    write_atomic(STATE, json.dumps(merged, ensure_ascii=False, indent=2))
    print(f'RSS: {len(merged)} events ({len(fresh)} present in source)')

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        run()
    except Exception:
        logging.exception('Update failed; previous RSS preserved')
        sys.exit(1)
