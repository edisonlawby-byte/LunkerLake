"""Downloads chosen Wikimedia Commons files (scaled to <= 2400 px wide) with licence/author metadata, one metadata
request for all titles, polite delays and retry on 429. Writes <out>/<key>_meta.json like inat_candidates.py.
python3 -I commons_get.py <out dir> <spec json: {"key": ["Title", ...], ...}>"""
import json, sys, os, re, time, urllib.request, urllib.parse, urllib.error
UA = {'User-Agent': 'AnglersBite-reference/1.0 (personal game project; reference research)'}
def get(url, tries=6):
    for k in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(min(90, max(int(e.headers.get('Retry-After') or 0), 20 * (k + 1)))); continue
            raise
    raise RuntimeError('rate limited: ' + url)
out = sys.argv[1]; spec = json.loads(open(sys.argv[2]).read())
allt = ['File:' + t for ts in spec.values() for t in ts]
info = {}
for i in range(0, len(allt), 40):
    q = urllib.parse.urlencode({'action': 'query', 'titles': '|'.join(allt[i:i + 40]), 'prop': 'imageinfo', 'iiprop': 'url|size|extmetadata', 'iiurlwidth': 1920, 'format': 'json'})
    r = json.loads(get('https://commons.wikimedia.org/w/api.php?' + q))
    norm = {n['to']: n['from'] for n in r['query'].get('normalized', [])}
    for p in r['query']['pages'].values():
        if 'imageinfo' in p: info[norm.get(p['title'], p['title'])] = p['imageinfo'][0]
    time.sleep(3)
for key, ts in spec.items():
    mp = os.path.join(out, f'{key}_meta.json'); meta = []
    for t in ts:
        ii = info.get('File:' + t)
        if not ii: print('missing', t); continue
        md = ii.get('extmetadata', {}); lic = md.get('LicenseShortName', {}).get('value', '')
        who = re.sub('<[^>]+>', '', md.get('Artist', {}).get('value', '')).strip()[:80]
        fn = f"{key}_c{len(meta)}.jpg"
        if not os.path.exists(os.path.join(out, fn)):
            try:
                u = ii['url'].split('?')[0]; w = next((x for x in (1920, 1280, 960) if ii['width'] >= x), 0)  # standard thumb steps on upload.wikimedia.org
                if w and not u.lower().endswith('.png'):
                    d_, f_ = u.rsplit('/', 1); u = d_.replace('/commons/', '/commons/thumb/') + '/' + f_ + f'/{w}px-' + f_
                data = get(u, tries=6)
                import io; from PIL import Image
                im = Image.open(io.BytesIO(data)).convert('RGB'); im.thumbnail((2400, 2400)); b = io.BytesIO(); im.save(b, 'JPEG', quality=92); data = b.getvalue()
            except Exception as e:
                print('skip', t, e, flush=True); continue
            open(os.path.join(out, fn), 'wb').write(data)
        meta.append({'file': fn, 'obs': t, 'license': lic, 'attribution': f'{who} ({lic}), Wikimedia Commons', 'author': who,
                     'url': ii['descriptionurl'], 'w': ii['width'], 'h': ii['height']})
        print(key, len(meta) - 1, lic, who[:30], t[:50], flush=True); time.sleep(20)
    json.dump(meta, open(mp, 'w'), indent=1)
