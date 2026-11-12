#!/bin/bash
# Record the promo bed under the next system ad on a channel (inside the rig):
#   bash bed_compare.sh CH_ID CH_NUM OUT.wav
# Tunes in 25 s before the next 'house' entry and records 10 s of the sound from
# 2 s into the card (Pulse null sink), then prints its loudness.
ID=$1; NUM=$2; OUT=$3
T=$(python3 - "$ID" <<'PY'
import json, sys, time
for e in json.load(open("/root/.kodi/userdata/addon_data/script.cablebox42/schedules/%s.json" % sys.argv[1]))["entries"]:
    if time.time() + 45 < e["s"] and e["k"] == "house":
        print("%.0f" % e["s"]); break
PY
)
echo "system ad at $(date -d @$T +%T)"
sleep $((T - $(date +%s) - 25))
kodi-send --action="ActivateWindow(home)" >/dev/null; sleep 6
kodi-send --action="RunScript(script.cablebox42,watch,$NUM)" >/dev/null
sleep $((T - $(date +%s) + 2))
ffmpeg -loglevel error -y -f pulse -i out.monitor -t 10 -ac 1 "$OUT"
kodi-send --action="ActivateWindow(home)" >/dev/null
ffmpeg -hide_banner -i "$OUT" -af volumedetect -f null - 2>&1 | grep -oE "(mean|max)_volume: [-0-9.]+ dB" | tr '\n' ' '; echo
