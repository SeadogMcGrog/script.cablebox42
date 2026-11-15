#!/bin/bash
# Stale library entries and missing files on air, in the rig (Git Bash, repo root):
#   bash .claude/tools/stale_check.sh ZIP OUT.txt
# Installs ZIP with lineup-stale.json (Comedy Corner: Comedy, Cheers excluded; Frontier: Westerns
# and dramas), makes the library list Seinfeld S01E03 twice (an old file name whose file is gone),
# plans 24 h and checks the old name is never planned (stale_check.py plan).  Then, on air: the
# programme on channel 3 pointed at the old name airs the real file; pointed at a file the library
# doesn't know, one stand-in fills the rest of the slot and is still on after tuning away and back.
# Cleans the library again at the end.  Summary lines are printed; everything goes to OUT.txt.
set -u
ZIP=$1; OUT=$2
S=.claude/kodi21-test-vm.sh
T=/mnt/g/CableBox42/script.cablebox42/.claude/tools
C="python3 $T/stale_check.py"
: > "$OUT"
r() { timeout 200 bash $S sh "$1" >> "$OUT" 2>&1; }
timeout 120 bash $S install "$ZIP" | tail -1
timeout 120 bash $S lineup .claude/tools/lineup-stale.json | tail -1
echo "== make" >> "$OUT"; r "$C make"
timeout 120 bash $S stop >/dev/null
r 'cd /root/.kodi/userdata/addon_data/script.cablebox42 && rm -rf schedules series.json unplayable.json'
timeout 120 bash $S setting horizon_hours=24 | tail -1
timeout 120 bash $S start >/dev/null
echo "== plan" >> "$OUT"
r "sleep 5; kodi-send --action='RunScript(script.cablebox42,watch,3)' >/dev/null; sleep 60; \
   kodi-send --action='ActivateWindow(home)' >/dev/null; sleep 3; $C plan"
for kind in real standin; do
  timeout 120 bash $S stop >/dev/null
  echo "== $kind" >> "$OUT"; r "$C inject $kind 3"
  timeout 120 bash $S start >/dev/null
  W=$(timeout 60 bash $S sh 'cat /tmp/stale_wait 2>/dev/null || echo 0' | tr -dc 0-9)
  echo "waiting ${W:-0} s for the slot" >> "$OUT"
  timeout 1500 bash $S sh "sleep 3; kodi-send --action='RunScript(script.cablebox42,watch,3)' >/dev/null; sleep $(( ${W:-0} + 30 )); $C verify $kind 3; $C playing" >> "$OUT" 2>&1
  if [ $kind = standin ]; then
    r "kodi-send --action=Up >/dev/null; sleep 12; $C playing; kodi-send --action=Down >/dev/null; sleep 15; $C playing"
  fi
  timeout 60 bash $S log 400 | grep -E "Missing file|stand-in|run Clean library|Traceback" >> "$OUT"
done
timeout 60 bash $S sh "kodi-send --action='ActivateWindow(home)' >/dev/null; sleep 3"
echo "== clean" >> "$OUT"; r "$C clean"
grep -E "^==|^PASS|^FAIL|^RESULT|^PLAYING|^injected" "$OUT" | cut -c1-240
P=$(grep "^RESULT" "$OUT" | tail -1 | cut -d' ' -f2-)
B=$(grep '^PLAYING' "$OUT" | tail -1 | cut -d' ' -f2-)   # back on channel 3 (a break may be on: check by eye)
echo "stand-in planned: $P"
echo "back on channel 3: $B $([ "$B" = "$P" ] && echo '(same)' || echo '(DIFFERENT)')"
echo "FAIL lines: $(grep -c '^FAIL' "$OUT")"
