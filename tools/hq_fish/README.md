# HQ fish pipeline (photo-real fish for the Ultra/High settings)

Each high-quality fish is built in Blender from ONE freely licensed side photo of the real species: the body outline
is traced from the photo, the photo itself becomes the skin (straightened onto the body), fins are cut from the photo,
and the eye is a round iris in the species' colours. Medium/Low keep the lighter fish in `models/fish.glb`.

Game side (index.html): `HQ_SPECIES` lists the species that have an HQ version. Each one is
`models/hq/<sp>.glb` (~75 KB geometry) + `models/hq/<sp>_{skin,nrm,atlas,atlas_a}.jpg` (~1.2 MB), fetched only when
that fish is needed on Ultra/High. Photo credits go in Settings > Credits (the `<p class="hint">High-quality fish skins…`
paragraph in index.html).

## Status (Nov 14 2026)

| | species |
|---|---|
| HQ done (24) | sm smallmouth, cr black crappie, br barramundi, sp spotted bass, pk northern pike, cf channel catfish, wa walleye, yp yellow perch, lt lake trout, bu burbot, ts giant snakehead, mu muskie (hand-traced `mask_poly`), hs striped snakehead, hb hampala barb (Commons photos), bg bluegill (photo skin on the 3D scan via `scan_hq.py`), **Amazon:** bp butterfly peacock bass, pr red-bellied piranha, rtc redtail catfish, wf wolf fish (Hoplias aimara), bt brook trout (iNat 150-obs set #257, photo was belly-up: flipped vertically, fingers cut off by the outline), ar silver arowana (iNat incl. non-research-grade, aquarium shot, graded from yellow to silver), ap arapaima (iNat non-research-grade #97, aquarium), rt rainbow trout (juvenile on a tray, iNat 150-obs #313), pb speckled peacock bass (Commons, CC BY-SA, `ccand` #3) |
| Scan, no HQ needed | lm largemouth (scan already photo-textured), gd golden largemouth (scan texture repainted natural gold, all settings) |
| No usable licensed photo yet | tm tiger muskie, ma mahseer (1 photo), rc Asian redtail catfish (Commons: none usable), fb giant featherback (one bent fish in a net), gg giant gourami (aquarium shots at angles only), py payara (iNat: 1 photo; Commons: a painted plate and a 1000-px juvenile aquarium shot only) — try Commons for these |
| Built, not shipped (no clear win) | first tries kept in overrides/old: ar #1 (dirty, leaf litter), ap #5 (crumpled tail), rt #97/#113 (leaves / washed-out) |

Rare species: drop the research-grade filter (`quality_grade`) in inat_candidates.py to get many more aquarium photos (check species by eye). Aquarium side shots work well.
Network: the cloud environment must allow `api.inaturalist.org`, `static.inaturalist.org`, `commons.wikimedia.org`, `upload.wikimedia.org`.
`commons_get.py` strips the `?utm_...` the API now adds to file URLs and fetches standard-width thumbs (1920/1280/960) from upload.wikimedia.org: odd widths redirect to thumb.wikimedia.org and originals get 429.
`get_orig.py` reads `$CD/<key>_meta.json` (default `cand`), e.g. `CD=cand150 python3 -I get_orig.py orig bt:257` for a bigger candidate set.
`spec_<key>.json` can also take `outline` + `band`: a hand-traced outline that GrabCut only refines within a band of that width (busy backgrounds: rtc, wf).
Pale/silvery fish photographed on the ground (trout, arowana, arapaima) tend to come out washed-out and lumpy; prefer vivid, fresh fish on a plain background.

Wikimedia Commons (`commons_get.py`, licences CC0/CC BY/CC BY-SA/PD) often has clean studio/specimen side photos when iNaturalist doesn't; it rate-limits hard, so batch requests and expect waits. CC BY-SA photos make the derived skin CC BY-SA: say so in the credits.
Photo skin on a scan: `python3 scan_hq.py <scan.glb> <body obj> <eye obj> <key> build` after `hq_fish.py build <key>` (needs the rectified photo in out/<key>).

Rule: only ship a fish if the in-game side-by-side clearly beats the current one. Otherwise leave it.
For species with no usable licensed photo, improve the existing model instead (colours, markings, eye) — don't force it.

## Setup (fresh cloud container)

```
pip install --break-system-packages bpy opencv-python-headless scipy pillow numpy   # bpy = Blender 5.x as a module
mkdir -p ~/hqwork && cd ~/hqwork && cp -r <repo>/tools/hq_fish/* .                 # work OUTSIDE the repo (big temp files)
cd test && npm i three@0.128.0 @gltf-transform/cli && cd ..                         # playwright + chromium are preinstalled
(cd <repo> && python3 -m http.server 8123 &)                                       # tests load the game from here
```

## Per species (key = the 2-3 letter code in SPECIES, e.g. `pb`)

1. **Photos**: `python3 -I inat_candidates.py "<Scientific name>" <key> cand 70` — iNaturalist research-grade,
   licences CC0 / CC BY / CC BY-SA only, every angle of each observation, metadata in `cand/<key>_meta.json`.
   (Hybrids etc.: drop the rank filter.) Never use Google Images or other copyrighted photos as skins — reference only.
2. **Rank**: `python3 -I score.py <key> cand work/top_<key>.jpg 12 <total length / depth>` → look at the sheet, pick
   the index of a clean photo: fish lying flat, side-on, whole body + tail visible, nothing over the side, not blurry,
   not underwater, not bleached. If the top 12 are bad, fetch more (150 observations) before settling.
3. **Full-size**: `python3 -I get_orig.py orig <key>:<index>`
4. **Cut-out + trace + straighten**: `./auto_run.sh <key> <index> cand '<overrides json>'`
   then view `out/<key>/check.jpg` (outline over the straightened fish) and `out/<key>/skin.jpg`.
   Fix with overrides (also saved as `overrides/ov_<key>.json`, `rect_<key>.txt` = fish box, `spec_<key>.json` =
   GrabCut hints `{"bg":[polys],"fg":[polys]}` in photo pixels):
   - `head`: "left"/"right" (which side the snout is)        - `snout`, `tbase`: [x,y] photo px if detected wrong
   - `eye_at`: [x,y], `eye_r`: px                             - `pec`: polygon (photo px) or `pec_uv` (on the skin)
   - `spans_top` / `spans_bot`: `[["d",u0,u1],...]` fin bases along the body (u: 0 tail base → 1 snout; read off
     check.jpg), with `"snap": false`                         - `head_bot`/`head_top`: polylines for jaw/nape
   - `paint_uv`: polygons on the straightened skin (u, t in 0..1) to paint out fins, hands, glare, debris
   - `occ`: polygons (photo px) hiding hands/clamps          - `specks`: px size for dirt removal
   - `grade`: `{"gain":[r,g,b],"sat":x,"contrast":x}` for washed-out photos      - `inset`, `bd_scale`
   Run species ONE AT A TIME (several in parallel ran the container out of memory).
5. **Species tables in `hq_fish.py`**: add the key to `SPEC` (which cross-section table + slimness), `IRIS_RATIO`,
   `IRIS_COL` (iris colours from reference photos), `BARBELS` if it has whiskers. Add a family in `auto_trace.py`
   (`FAM`/`FAMILY`) if it's a new body type. Existing cross-section tables: bass, bluegill, pike, catfish, trout,
   burbot, snakehead, knife.
6. **Build**: `python3 hq_fish.py build <key>[,<key2>...]` → `build/hq/<key>.glb` + jpgs, `build/fish_hq.blend`.
   Check in Cycles: `python3 render_hq.py build/fish_hq.blend work/r.png <keys> 24 400`.
7. **Into the game**: `npx gltf-transform draco build/hq/<key>.glb <repo>/models/hq/<key>.glb --quantize-position 14
   --quantize-normal 10 --quantize-texcoord 12`; copy `build/hq/<key>_*.jpg` to `<repo>/models/hq/`; add the key to
   `HQ_SPECIES`; add the photo credit (author, licence, iNaturalist link) to the credits paragraph.
8. **Check**: `cd test && node hqshot.js ../work/game.png <keys>` → old (left) vs HQ (right) in the real game engine;
   `node hqgame.js ../work/g.png` → quality switching, no errors (one ERR_FAILED for an external font is normal).
9. Ship only the clear wins; commit with author Edison (`git -c user.name=Edison -c user.email=<owner's email>`),
   push to main (Vercel deploys fishing.edisonlawby.com). Send Edison the before/after image.

## Lessons
- Photo choice is 80% of the result. Bad photo → stop and pick another rather than patch for an hour.
- Licensed photos are scarce for rare Asian/Amazon fish; check `score.py` sheets early and report gaps honestly.
- Common fixes: hands/clamps → `occ`; fins folded onto the body → `paint_uv`; outline dips under fins → `spans_*`;
  open mouth → `head_bot`; glare → choose another photo.
- `models/scans.glb` (largemouth/bluegill DigitalLife3D scans, CC BY-NC) stays as is.
