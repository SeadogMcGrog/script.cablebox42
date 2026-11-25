#!/bin/bash
# nfo-titles Step 0 captures + house-breaks end-gap recording (inside the rig, one-off).
T=/mnt/g/CableBox42/script.cablebox42/.claude/tools
OUT=/mnt/g/CableBox42/rig
w() { local t; t=$(date -d "$1" +%s); local d=$((t - $(date +%s))); [ $d -gt 0 ] && sleep $d; }
shot() { xwd -root -silent -display :9 | convert xwd:- -resize 60% "$OUT/$1.png"; }
item() { python3 - "$1" <<'PY'
import json, socket, sys
def rpc(m, p):
    s = socket.create_connection(("127.0.0.1", 9090)); s.sendall(json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode())
    r = json.loads(s.recv(65536).decode()); s.close(); return r.get("result")
pl = [p for p in rpc("Player.GetActivePlayers", {}) or [] if p["type"] == "video"]
it = rpc("Player.GetItem", {"playerid": pl[0]["playerid"], "properties": ["title", "showtitle", "file"]}) if pl else {}
lab = rpc("XBMC.GetInfoLabels", {"labels": ["VideoPlayer.Title", "VideoPlayer.TVShowTitle", "Player.Title"]})
print(sys.argv[1], json.dumps(it.get("item") if it else None), json.dumps(lab))
PY
}
tune() { kodi-send --action="ActivateWindow(home)" >/dev/null; sleep 6; kodi-send --action="RunScript(script.cablebox42,watch,$1)" >/dev/null; }
w 06:29:20; tune 3
w 06:29:57; shot nfo-upnext
w 06:30:04; shot nfo-banner-dw; item doctor-who
w 06:30:50; tune 2
w 06:31:05; shot nfo-guide
w 06:31:40; tune 6
w 06:31:48; shot nfo-banner-movie; item movie
w 06:53:20; tune 4
w 06:53:50
python3 $T/notes.py 385 /root/test/endgap2.tsv &
ffmpeg -loglevel error -y -f x11grab -framerate 10 -video_size 1280x720 -i :9 -t 385 -vf scale=640:360 -c:v libx264 -preset ultrafast /root/test/endgap2.mp4 &
w 06:55:30; shot nfo-xpromo-dw
w 06:58:10; shot endgap2-house
w 06:59:30; shot endgap2-upnext
w 07:00:04; shot endgap2-show
wait
echo "-- black frames (>=0.04 s) in 06:53:50-07:00:15:"
ffmpeg -hide_banner -i /root/test/endgap2.mp4 -vf blackdetect=d=0.04:pix_th=0.10:pic_th=0.90 -an -f null - 2>&1 | grep -o "black_start.*"
grep AVStart /root/test/endgap2.tsv | tail -2
echo DONE
