#!/usr/bin/env python3
"""ITLF DATEX II SituationPublication snapshot -> RSS 2.0 and GeoJSON. Python 3.10+."""
import hashlib
import json
import logging
from collections import Counter
import os
import re
import tempfile
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

SOURCE = os.getenv('ITLF_DATEX_URL', 'https://tipi.bison-fute.gouv.fr/bison-fute-ouvert/publicationsDIR/Evenementiel-DIR/grt/RRN/content.xml')
OUTPUT = Path(os.getenv('ITLF_RSS_PATH', 'rss.xml'))
GEOJSON = Path(os.getenv('ITLF_GEOJSON_PATH', 'traffic.geojson'))
STATE = Path(os.getenv('ITLF_STATE_PATH', 'state.json'))
DEPTS = {'54', '55', '57', '88'}
# Approximate envelope is a candidate filter, NOT proof of belonging to Lorraine.
BBOX = (47.7, 4.7, 49.7, 7.7)
MAX_MISSES = 2
# Optional official departmental boundaries as GeoJSON (54, 55, 57, 88).
# Without this file, only a broad candidate bounding box is available.
BOUNDARIES = Path(os.getenv('ITLF_BOUNDARIES_PATH', 'lorraine_departements.geojson'))
REJECT_REPORT = Path(os.getenv('ITLF_REJECT_REPORT', 'rejets.json'))
# GeoJSON source from france-geojson (open data based on French administrative boundaries).
# Pinned in the repository by the separate bootstrap script, never silently refreshed.
BOUNDARIES_SOURCE = 'https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements.geojson'


LABELS = {'accident': '🚨 Accident', 'closure': '⛔ Fermeture', 'jam': '🚗 Bouchon', 'works': '🚧 Travaux', 'obstacle': '⚠️ Obstacle'}
XSI_TYPE = '{http://www.w3.org/2001/XMLSchema-instance}type'


def local(tag):
    return tag.rsplit('}', 1)[-1]


def walk(node, *names):
    names = set(names)
    return [el for el in node.iter() if local(el.tag) in names]


def first(node, *names):
    for el in walk(node, *names):
        if el.text and el.text.strip():
            return el.text.strip()
    return ''


