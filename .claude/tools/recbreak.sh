#!/bin/bash
# Record the next break on a channel, with Kodi's player events (inside the rig):
#   bash recbreak.sh CHANNEL_ID CHANNEL_NUMBER [LEAD_SECS]
# Tunes in LEAD+15 s before the break, records from LEAD s before it to 10 s after,
# then lists player events, black frames (>= 0.04 s) and silences (>= 0.1 s).
T=$(dirname "$0")
ID=$1; NUM=$2; LEAD=${3:-10}
read -r S E < <(python3 - "$ID" <<'PY'
import json, sys, time
d = json.load(open("/root/.kodi/userdata/addon_data/script.cablebox42/schedules/%s.json" % sys.argv[1]))
now = time.time() + 40
ents = d["entries"]
for i, e in enumerate(ents):
    if e["k"] != "show" and e["s"] > now and i and ents[i - 1]["k"] == "show":
        j = i
        while j < len(ents) and ents[j]["k"] != "show":
            j += 1
        print("%.3f %.3f" % (e["s"], ents[j]["s"]))
        break
PY
)
echo "break $(date -d @${S%.*} +%T) .. $(date -d @${E%.*} +%T)"
sleep $(python3 -c "print(max(0, $S - $LEAD - 22 - __import__('time').time()))")
kodi-send --action="ActivateWindow(home)" >/dev/null   # a TV already on switches off first
sleep 7
kodi-send --action="RunScript(script.cablebox42,watch,$NUM)" >/dev/null
sleep $(python3 -c "print(max(0, $S - $LEAD - __import__('time').time()))")
DUR=$(python3 -c "print(int($E - $S + $LEAD + 10))")
T0=$(date +%s.%N)
python3 "$T/notes.py" "$DUR" /root/test/brk.tsv &
ffmpeg -loglevel error -y -f x11grab -framerate 25 -video_size 1280x720 -i :9 -f pulse -i out.monitor -t "$DUR" \
  -vf scale=640:360 -c:v libx264 -preset ultrafast -c:a aac /root/test/brk.mp4
sleep 2
echo "rec t0 $T0 (break at +$(python3 -c "print(round($S - $T0, 2))") s)"
python3 - "$T0" <<'PY'
import sys
t0 = float(sys.argv[1])
rows = [l.rstrip("\n").split("\t") for l in open("/root/test/brk.tsv")]
stop = None
for t, m, end, f in rows:
    t = float(t)
    if m == "Player.OnStop":
        stop = (t, f)
    if m == "Player.OnAVStart":
        gap = ("  switch %.3f s after %s ended" % (t - stop[0], stop[1])) if stop else ""
        print("%7.2f  AVStart %-28s%s" % (t - t0, f[:28], gap))
        stop = None
PY
echo "-- black frames:"
ffmpeg -hide_banner -i /root/test/brk.mp4 -vf blackdetect=d=0.04:pix_th=0.10:pic_th=0.90 -an -f null - 2>&1 | grep -o 'black_start.*'
echo "-- silences:"
ffmpeg -hide_banner -i /root/test/brk.mp4 -af silencedetect=n=-50dB:d=0.1 -vn -f null - 2>&1 | grep -oE 'silence_end.*'
