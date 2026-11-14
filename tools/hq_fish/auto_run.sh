#!/bin/bash
mkdir -p work trace out orig
# auto_run.sh <key> <meta index> [cand dir] [overrides json] : cut-out, auto trace, rectify -> out/<key>
K=$1; I=$2; CD=${3:-cand}; OV=${4:-$( [ -f overrides/ov_$K.json ] && cat overrides/ov_$K.json || echo '{}')}
F=$(python3 -I -c "import json;m=json.load(open('$CD/${MK:-$K}_meta.json'))[$I];print(m['file'])")
CR=$(python3 -I -c "import json;m=json.load(open('$CD/${MK:-$K}_meta.json'))[$I];a=m['attribution'];print(json.dumps({'by':a.split('(c) ')[-1].split(',')[0],'license':m['license'].upper().replace('CC-','CC ')+' 4.0','url':m['url']}))")
P=orig/$F
[ -f overrides/rect_$K.txt ] || python3 -I -c "
import cv2,sys;im=cv2.imread('$P');h,w=im.shape[:2];print(f'{int(w*.015)},{int(h*.015)},{int(w*.985)},{int(h*.985)}')" > overrides/rect_$K.txt
python3 -I seg.py $P work/m_$K.png $(cat overrides/rect_$K.txt) $( [ -f overrides/spec_$K.json ] && echo overrides/spec_$K.json ) >/dev/null
python3 -I auto_trace.py $P work/m_$K.png $K trace/$K.json "$CR" "$OV"
python3 -I rectify.py trace/$K.json out/$K | tail -1
