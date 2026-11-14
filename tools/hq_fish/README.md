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
| HQ done (11) | sm smallmouth, cr black crappie, br barramundi, sp spotted bass, pk northern pike, cf channel catfish, wa walleye, yp yellow perch, lt lake trout, bu burbot, ts giant snakehead |
| Keep 3D scan, upgrade skin only | lm largemouth, gd golden largemouth (recolour of lm), bg bluegill — the pipeline's own body came out worse than the scans (blocky head). Plan: keep the scan mesh (models/scans.glb) and project a licensed photo skin onto it in Blender; gd = better gold recolour |
| Tried, no usable photo yet | mu muskie (pale/scratched), tm tiger muskie (only 9 photos, head crops), bt brook trout + rt rainbow trout (not ranked yet, many photos exist — easy next win), hs striped snakehead (doubled head; try another photo), gg giant gourami (damaged fish), hb hampala (red clamp over body), ma mahseer (1 photo), rc Asian redtail catfish (0), fb giant featherback Chitala lopis (0) |
| Not started | Amazon: pb speckled peacock bass, bp butterfly peacock bass, pr red-bellied piranha, py payara, ar silver arowana, rtc redtail catfish, wf wolf fish (Hoplias aimara), ap arapaima |

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
