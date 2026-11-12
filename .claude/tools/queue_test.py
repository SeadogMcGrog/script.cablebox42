"""Queue-ahead safety checks in the rig (TV must be off; takes ~3 minutes):
    python3 queue_test.py zap|back|refresh
zap:     tune Keystone (3), and 5 s before a spot ends (its successor already queued)
         press Up to Beacon (4); for 40 s every file Kodi plays must be Beacon's planned one.
back:    the same, but press Back: for 30 s nothing may play.
refresh: the same, but Tools > Refresh schedules runs in the TV's process stand-in: the
         schedule file is rewritten with the following spot swapped; Kodi must play the
         new plan's spot at that slot."""
import json
import os
import socket
import subprocess
import sys
import time

SCHED = "/root/.kodi/userdata/addon_data/script.cablebox42/schedules/%s.json"
MODE = sys.argv[1]


def rpc(method, params=None):
    s = socket.create_connection(("127.0.0.1", 9090), 2)
    s.sendall(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode())
    buf = b""
    dec = json.JSONDecoder()
    while True:
        buf += s.recv(65536)
        try:
            txt = buf.decode()
            i = 0
            while i < len(txt):
                obj, n = dec.raw_decode(txt[i:].lstrip())
                i += n + (len(txt[i:]) - len(txt[i:].lstrip()))
                if obj.get("id") == 1:
                    s.close()
                    return obj.get("result")
        except ValueError:
            continue


def playing():
    act = rpc("Player.GetActivePlayers") or []
    vid = [p for p in act if p.get("type") == "video"]
    if not vid:
        return None
    it = rpc("Player.GetItem", {"playerid": vid[0]["playerid"], "properties": ["file"]}) or {}
    return (it.get("item") or {}).get("file")


def entry_at(ch, t):
    for e in json.load(open(SCHED % ch))["entries"]:
        if e["s"] <= t < e["e"]:
            return e


def send(a):
    subprocess.call(["kodi-send", "--action=%s" % a], stdout=subprocess.DEVNULL)


# a spot on Keystone that ends in 40-120 s and is followed by another spot
now = time.time()
ents = json.load(open(SCHED % "keys0003"))["entries"]
cand = [(a, b) for a, b in zip(ents, ents[1:]) if a["k"] == "ad" and b["k"] == "ad" and a["e"] > now + 40]
a, b = cand[0]
print("spot %s ends %s, then %s" % (os.path.basename(a["p"]), time.strftime("%T", time.localtime(a["e"])),
                                    os.path.basename(b["p"])))
time.sleep(max(0, a["e"] - 25 - time.time()))
send("RunScript(script.cablebox42,watch,3)")
time.sleep(max(0, a["e"] - 5 - time.time()))
pl = rpc("Playlist.GetItems", {"playlistid": 1, "properties": ["file"]}) or {}
print("playlist 5 s before the end:", [os.path.basename(i["file"]) for i in pl.get("items", [])])
bad = 0
if MODE == "zap":
    send("Up")
    time.sleep(1.5)                      # the channel change itself
    t_end = time.time() + 40
    while time.time() < t_end:
        f = playing()
        e = entry_at("beac0004", time.time())
        want = e.get("p") if e else None
        if f and want and f != want and "static" not in f and "power_on" not in f:
            # allow the half-second around a slot change
            e2 = entry_at("beac0004", time.time() - 0.6)
            if not e2 or e2.get("p") != f:
                bad += 1
                print("%.1f MISMATCH playing %s, Beacon has %s" % (time.time() % 1000, f, want))
        if f and "keys" not in f and os.path.dirname(f) and f == b["p"] and (not want or want != f):
            pass
        time.sleep(0.5)
elif MODE == "back":
    send("Back")
    time.sleep(3)
    t_end = time.time() + 30
    while time.time() < t_end:
        f = playing()
        if f:
            bad += 1
            print("%.1f still playing %s" % (time.time() % 1000, f))
        time.sleep(0.5)
elif MODE == "refresh":
    d = json.load(open(SCHED % "keys0003"))
    for e in d["entries"]:
        if abs(e["s"] - b["s"]) < 0.01:
            pool = sorted(set(x["p"] for x in d["entries"] if x["k"] == "ad" and x["p"] not in (a["p"], b["p"])))
            print("replanning the next slot: %s -> %s" % (os.path.basename(e["p"]), os.path.basename(pool[0])))
            e["p"] = pool[0]
            new = pool[0]
    json.dump(d, open(SCHED % "keys0003", "w"))
    time.sleep(max(0, b["s"] + 2 - time.time()))
    f = playing()
    print("at the slot Kodi plays %s (plan: %s)" % (f and os.path.basename(f), os.path.basename(new)))
    bad += f != new
print("RESULT %s: %s" % (MODE, "PASS" if not bad else "FAIL (%d)" % bad))
send("ActivateWindow(home)")
