#!/bin/bash
# Holiday seasons: the rig cases (Git Bash, from script.cablebox42), each planned from the same saved
# start (ab.sh save) with and without a test seasons.json (seasons_rig.py CASES).
#   bash .claude/tools/seasons_cases.sh ZIP stage1|stage2|stage3
# Holiday material in the rig: genre Western (Bonanza, Gunsmoke); "west" = their programmes in the
# next 24 h on the seasons_today clock, per run.
AB=.claude/tools/ab.sh
S=.claude/kodi21-test-vm.sh
zip=${1:?zip}; stage=${2:?stage}
COMMON="seasons_on=true halloween_on=true thanksgiving_on=true christmas_on=true season_hold=true specials_today= horizon_hours=24 halloween_genres=Western thanksgiving_genres=Western christmas_genres=Western"

start_with() {   # start_with CASE: /root/test/ab_start_CASE = the saved start + that seasons.json
  bash $S sh "rm -rf /root/test/ab_start_$1 && cp -a /root/test/ab_start /root/test/ab_start_$1 && \
    python3 - <<'PY'
import json, sys
sys.path.insert(0, '/mnt/g/CableBox42/script.cablebox42/.claude/tools')
import seasons_rig
json.dump(seasons_rig.CASES['$1'], open('/root/test/ab_start_$1/seasons.json', 'w'))
PY
echo start $1"
}

west() {   # west RUN: Western programmes planned in the next 24 h
  bash $S sh "python3 - <<'PY'
import json, glob, time
t0 = time.time(); n = 0; tot = 0
for f in glob.glob('/root/test/ab_$1/*.json'):
    for e in json.load(open(f))['entries']:
        if e.get('k') == 'show' and t0 <= e['s'] < t0 + 86400:
            tot += 1
            n += e.get('t') in ('Bonanza', 'Gunsmoke')
print('$1: %d of %d programmes are Bonanza/Gunsmoke' % (n, tot))
PY"
}

run() {   # run NAME DATE [CASE]
  local name=$1 date=$2 case=${3:-}
  if [ -n "$case" ]; then AB_START=ab_start_$case bash $AB run $name "$zip" $COMMON seasons_today=$date | tail -1
  else bash $AB run $name "$zip" $COMMON seasons_today=$date | tail -1; fi
  west $name
}

total() {   # total A B: entries that differ, all channels
  bash $AB diff $1 $2 | grep -o "[0-9]* differ" | awk -v a=$1 -v b=$2 '{s+=$1} END {print a " vs " b ": " s+0 " entries differ"}'
}

bash $S sh "rm -f /root/test/ab_start/seasons.json; echo start has no seasons.json"   # every case starts from none
case $stage in
stage1)
  start_with early; start_with canada
  echo "== Halloween run-up from 15 September"
  run s0920 2026-09-20; run e0920 2026-09-20 early; total s0920 e0920
  run s1126 2026-11-26; run e1126 2026-11-26 early; total s1126 e1126
  echo "== Canadian Thanksgiving (genre Western)"
  run s1012 2026-10-12; run c1012 2026-10-12 canada; total s1012 c1012
  run c1126 2026-11-26 canada; total s1126 c1126
  run s1210 2026-12-10; run c1210 2026-12-10 canada; total s1210 c1210
  ;;
stage2)
  start_with festivus; start_with festivus_hold; start_with diwali
  echo "== Festivus: 23 Dec, 1 day, 2 days of run-up (genre Western), hold off"
  run s1221 2026-12-21; run f1221 2026-12-21 festivus; total s1221 f1221
  run s1223 2026-12-23; run f1223 2026-12-23 festivus; total s1223 f1223
  run s0704 2026-07-04; run f0704 2026-07-04 festivus; total s0704 f0704
  echo "== Festivus with Save for its season on, then off again (= the run without it above)"
  run g0704 2026-07-04 festivus_hold; total s0704 g0704
  run g1223 2026-12-23 festivus_hold; total f1223 g1223
  echo "== Diwali, dates typed for 2026 and 2027 only"
  run s1108 2026-11-08; run d1108 2026-11-08 diwali; total s1108 d1108
  run s2028 2028-11-08; run d2028 2028-11-08 diwali; total s2028 d2028
  ;;
stage3)
  echo "== Christmas Eve with one channel's seasons off (see the case's own notes)"
  ;;
esac
