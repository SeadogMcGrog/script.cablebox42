#!/bin/bash
# Holidays and specials: the stage 2 rig cases, one after another (Git Bash, from script.cablebox42).
#   bash .claude/tools/hol_cases.sh ZIP
S=.claude/kodi21-test-vm.sh
R='python3 /mnt/g/CableBox42/script.cablebox42/.claude/tools/specials_rig.py'
zip=${1:?zip}
bash $S install "$zip" | tail -1

run() {   # run TITLE CASE TODAY [show args] -- [settings...]
  local title=$1 c=$2 today=$3; shift 3
  local args=()
  while [ $# -gt 0 ] && [ "$1" != "--" ]; do args+=("$1"); shift; done
  [ "$1" = "--" ] && shift
  echo "=================== $title"
  bash $S lineup .claude/tools/lineup-specials.json | tail -1
  bash $S sh "$R case $c" | tail -1
  bash $S setting horizon_hours=24 specials_today=$today rerun_today= summer_reruns=0 thanksgiving_genres= promos_on=false promo_every=1 "$@" | tail -1
  bash $S start | tail -1
  sleep 40
  bash $S sh "$R show 24 ${args[*]}" > ../rig/hol_case_$c.txt 2>&1
  grep -E "special:|\[|bookmark event|FAIL|PASS|planned to" ../rig/hol_case_$c.txt | awk '!/\[/ || ++n<=6 || /Station Break/' | cut -c1-120
  tail -1 ../rig/hol_case_$c.txt
}

run "Thanksgiving, Seinfeld all day on Keystone" thanksgiving 2026-11-26
echo "=================== a year later"
bash $S sh "$R aired" | tail -1
bash $S setting specials_today=2027-11-25 | tail -1
bash $S start | tail -1
sleep 40
bash $S sh "$R show 24" > ../rig/hol_case_thanksgiving2.txt 2>&1
grep -E "special:|\[|bookmark event|FAIL|PASS" ../rig/hol_case_thanksgiving2.txt | awk '!/\[/ || ++n<=4' | cut -c1-120

run "New Year's Eve 6 PM - 6 AM on Beacon (off-air 1-5 AM, pin at 6 AM)" nye 2026-12-31
grep -E "Thu 31 Dec 1[78]:|Thu 31 Dec 23:|Fri 01 Jan 0[0-6]:" ../rig/hol_case_nye.txt | grep -A40 "4 Beacon" | head -0
awk '/^4 Beacon/{f=1} /^6 /{f=0} f' ../rig/hol_case_nye.txt | grep -E "17:|18:00|23:30|00:00|00:30|01:00|04:30|05:30|06:00|08:30" | cut -c1-110

run "Christmas Day on three channels (broadcast day to 6 AM on the 26th)" christmas 2026-12-25 -- christmas_genres=Western
for n in 3 6 7; do awk "/^$n /{f=1;print} /^[0-9]+ /&&!/^$n /{f=0} f" ../rig/hol_case_christmas.txt | grep -E "Sat 26 Dec 0[56]:|special:|Fri 25 Dec (20|22|23):" | head -8 | cut -c1-110; done

run "Thanksgiving episodes only (Kid Stuff has none)" holiday 2026-11-26 --none=kids0007 -- thanksgiving_genres=Western
run "A June special on a channel with summer reruns" june 2026-06-15 -- summer_reruns=1 rerun_today=2026-06-15
grep -c "(R)" ../rig/hol_case_june.txt
