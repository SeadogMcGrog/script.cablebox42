"""Open a file at a position in Kodi's own player on the N2 and log what Kodi's audio does for
SECS seconds (the 18 Nov DTS wedge and CableBox's audio watch).

    python .claude/tools/n2/dts_wedge.py NAME FILE POS_S [SECS]

Prints the SyncDTS line, layout errors per second, CableBox's 'audio watch' lines and whether
Kodi still answers; saves the log lines to n2/logs/dts/NAME.log.  Stops the player at the end."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import n2  # noqa: E402
import dts_starts as D  # noqa: E402

name, f, pos_s = sys.argv[1], sys.argv[2], float(sys.argv[3])
secs = float(sys.argv[4]) if len(sys.argv) > 4 else 20
start = D.log_size()
ms = int(round(pos_s * 1000))
h, ms = divmod(ms, 3600000)
m, ms = divmod(ms, 60000)
s, ms = divmod(ms, 1000)
t0 = time.time()
try:
    n2.rpc("Player.Open", {"item": {"file": f}, "options": {"resume": {"hours": h, "minutes": m, "seconds": s, "milliseconds": ms}}},
           timeout=15)
except Exception as exc:
    print("Player.Open: %s" % exc)
seen = 0
while time.time() - t0 < secs:
    time.sleep(1.0)
    new = D.log_since(start)
    lines = new.splitlines()
    for l in lines[seen:]:
        if "SyncDTS" in l or "audio watch" in l or "audio output was reset" in l or "SetSettingValue" in l:
            print("  %s" % l[11:23], l.split("> ", 1)[-1][:150].strip() if "> " in l else l[:150])
    seen = len(lines)
    try:
        ok = "answers" if n2.rpc("JSONRPC.Ping", timeout=2) == "pong" else "?"
        t = n2.labels("Player.Time").get("Player.Time")
    except Exception:
        ok, t = "NO ANSWER", "?"
    print("%5.1f s  layout errors so far %3d  Kodi %s  Player.Time %s" % (time.time() - t0, new.count(D.WEDGE), ok, t))
out = os.path.join(n2.ROOT, "logs", "dts", name + ".log")
open(out, "w", encoding="utf-8").write(D.log_since(start))
try:
    D.stop()
except Exception as exc:
    print("stop: %s" % exc)
print("passthrough now %s; log %s" % (D.passthrough(), out))
