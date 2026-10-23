#!/usr/bin/env python3
"""Download and pin French department boundaries for ITLF; run once before deployment."""
import json
import os
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

URL = os.getenv(
    'ITLF_BOUNDARIES_SOURCE',
    'https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements.geojson'
)
DEST = Path(os.getenv('ITLF_BOUNDARIES_PATH', 'lorraine_departements.geojson'))
CODES = {'54', '55', '57', '88'}

def main():
    req = Request(URL, headers={'User-Agent': 'ITLF-RSS/3.2', 'Accept': 'application/geo+json,application/json'})
    with urlopen(req, timeout=45) as response:
        raw = response.read(12_000_001)
    if len(raw) > 12_000_000:
        raise ValueError('Boundary file too large')
    data = json.loads(raw)
    if data.get('type') != 'FeatureCollection':
        raise ValueError('Expected GeoJSON FeatureCollection')
    selected = []
    for feature in data.get('features', []):
        props = feature.get('properties') or {}
        code = str(props.get('code', '')).zfill(2)
        if code in CODES:
            geometry = feature.get('geometry') or {}
            if geometry.get('type') not in ('Polygon', 'MultiPolygon') or not geometry.get('coordinates'):
                raise ValueError('Missing polygon for ' + code)
            selected.append({'type': 'Feature', 'properties': {'code': code, 'nom': props.get('nom', '')},
                             'geometry': geometry})
    if {f['properties']['code'] for f in selected} != CODES or len(selected) != 4:
        raise ValueError('Expected exactly four departments: 54, 55, 57, 88')
    out = {'type': 'FeatureCollection', 'features': selected}
    DEST.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=DEST.parent, prefix='.boundaries-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
            f.write('\n')
        os.replace(temp, DEST)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    print(f'Boundary file ready: {DEST} ({DEST.stat().st_size} bytes)')

if __name__ == '__main__':
    main()