def text_clean(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def parse_date(value):
    if not value:
        return None
    try:
        d = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        # An unqualified timestamp is ambiguous: do not use it to expire an event.
        return d if d.tzinfo else None
    except ValueError:
        return None


def download(url):
    req = Request(url, headers={'User-Agent': 'ITLF-RSS/3.0', 'Accept': 'application/xml,text/xml,*/*'})
    with urlopen(req, timeout=35) as response:
        data = response.read(20_000_001)
    if len(data) > 20_000_000:
        raise ValueError('Source XML too large')
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('DTD forbidden')
    return ET.fromstring(data)


def category(record):
    # Use record's concrete DATEX type, not metadata from the entire situation.
    types = ' '.join([record.attrib.get(XSI_TYPE, '')] + [el.attrib.get(XSI_TYPE, '') for el in record.iter()])
    types = types.lower()
    if any(t in types for t in ('accident', 'collision')):
        return 'accident'
    if any(t in types for t in ('roadclosed', 'roadclosure', 'carriagewayclosure', 'lanesclosed', 'closure', 'closed')):
        return 'closure'
    if any(t in types for t in ('abnormaltraffic', 'trafficcongestion', 'queuingtraffic', 'trafficjam')):
        return 'jam'
    if any(t in types for t in ('roadworks', 'constructionworks', 'maintenanceworks', 'works')):
        return 'works'
    if any(t in types for t in ('obstruction', 'vehicleobstruction', 'animalpresence', 'objectontheroad', 'hazard', 'breakdown', 'obstacle')):
        return 'obstacle'
    return None


def normalize_road(value):
    value = text_clean(value)
    m = re.fullmatch(r'([AaNnDd])0*(\d+)(.*)', value)
    return f'{m.group(1).upper()}{int(m.group(2))}{m.group(3)}' if m else value


def coordinates(record):
    # Only pair lat/lon from the same enclosing point, never unrelated descendants.
    for el in record.iter():
        direct = {local(ch.tag): (ch.text or '').strip() for ch in el}
        if 'latitude' in direct and 'longitude' in direct:
            try:
                lat, lon = float(direct['latitude']), float(direct['longitude'])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return lat, lon
            except ValueError:
                pass
    return None


def inside_polygon(lon, lat, ring):
    """Ray casting on GeoJSON [longitude, latitude] rings."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        x1, y1 = ring[i]
        x2, y2 = ring[j]
        if (y1 > lat) != (y2 > lat):
            x_cross = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def department_from_boundaries(point, boundaries):
    """Return department only when a point is inside a supplied polygon."""
    if not point or not boundaries:
        return ''
    lat, lon = point
    for feature in boundaries.get('features', []):
        props = feature.get('properties') or {}
        dep = str(props.get('code') or props.get('code_departement') or
                  props.get('department') or props.get('dep') or '').zfill(2)
        if dep not in DEPTS:
            continue
        geometry = feature.get('geometry') or {}
        typ = geometry.get('type')
        coords = geometry.get('coordinates') or []
        polygons = [coords] if typ == 'Polygon' else coords if typ == 'MultiPolygon' else []
        for polygon in polygons:
            if polygon and inside_polygon(lon, lat, polygon[0]) and not any(
                    inside_polygon(lon, lat, hole) for hole in polygon[1:]):
                return dep
    return ''


def load_boundaries():
    if not BOUNDARIES.exists():
        raise FileNotFoundError(
            f'{BOUNDARIES} missing: refusing approximate filtering. '
            'Run python prepare_boundaries.py and commit the resulting file.'
        )
    data = json.loads(BOUNDARIES.read_text(encoding='utf-8'))
    if data.get('type') != 'FeatureCollection':
        raise ValueError('Invalid department boundaries GeoJSON')
    found = {str((f.get('properties') or {}).get('code', '')).zfill(2)
             for f in data.get('features', [])}
    if not DEPTS.issubset(found):
        raise ValueError('Boundary GeoJSON must contain departments 54, 55, 57 and 88 (property code)')
    if any((f.get('geometry') or {}).get('type') not in ('Polygon', 'MultiPolygon')
           for f in data.get('features', [])):
        raise ValueError('Invalid department geometry')
    return data


def location(record, boundaries):
    """Fail closed when a point is absent or outside the four polygons."""
    dept = ''
    for el in walk(record, 'department', 'departmentCode', 'departement'):
        val = text_clean(el.text)
        if val:
            dept = val.zfill(2) if val.isdigit() else val
            break
    for el in record.iter():
        for key, value in el.attrib.items():
            if local(key).lower() in ('department', 'departmentcode', 'departement'):
                dept = text_clean(value).zfill(2)
                break
    point = coordinates(record)
    if point is None:
        return None, 'missing_coordinates'
    if not (BBOX[0] <= point[0] <= BBOX[2] and BBOX[1] <= point[1] <= BBOX[3]):
        return None, 'outside_department'
    mapped = department_from_boundaries(point, boundaries)
    if not mapped:
        return None, 'outside_department'
    if dept and dept not in DEPTS:
        return None, 'conflicting_location'
    if dept and dept != mapped:
        return None, 'conflicting_location'
    road = normalize_road(first(record, 'roadNumber', 'roadName', 'roadIdentifier'))
    town = text_clean(first(record, 'townName', 'city', 'localityName'))
    return {'department': mapped, 'road': road, 'town': town, 'point': point}, None


def human_place(record, loc):
    """Prefer explicit locality over towns used only as distance markers."""
    town = text_clean(loc.get('town', ''))
    if town:
        return town
    # DATEX often puts the event locality in a short standalone descriptor,
    # after longer "debut/fin" reference-point descriptions.
    details = descriptions(record)
    for value in reversed(details):
        candidate = text_clean(value)
        if (2 <= len(candidate) <= 65
                and re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’ .-]*", candidate)
                and not re.search(r"\b(?:direction|début|fin|situé|route|travaux|vitesse|restriction|bretelle|département)\b", candidate, re.I)
                and candidate.casefold() not in {'nord', 'sud', 'est', 'ouest', 'inconnu'}):
            return candidate
    # Last resort: a named reference point is better than a department number.
    for val in details:
        match = re.search(r"\bsitué(?:e)?\s+\d+\s*m\s+.+?\s+de\s+([^,;|]+)", val, re.I)
        if match:
            place = re.split(r'\s+(?:sur|dans|au niveau de)\s+', match.group(1), maxsplit=1, flags=re.I)[0].strip(' .')
            if place and len(place) <= 75:
                return place
    return ''


def readable_detail(value):
    """Make DATEX distance-marker prose readable without dropping distances."""
    value = text_clean(value)
    value = re.sub(r'\bdébut\s*:\s*situé\s*', 'Début : ', value, flags=re.I)
    value = re.sub(r'\bfin\s*:\s*situé\s*', 'fin : ', value, flags=re.I)
    value = re.sub(r"\bsitué\s+(?=\d+\s*m)", '', value, flags=re.I)
    value = re.sub(r'\s*,\s*fin\s*:', ' ; fin :', value, flags=re.I)
    return value


def readable_direction(value):
    """Shorten only obvious administrative prefixes; never infer a direction."""
    value = text_clean(value)
    value = re.sub(r'^Allemagne\s*[-–]\s*', '', value, flags=re.I)
    value = re.sub(r'^Suisse\s*[-–]\s*', '', value, flags=re.I)
    return value


def descriptions(record):
    """Keep useful public messages, excluding operational metadata."""
    values = []
    for el in walk(record, 'comment', 'commentText', 'locationDescriptor',
                   'locationDescription', 'descriptor', 'value'):
        val = text_clean(el.text)
        if not val or len(val) > 400:
            continue
        low = val.lower()
        if re.fullmatch(r'\d{4}-\d\d-\d\d[tT][^ ]+', val):
            continue
        if low.startswith(('ge_dire/', 'dir est/', 'point particulier :')):
            # Location descriptions remain useful even with the technical prefix.
            if low.startswith('point particulier :'):
                val = re.sub(r'^Point particulier\s*:\s*', '', val, flags=re.I)
            else:
                continue
        if low in ('aligned', 'opposite', 'both', 'unknown', 'hors voie de circulation'):
            continue
        if re.match(r'^de .+ vers .+$', val, re.I):
            continue
        if val not in values:
            values.append(val)
    return values[:3]


def direction(record):
    """Geographic destination only; never publish aligned/opposite or PR senses."""
    for el in walk(record, 'directionDestination', 'destinationName', 'destination'):
        val = text_clean(el.text)
        if val and val.lower() not in ('aligned', 'opposite', 'both', 'unknown'):
            return val
    for el in walk(record, 'comment', 'commentText', 'value', 'descriptor'):
        val = text_clean(el.text)
        match = re.search(r'\bde\s+(.+?)\s+vers\s+([^|;]+)', val, re.I)
        if match:
            return match.group(2).strip()
    return ''


def active(record, now):
    status = first(record, 'validityStatus').lower()
    if status in ('suspended', 'inactive', 'cancelled', 'canceled'):
        return False
    # Some records have several time periods. Only expire if *all* explicit ends
    # have passed. Recurrence calendars require separate support.
    ends = [parse_date(el.text or '') for el in walk(record, 'overallEndTime', 'endOfPeriod')]
    ends = [end for end in ends if end is not None]
    if ends and all(end <= now for end in ends):
        return False
    starts = [parse_date(el.text or '') for el in walk(record, 'overallStartTime', 'startOfPeriod')]
    starts = [start for start in starts if start is not None]
    if starts and all(start > now for start in starts):
        return False
    return True


def diagnostic_fields(record):
    """Capture DATEX fields verbatim, bounded, without inferring a restriction."""
    fields = []
    for element in record.iter():
        value = text_clean(element.text)
        attributes = {local(k): text_clean(v)[:160] for k, v in element.attrib.items()}
        if not value and not attributes:
            continue
        if len(fields) >= 180:
            break
        fields.append({'tag': local(element.tag), 'value': value[:350], 'attributes': attributes})
    return fields


def diagnostic_record(record, situation, sid, loc):
    """Keep relevant record and situation-level measures for manual interpretation."""
    return {
        'situation_id': sid,
        'record_id': record.attrib.get('id', ''),
        'record_type': record.attrib.get(XSI_TYPE, ''),
        'department': loc['department'],
        'road': loc['road'],
        'coordinates': [loc['point'][1], loc['point'][0]],
        'validity_status': first(record, 'validityStatus'),
        'details': descriptions(record),
        'record_fields': diagnostic_fields(record),
        'situation_fields': [
            {'tag': local(child.tag), 'value': text_clean(child.text)[:350]}
            for child in situation if local(child.tag) != 'situationRecord' and text_clean(child.text)
        ][:30],
    }


def management_measure(record):
    """Only explicitly coded DATEX measures; no inferred road closures."""
    if not record.attrib.get(XSI_TYPE, '').endswith('RoadOrCarriagewayOrLaneManagement'):
        return None
    kind = first(record, 'roadOrCarriagewayOrLaneManagementType')
    restricted = first(record, 'numberOfLanesRestricted')
    total = first(record, 'originalNumberOfLanes')
    if kind == 'laneClosures' and restricted.isdigit() and int(restricted) > 0:
        if total.isdigit() and int(restricted) > int(total):
            return None
        return {'kind': 'lane', 'count': int(restricted), 'total': int(total) if total.isdigit() else None}
    if kind == 'contraflow':
        return {'kind': 'contraflow', 'count': None, 'total': None}
    return None


def lane_closure_phrase(count, total):
    """Natural French singular/plural for explicit lane closures."""
    noun = 'voie fermée' if count == 1 else 'voies fermées'
    return f'{count} {noun}' + (f' sur {total}' if total else '')


def management_item(sid, records, now):
    """One alert per situation, with distinct explicitly coded measures."""
    records = sorted(records, key=lambda x: x[0].attrib.get('id', ''))
    first_record, first_loc, _ = records[0]
    roads = sorted({loc['road'] for _, loc, _ in records if loc['road']})
    road = roads[0] if len(roads) == 1 else ''
    towns = []
    for record, loc, _ in records:
        town = human_place(record, loc)
        if town and town not in towns:
            towns.append(town)
    town = ' / '.join(towns[:3])
    dept = first_loc['department']
    kinds = {measure['kind'] for _, _, measure in records}
    label = ('⚠️ Basculement de circulation et voies fermées' if len(kinds) > 1 else
             '⚠️ Basculement de circulation' if 'contraflow' in kinds else
             '⛔ Voie fermée' if len(records) == 1 and records[0][2]['count'] == 1 else
             '⛔ Fermetures de voies')
    place = ' – '.join(x for x in (road, town) if x) or f'Département {dept}'
    title = f'{label} – {place} ({dept})' if place != f'Département {dept}' else f'{label} – {place}'
    parts = [title]
    for record, loc, measure in records:
        desc = ('Basculement de circulation' if measure['kind'] == 'contraflow' else
                lane_closure_phrase(measure['count'], measure['total']))
        direct = readable_direction(direction(record))
        if direct:
            desc += f' – direction {direct}'
        detail = next((readable_detail(d) for d in descriptions(record)
                       if 'situé' in d.lower() or 'bretelle' in d.lower()), '')
        if detail:
            desc += f' – {detail}'
        if desc not in parts:
            parts.append(desc)
    when = first(first_record, 'situationRecordCreationTime', 'situationRecordFirstSupplierVersionTime', 'overallStartTime')
    dt = parse_date(when) or now
    return {
        'title': title, 'description': ' | '.join(parts), 'date': dt.isoformat(),
        'category': 'closure' if kinds == {'lane'} else 'management',
        'department': dept, 'road': road, 'town': town, 'direction': '',
        'coordinates': [first_loc['point'][1], first_loc['point'][0]], 'misses': 0,
    }


def parse(root, boundaries=None):
    publications = walk(root, 'payloadPublication')
    if not publications or not any('SituationPublication' in p.attrib.get(XSI_TYPE, '') or walk(p, 'situation') for p in publications):
        raise ValueError('Not a DATEX II SituationPublication; existing feed preserved')
    now = datetime.now(timezone.utc)
    items = {}
    rejected = Counter()
    rejected_types = Counter()
    rejected_statuses = Counter()
    unknown_in_area = Counter()
    unknown_in_area_examples = {}
    unknown_location_reasons = Counter()
    unknown_inactive = Counter()
    diagnostic_records = []
    management_groups = {}
    management_stats = Counter()
    for situation in walk(root, 'situation'):
        sid = situation.attrib.get('id', '')
        for record in walk(situation, 'situationRecord'):
            cat = category(record)
            if not cat:
                measure = management_measure(record)
                if measure is not None and active(record, now):
                    management_loc, _ = location(record, boundaries)
                    if management_loc is not None and (sid or record.attrib.get('id')):
                        group_id = sid or record.attrib['id']
                        management_groups.setdefault(group_id, []).append((record, management_loc, measure))
                        management_stats[measure['kind']] += 1
                rejected['unrecognized_category'] += 1
                raw_type = record.attrib.get(XSI_TYPE, '') or '(missing type)'
                rejected_types[raw_type] += 1
                # Diagnostic only: unknown types NEVER enter the published feed.
                # Evaluate their actual position and validity to distinguish
                # irrelevant national data from potentially useful local alerts.
                if not active(record, now):
                    unknown_inactive[raw_type] += 1
                else:
                    unknown_loc, unknown_reason = location(record, boundaries)
                    if unknown_loc is None:
                        unknown_location_reasons[unknown_reason] += 1
                    else:
                        unknown_in_area[raw_type] += 1
                        if len(diagnostic_records) < 100:
                            diagnostic_records.append(diagnostic_record(record, situation, sid, unknown_loc))
                        examples = unknown_in_area_examples.setdefault(raw_type, [])
                        if len(examples) < 5:
                            examples.append({
                                'situation_id': sid,
                                'record_id': record.attrib.get('id', ''),
                                'department': unknown_loc['department'],
                                'road': unknown_loc['road'],
                                'town': unknown_loc['town'],
                                'coordinates': [unknown_loc['point'][1], unknown_loc['point'][0]],
                                'details': descriptions(record)[:2]
                            })
                continue
            if not active(record, now):
                rejected['inactive_or_outside_validity'] += 1
                rejected_statuses[first(record, 'validityStatus') or '(missing status)'] += 1
                continue
            loc, reason = location(record, boundaries)
            if loc is None:
                rejected[reason] += 1
                continue
            rid = record.attrib.get('id', '')
            if not sid and not rid:
                rejected['missing_identifier'] += 1
                continue
            key = f'bison:{sid}:{rid}'
            label = LABELS[cat]
            town = human_place(record, loc)
            road = loc['road']
            if road and town:
                place = f"{road} – {town} ({loc['department']})"
            elif road:
                place = f"{road} ({loc['department']})"
            elif town:
                place = f"{town} ({loc['department']})"
            else:
                place = f"Département {loc['department']}"
            title = f'{label} – {place}'
            desc_parts = [title]
            geographic_direction = readable_direction(direction(record))
            if geographic_direction:
                desc_parts.append(f'Direction {geographic_direction}')
            seen = {text_clean(title).casefold(), text_clean(road).casefold(), text_clean(town).casefold()}
            for detail in descriptions(record):
                normalized = text_clean(detail).casefold()
                if normalized not in seen and normalized not in (f'département {loc["department"]}'.casefold(),):
                    desc_parts.append(readable_detail(detail))
                    seen.add(normalized)
            when = first(record, 'situationRecordCreationTime', 'situationRecordFirstSupplierVersionTime', 'overallStartTime')
            dt = parse_date(when) or now
            items[key] = {
                'title': title,
                'description': ' | '.join(desc_parts),
                'date': dt.isoformat(),
                'category': cat,
                'department': loc['department'],
                'road': loc['road'],
                'town': town,
                'direction': geographic_direction,
                'coordinates': [loc['point'][1], loc['point'][0]] if loc['point'] else None,
                'misses': 0,
            }
    for group_id, group_records in management_groups.items():
        # Stable group GUID independent of the number/order of associated measures.
        key = f'bison:{group_id}:management'
        items[key] = management_item(group_id, group_records, now)
    return items, {
        'management_published_records': dict(management_stats),
        'management_published_situations': len(management_groups),
        'rejected_by_reason': dict(rejected),
        'unrecognized_types': dict(rejected_types.most_common(20)),
        'inactive_statuses': dict(rejected_statuses.most_common(20)),
        'unknown_types_in_lorraine': dict(unknown_in_area.most_common()),
        'unknown_types_in_lorraine_examples': unknown_in_area_examples,
        'unknown_types_inactive': dict(unknown_inactive.most_common()),
        'unknown_types_location_rejections': dict(unknown_location_reasons),
        'diagnostic_records': diagnostic_records
    }


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.itlf-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def rss(items):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>',
             '<title>ITLF – Alertes trafic Lorraine et frontières</title>',
             '<link>https://www.bison-fute.gouv.fr/</link>',
             '<description>Événements routiers issus de Bison Futé / DIR – Licence Ouverte 2.0</description>',
             '<language>fr-FR</language>',
             f'<lastBuildDate>{format_datetime(datetime.now(timezone.utc))}</lastBuildDate>']
    for key, item in sorted(items.items(), key=lambda x: x[1]['date'], reverse=True):
        guid = 'urn:itlf:' + hashlib.sha256(key.encode()).hexdigest()
        lines.extend(['<item>', f'<title>{escape(item["title"])}</title>',
                      f'<description>{escape(item["description"])}</description>',
                      f'<guid isPermaLink="false">{guid}</guid>',
                      f'<pubDate>{format_datetime(parse_date(item["date"]) or datetime.now(timezone.utc))}</pubDate>',
                      f'<category>{item["category"]}</category>', '</item>'])
    return '\n'.join(lines + ['</channel></rss>']) + '\n'


def geojson(items):
    features = []
    for key, item in items.items():
        if item.get('coordinates') is not None:
            features.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': item['coordinates']},
                             'properties': {k: v for k, v in item.items() if k not in ('coordinates', 'misses')} | {'id': key}})
    return json.dumps({'type': 'FeatureCollection', 'features': features}, ensure_ascii=False, indent=2) + '\n'


def run():
    boundaries = load_boundaries()
    fresh, rejected = parse(download(SOURCE), boundaries)
    logging.info('Source parsing: %d accepted; rejected: %s', len(fresh), rejected['rejected_by_reason'])
    if not fresh:
        raise ValueError('No eligible events after filtering: preserving previous RSS and state')
    old = {}
    if STATE.exists():
        try:
            old = json.loads(STATE.read_text(encoding='utf-8'))
            if not isinstance(old, dict):
                raise ValueError('Invalid state')
        except (ValueError, OSError):
            logging.warning('Invalid old state, starting from fresh snapshot')
            old = {}
    merged = {}
    for key, item in fresh.items():
        if key in old and parse_date(old[key].get('date', '')):
            item['date'] = old[key]['date']
        merged[key] = item
    for key, item in old.items():
        # Only carry forward v3-format items. This prevents old technical
        # descriptions from leaking into the new feed during migration.
        if key not in fresh and isinstance(item, dict) and item.get('coordinates'):
            point = (item['coordinates'][1], item['coordinates'][0])
            if department_from_boundaries(point, boundaries) and item.get('misses', 0) + 1 < MAX_MISSES:
                item['misses'] = item.get('misses', 0) + 1
                merged[key] = item
    # Validate both representations before replacing the outputs.
    rss_text = rss(merged)
    ET.fromstring(rss_text)
    geojson_text = geojson(merged)
    json.loads(geojson_text)
    atomic(OUTPUT, rss_text)
    atomic(GEOJSON, geojson_text)
    atomic(STATE, json.dumps(merged, ensure_ascii=False, indent=2) + '\n')
    atomic(Path(os.getenv('ITLF_MEASURES_PATH', 'mesures_a_analyser.json')), json.dumps({
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'purpose': 'Diagnostic of unrecognized DATEX types; some explicitly coded lane/contraflow measures are now published',
        'count': len(rejected['diagnostic_records']),
        'records': rejected['diagnostic_records']
    }, ensure_ascii=False, indent=2) + '\n')
    atomic(REJECT_REPORT, json.dumps({
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'accepted': len(fresh),
        'management_published_records': rejected['management_published_records'],
        'management_published_situations': rejected['management_published_situations'],
        'rejected_by_reason': rejected['rejected_by_reason'],
        'unrecognized_types': rejected['unrecognized_types'],
        'inactive_statuses': rejected['inactive_statuses'],
        'unknown_types_in_lorraine': rejected['unknown_types_in_lorraine'],
        'unknown_types_in_lorraine_examples': rejected['unknown_types_in_lorraine_examples'],
        'unknown_types_inactive': rejected['unknown_types_inactive'],
        'unknown_types_location_rejections': rejected['unknown_types_location_rejections'],
        'precise_department_boundaries': True,
        'boundary_file': str(BOUNDARIES)
    }, ensure_ascii=False, indent=2) + '\n')
    print(f'RSS: {len(merged)} events ({len(fresh)} present in source); GeoJSON: {sum(bool(x.get("coordinates")) for x in merged.values())} points')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        run()
    except Exception:
        logging.exception('Update failed; previous files preserved')
        raise SystemExit(1)