"""The Program Guide channel in the rig (Kodi running, CableBox on the guide):
every channel of the lineup but the guide itself has a row with its number and
name, and kodi.log has no 'tick failed' line since CableBox started.

    python3 guide_check.py GUIDE_NUMBER        (inside the rig)

Tunes the guide (RunScript ... watch,N), waits for the rows, reads the list
through JSON-RPC (Container(50) labels via GUI.GetProperties is not exposed, so
it reads the window's list items with XBMC.GetInfoLabels over port 9090), then turns the TV off.
Ends PASS/FAIL.  Also: python3 guide_check.py --log  only scans the log.
"""
import json
import subprocess
import sys
import time
import socket

D = "/root/.kodi/userdata/addon_data/script.cablebox42"
LOG = "/root/.kodi/temp/kodi.log"


def rpc(method, params=None):
    """JSON-RPC over Kodi's TCP port 9090 (the rig has no web server)."""
    s = socket.create_connection(("127.0.0.1", 9090), 5)
    s.sendall(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode())
    buf, dec = b"", json.JSONDecoder()
    s.settimeout(5)
    while True:
        chunk = s.recv(65536)
        if not chunk:
            break
        buf += chunk
        try:
            obj, _end = dec.raw_decode(buf.decode("utf-8", "replace"))
        except ValueError:
            continue
        if obj.get("id") == 1:
            s.close()
            return obj.get("result")
        buf = b""                        # a notification: wait for our answer
    s.close()
    return None


def log_failures():
    try:
        lines = open(LOG, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return ["kodi.log not found"]
    start = max([i for i, l in enumerate(lines) if "CableBox" in l and "start" in l.lower()] or [0])
    return [l for l in lines if "tick failed" in l] + \
        [l for l in lines[start:] if "Traceback" in l and "cablebox42" in l]


def main():
    bad = []
    if "--log" not in sys.argv:
        num = int(sys.argv[1]) if len(sys.argv) > 1 else 2
        chans = json.load(open(D + "/channels.json"))["channels"]
        want = [c for c in chans if c.get("type") != "guide"]
        # the TV off first: in captions mode (Kodi's full-screen player under CableBox's
        # overlay dialog) Kodi refuses ActivateWindow(home) - "active modal dialogs" -
        # so it gets the Stop key, which CableBox takes as switching off
        for _i in range(20):
            on = (rpc("XBMC.GetInfoLabels", {"labels": ["Window(Home).Property(cablebox42.running)"]}) or {})
            if on.get("Window(Home).Property(cablebox42.running)") != "1":
                break
            subprocess.run(["kodi-send", "--action=Stop"], stdout=subprocess.DEVNULL)
            time.sleep(2)
        subprocess.run(["kodi-send", "--action=ActivateWindow(home)"], stdout=subprocess.DEVNULL)
        time.sleep(4)
        subprocess.run(["kodi-send", "--action=RunScript(script.cablebox42,watch,%d)" % num], stdout=subprocess.DEVNULL)
        rows = []
        for _i in range(180):            # right after a big plan the guide can take a while to fill
            time.sleep(1)
            n = rpc("XBMC.GetInfoLabels", {"labels": ["Container(50).NumItems"]}) or {}
            if str(n.get("Container(50).NumItems", "0")).isdigit() and int(n["Container(50).NumItems"]) >= len(want):
                break
        n = int((rpc("XBMC.GetInfoLabels", {"labels": ["Container(50).NumItems"]}) or {}).get(
            "Container(50).NumItems", "0") or 0)
        for i in range(n):
            r = rpc("XBMC.GetInfoLabels", {"labels": ["Container(50).ListItemAbsolute(%d).Label" % i,
                                                      "Container(50).ListItemAbsolute(%d).Label2" % i,
                                                      "Container(50).ListItemAbsolute(%d).Property(c1)" % i]}) or {}
            rows.append([r.get(k, "") for k in sorted(r)])
        got = {}
        for r in rows:
            vals = dict(zip(("label", "label2", "c1"), (r[0], r[1], r[2]))) if len(r) == 3 else {}
            got[vals.get("label")] = vals
        for c in want:
            row = got.get(str(c["number"]))
            if not row:
                bad.append("no guide row for channel %s %s" % (c["number"], c["name"]))
            elif not row.get("label2"):
                bad.append("channel %s's row has no name" % c["number"])
        print("guide rows: %d for %d channels" % (n, len(want)))
        for r in rows:
            print("  ", r)
        subprocess.run(["kodi-send", "--action=ActivateWindow(home)"], stdout=subprocess.DEVNULL)
    fails = log_failures()
    for l in fails[:5]:
        bad.append("log: " + l.strip()[:160])
    if len(fails) > 5:
        bad.append("log: ... %d lines in all" % len(fails))
    for b in bad:
        print("FAIL", b)
    print("PASS" if not bad else "FAIL")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
