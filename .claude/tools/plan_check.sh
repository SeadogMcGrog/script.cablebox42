#!/bin/bash
# Plan a build for 24 hours from scratch and run every schedule check (Git Bash, repo root):
#   [SHORTS=2] [SKIP=0..3] bash .claude/tools/plan_check.sh ZIP LINEUP.json OUT.txt [refresh]   (SHORTS: the shorts_mode setting)
# Installs ZIP, loads LINEUP (house breaks, no commercials, retro ads on), plans 24 h by
# tuning channel 3, then runs retro_check.py, gaps.py, house_check.py, squeeze_check.py and guide_check.py
# (the guide's rows and 'tick failed' in kodi.log).  With 'refresh', it then runs
# Tools > Refresh schedules (what's on air stays as planned) and checks the files that
# refresh left.  Everything goes to OUT.txt; the summary lines are printed.
set -u
ZIP=$1; LINEUP=$2; OUT=$3; MODE=${4:-}
S=.claude/kodi21-test-vm.sh
T=/mnt/g/CableBox42/script.cablebox42/.claude/tools
W=$(wslpath_out() { echo "$1" | sed 's#^G:#/mnt/g#; s#^/g/#/mnt/g/#; s#\\#/#g'; }; wslpath_out "$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")")
timeout 120 bash $S install "$ZIP" | tail -1
timeout 120 bash $S lineup "$LINEUP" | tail -1
timeout 120 bash $S stop >/dev/null
timeout 60 bash $S sh 'cd /root/.kodi/userdata/addon_data/script.cablebox42 && rm -rf schedules series.json'
timeout 120 bash $S setting house_breaks=0 promos_on=false promo_extras=false summer_reruns=0 commercials_path= retro_ads=true promo_style=0 horizon_hours=24 shorts_mode=${SHORTS:-0} skip_short=${SKIP:-2} | tail -1
timeout 120 bash $S start >/dev/null
timeout 420 bash $S sh "sleep 5; kodi-send --action='RunScript(script.cablebox42,watch,3)' >/dev/null; sleep 60; \
  kodi-send --action='ActivateWindow(home)' >/dev/null; sleep 3; cd $T; \
  { echo '== retro_check (fresh 24 h plan)'; python3 retro_check.py 24; echo '== gaps'; python3 gaps.py 24 | tail -3; \
    echo '== house_check'; python3 house_check.py 24 | tail -8; echo '== squeeze_check'; python3 squeeze_check.py 24 | tail -9; \
    echo '== guide_check'; timeout 240 python3 guide_check.py 2; } > $W 2>&1"
if [ "$MODE" = refresh ]; then
  timeout 200 bash $S sh "kodi-send --action='RunScript(script.cablebox42,tool,refresh)' >/dev/null; sleep 45; \
    kodi-send --action='ActivateWindow(home)' >/dev/null; cd $T; \
    { echo '== retro_check (the files Tools > Refresh schedules left)'; python3 retro_check.py 24; \
      echo '== guide_check --log'; python3 guide_check.py --log; } >> $W 2>&1"
fi
grep -E "^==|^PASS|^FAIL|long end gaps|retro ads .*each|picker turns|earlier build|guide rows" "$OUT" | grep -v "^FAIL .*" | cut -c1-260
echo "FAIL lines: $(grep -c '^FAIL' "$OUT")"
