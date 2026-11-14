"""Collects candidate reference photos for one species from iNaturalist research-grade observations.
Keeps every photo of each observation (different angles), with licence and attribution. Only licences that allow
reuse in the game's skins are requested (CC0, CC BY, CC BY-SA); public-domain marks come through as cc0/pd.
Usage: python3 -I inat_candidates.py "<scientific name>" <key> <out dir> [observations]"""
import json, sys, os, time, urllib.request, urllib.parse

SCI, KEY, OUT = sys.argv[1:4]
NOBS = int(sys.argv[4]) if len(sys.argv) > 4 else 30
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'AnglersBite-reference/1.0'}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


tx = json.loads(get('https://api.inaturalist.org/v1/taxa?' + urllib.parse.urlencode({'q': SCI, 'rank': 'species', 'per_page': 5})))['results']
tx = next(t for t in tx if t['name'].lower() == SCI.lower())
meta = []
page = 1
while len({m["obs"] for m in meta}) < NOBS and page < 12:
    q = urllib.parse.urlencode({'taxon_id': tx['id'], 'quality_grade': 'research', 'photo_license': 'cc0,cc-by,cc-by-sa',
                                'order_by': 'votes', 'per_page': 50, 'page': page, 'photos': 'true'})
    obs = json.loads(get('https://api.inaturalist.org/v1/observations?' + q))['results']
    if not obs:
        break
    for o in obs:
        if len({m['obs'] for m in meta}) >= NOBS:
            break
        for k, ph in enumerate(o['photos'][:5]):
            lic = ph.get('license_code')
            if lic not in ('cc0', 'cc-by', 'cc-by-sa', 'pd'):
                continue
            url = ph['url'].replace('/square.', '/large.')
            fn = f"{KEY}_{o['id']}_{k}.jpg"
            try:
                open(os.path.join(OUT, fn), 'wb').write(get(url))
            except Exception as e:
                print('skip', fn, e)
                continue
            meta.append({'file': fn, 'obs': o['id'], 'license': lic, 'attribution': ph['attribution'],
                         'url': f"https://www.inaturalist.org/observations/{o['id']}", 'w': ph.get('original_dimensions', {}).get('width'),
                         'h': ph.get('original_dimensions', {}).get('height')})
        time.sleep(.6)
    page += 1
json.dump(meta, open(os.path.join(OUT, f'{KEY}_meta.json'), 'w'), indent=1)
print(KEY, tx['name'], len(meta), 'photos from', len({m['obs'] for m in meta}), 'observations')
