#!/bin/bash
# Which value of Kodi's "Ignore video extras on scan" BACKLOT needs (inside the rig, one-off):
#   bash extras_setting_test.sh true|false
# Removes the test film (and anything Kodi added from its folder) from Kodi's library,
# sets videolibrary.ignorevideoextras, scans, and reports what Kodi made of the folder:
# movies in the library, video versions/extras, and what CableBox's Extras listing sees.
VAL=${1:?true or false}
M=/root/library/movies/Test_Film_2001
SRC="/root/library/tv/Friends/Friends S01E01.mp4"
if [ ! -d "$M" ]; then
  mkdir -p "$M/Extras"
  cp "/root/library/movies/Second Wind (1991)/"*.mp4 "$M/Test_Film_2001.mp4"
  printf '<movie><title>Test Film</title><year>2001</year><genre>Drama</genre></movie>' > "$M/Test_Film_2001.nfo"
  ffmpeg -loglevel error -y -i "$SRC" -t 120 -c copy "$M/Extras/Making.Of.Test.Film.mp4"
  printf '<movie><title>The Making of Test Film</title></movie>' > "$M/Extras/Making.Of.Test.Film.nfo"
  ffmpeg -loglevel error -y -i "$SRC" -t 120 -c copy "$M/Extras/Behind_The_Scenes_No_Nfo.mp4"
fi
python3 - "$VAL" "$M" <<'PY'
import json, socket, sys, time
val, folder = sys.argv[1] == "true", sys.argv[2]
def rpc(m, p):
    s = socket.create_connection(("127.0.0.1", 9090)); s.sendall(json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode())
    buf = b""
    while True:
        buf += s.recv(65536)
        try:
            r = json.loads(buf.decode()); break
        except ValueError:
            continue
    s.close(); return r.get("result", r.get("error"))
def ours():
    ms = rpc("VideoLibrary.GetMovies", {"properties": ["file", "title"]}).get("movies", [])
    return [m for m in ms if m["file"].startswith(folder)]
for m in ours():
    rpc("VideoLibrary.RemoveMovie", {"movieid": m["movieid"]})
rpc("VideoLibrary.Clean", {"showdialogs": False}); time.sleep(4)
print("setting:", rpc("Settings.SetSettingValue", {"setting": "videolibrary.ignorevideoextras", "value": val}),
      rpc("Settings.GetSettingValue", {"setting": "videolibrary.ignorevideoextras"}))
rpc("VideoLibrary.Scan", {"directory": folder + "/", "showdialogs": False}); time.sleep(12)
ms = ours()
print("movies Kodi has from the folder:")
for m in ms:
    print("   ", repr(m["title"]), "<-", m["file"][len(folder) + 1:])
main = [m for m in ms if "/Extras/" not in m["file"]]
if main:
    d = rpc("VideoLibrary.GetMovieDetails", {"movieid": main[0]["movieid"], "properties": ["title"]})
    try:
        v = rpc("VideoLibrary.GetAvailableArt", {"item": {"movieid": main[0]["movieid"]}})
    except Exception:
        v = None
print("extras as movies of their own:", sum(1 for m in ms if "/Extras/" in m["file"]))
PY
sqlite3 /root/.kodi/userdata/Database/MyVideos131.db \
  "select f.strFilename, v.itemType, t.name from videoversion v join files f on f.idFile=v.idFile left join videoversiontype t on t.id=v.idType where f.idPath in (select idPath from path where strPath like '$M/Extras/%');" 2>&1 | sed 's/^/videoversion: /'
