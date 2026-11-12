#!/bin/bash
# nfo-titles Done-when captures (inside the rig, one-off, 2026-11-12).
OUT=/mnt/g/CableBox42/rig
w() { local t; t=$(date -d "$1" +%s); local d=$((t - $(date +%s))); [ $d -gt 0 ] && sleep $d; }
shot() { xwd -root -silent -display :9 | convert xwd:- -resize 60% "$OUT/nt-$1.png"; }
lab() { python3 - "$1" <<'PY'
import json, socket, sys
s = socket.create_connection(("127.0.0.1", 9090))
s.sendall(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "XBMC.GetInfoLabels", "params": {"labels": ["VideoPlayer.Title", "VideoPlayer.TVShowTitle", "Player.Title"]}}).encode())
print(sys.argv[1], json.loads(s.recv(65536).decode()).get("result"))
PY
}
w 07:24:20; kodi-send --action="ActivateWindow(home)" >/dev/null; sleep 6
kodi-send --action="RunScript(script.cablebox42,watch,4)" >/dev/null; sleep 1.2; lab turn-on
w 07:27:02; shot xpromo-tng
w 07:27:42; shot xpromo-movie
w 07:28:12; shot xpromo-dw2005
w 07:29:00; kodi-send --action=Down >/dev/null
w 07:29:08; lab commercial
w 07:29:57; shot upnext-tng
w 07:30:04; shot banner-tng; lab programme
w 07:31:00; kodi-send --action=Down >/dev/null
w 07:31:12; shot guide
kodi-send --action="ActivateWindow(home)" >/dev/null
echo DONE
