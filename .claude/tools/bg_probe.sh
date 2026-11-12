#!/bin/bash
# Does the promo card drop its background picture when promo_bg is emptied while
# the card stays up?  (inside the rig)  bash bg_probe.sh CH_NUM TUNE_AT PROMO_ON_AT
NUM=$1; TUNE=$2; AT=$3
OUT=/mnt/g/CableBox42/rig
wait_until() { local t; t=$(date -d "$1" +%s); local d=$((t - $(date +%s))); [ $d -gt 0 ] && sleep $d; }
shot() { xwd -root -silent -display :9 | convert xwd:- -resize 50% "$OUT/bgp-$1.png"; }
wait_until "$TUNE"
kodi-send --action="ActivateWindow(home)" >/dev/null; sleep 6
kodi-send --action="RunScript(script.cablebox42,watch,$NUM)" >/dev/null
wait_until "$AT"; sleep 4; shot a-card
kodi-send --action="SetProperty(promo_bg,,13000)" >/dev/null; sleep 1.5; shot b-emptied
kodi-send --action="SetProperty(mode,card,13000)" >/dev/null; sleep 0.3
kodi-send --action="SetProperty(mode,promo,13000)" >/dev/null; sleep 1.5; shot c-flipped
echo DONE
