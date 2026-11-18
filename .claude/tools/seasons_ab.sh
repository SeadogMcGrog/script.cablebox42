#!/bin/bash
# Holiday seasons A/B (Git Bash, from script.cablebox42): no seasons.json must plan exactly like
# the reference, on today's date and on pretend dates inside each season (hidden seasons_today).
#   bash .claude/tools/seasons_ab.sh REF_ZIP HOOK_REF_ZIP NEW_ZIP [DATE...]
# REF_ZIP: the build to match on today's date (no seasons_today needed).
# HOOK_REF_ZIP: the same build plus only the seasons_today hook (pretend dates).
# The rig's current CableBox data is saved once as the start (ab.sh save); every run starts from it.
AB=.claude/tools/ab.sh
ref=${1:?ref zip}; hook=${2:?hook ref zip}; new=${3:?new zip}; shift 3
dates=${*:-2026-10-20 2026-10-31 2026-11-26 2026-12-10 2026-12-24}
COMMON="seasons_on=true halloween_on=true thanksgiving_on=true christmas_on=true season_hold=true specials_today= horizon_hours=24"
bash $AB save
bash $AB run ref "$ref" $COMMON
bash $AB run new "$new" $COMMON seasons_today=
echo "== today's date: reference vs new"
bash $AB diff ref new
for d in $dates; do
  n=${d//-/}
  bash $AB run h$n "$hook" $COMMON seasons_today=$d
  bash $AB run n$n "$new" $COMMON seasons_today=$d
  echo "== $d: reference + hook vs new"
  bash $AB diff h$n n$n
  echo "== $d against today's date (the pretend date must change the plan)"
  bash $AB diff new n$n | grep -o "[0-9]* differ" | awk '{s+=$1} END {print "entries differing from today: " s+0}'
done
