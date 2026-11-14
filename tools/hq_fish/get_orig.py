"""Downloads the full-resolution ('original', up to 2048 px) versions of chosen candidate photos.
python3 -I get_orig.py <out dir> key:index ..."""
import json, sys, time, urllib.request
UA = {'User-Agent': 'AnglersBite-reference/1.0'}
out = sys.argv[1]
for a in sys.argv[2:]:
    key, i = a.split(':'); i = int(i)
    m = json.load(open(f'{__import__("os").environ.get("CD","cand")}/{key}_meta.json'))[i]
    obs, k = m['obs'], int(m['file'].rsplit('_', 1)[1].split('.')[0])
    ph = json.load(urllib.request.urlopen(urllib.request.Request(f'https://api.inaturalist.org/v1/observations/{obs}', headers=UA)))['results'][0]['photos'][k]
    url = ph['url'].replace('/square.', '/original.')
    open(f'{out}/{m["file"]}', 'wb').write(urllib.request.urlopen(urllib.request.Request(url, headers=UA)).read())
    print(m['file'], ph['license_code'])
    time.sleep(.5)
