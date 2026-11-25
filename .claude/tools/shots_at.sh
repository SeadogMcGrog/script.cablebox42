#!/bin/bash
# Screenshots at given times (inside the rig):
#   bash shots_at.sh CH_NUM TUNE_AT PREFIX HH:MM:SS...
# Tunes CH_NUM at TUNE_AT (the TV switched off first), then saves
# /mnt/g/CableBox42/rig/PREFIX-HHMMSS.png at each time.
NUM=$1; TUNE=$2; PREFIX=$3; shift 3
wait_until() { local t; t=$(date -d "$1" +%s); local d=$((t - $(date +%s))); [ $d -gt 0 ] && sleep $d; }
wait_until "$TUNE"
kodi-send --action="ActivateWindow(home)" >/dev/null; sleep 6
kodi-send --action="RunScript(script.cablebox42,watch,$NUM)" >/dev/null
for at in "$@"; do
  wait_until "$at"
  xwd -root -silent -display :9 | convert xwd:- -resize 60% "/mnt/g/CableBox42/rig/$PREFIX-${at//:/}.png"
done
echo DONE
