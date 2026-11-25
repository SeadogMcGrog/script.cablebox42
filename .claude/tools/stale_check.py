"""Stale library entries and missing files on air (inside the rig, python3).

  stale_check.py make            copy Seinfeld S01E03 under an old name, scan, delete the copy
                                 (the library now lists S01E03 twice, one file gone; no Clean library)
  stale_check.py plan            the planned schedules never use the old name; the real S01E03
                                 airs once per round of Seinfeld; kodi.log has the 'run Clean library' line
  stale_check.py inject real|standin CH
                                 (Kodi stopped) point the programme on air now on channel CH at the
                                 old name (real: its library twin should air) or at a file the
                                 library doesn't know (standin)
  stale_check.py verify real|standin CH
                                 the rest of that slot was planned again at once: every remaining
                                 part points at the real file / at one stand-in from the channel's
                                 own shows (offsets running on), and kodi.log says so
  stale_check.py playing         the file Kodi plays now
  stale_check.py clean           remove the stale entry from the library again (Clean library)
Ends with PASS or FAIL lines."""
import json
import os
import re
import socket
import sys
import time

TV = "/root/library/tv/Seinfeld/"
REAL = TV + "Seinfeld S01E03.mp4"
OLD = TV + "Seinfeld - S01E03 - old name.mp4"
GONE = TV + "Seinfeld S01E09 never there.mp4"
DATA = "/root/.kodi/userdata/addon_data/script.cablebox42"
LOG = "/root/.kodi/temp/kodi.log"
FAILS = []


def rpc(method, params=None):
    s = socket.create_connection(("127.0.0.1", 9090), 5)
    s.sendall(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode())
    buf, dec = b"", json.JSONDecoder()
    s.settimeout(20)
    while True:
        chunk = s.recv(65536)
        if not chunk:
            break
        buf += chunk
        try:
            obj, _ = dec.raw_decode(buf.decode("utf-8"))
        except ValueError:
            continue
        if obj.get("id") == 1:
            s.close()
            return obj.get("result", {})
    s.close()
    return {}


def check(ok, what):
    print(("PASS " if ok else "FAIL ") + what)
    if not ok:
        FAILS.append(what)


def seinfeld_eps():
    shows = rpc("VideoLibrary.GetTVShows", {"properties": ["title"]}).get("tvshows", [])
    sid = next(s["tvshowid"] for s in shows if s["title"] == "Seinfeld")
    return rpc("VideoLibrary.GetEpisodes", {"tvshowid": sid, "properties": ["file", "season", "episode"]})["episodes"]


def make():
    import shutil
    shutil.copy(REAL, OLD)
    shutil.copy(REAL[:-4] + ".nfo", OLD[:-4] + ".nfo")
    rpc("VideoLibrary.Scan", {"directory": TV})
    for _ in range(60):
        time.sleep(1)
        if any(e["file"] == OLD for e in seinfeld_eps()):
            break
    time.sleep(3)
    os.remove(OLD)
    os.remove(OLD[:-4] + ".nfo")
    e3 = [e["file"] for e in seinfeld_eps() if (e["season"], e["episode"]) == (1, 3)]
    print("library S01E03:", e3)
    check(sorted(e3) == sorted([REAL, OLD]) and not os.path.exists(OLD),
          "the library lists S01E03 twice, the old name's file is gone")


def schedules():
    out = {}
    for fn in sorted(os.listdir(os.path.join(DATA, "schedules"))):
        with open(os.path.join(DATA, "schedules", fn)) as f:
            out[fn] = json.load(f)
    return out


def channels():
    with open(os.path.join(DATA, "channels.json")) as f:
        return json.load(f)["channels"]


def plan():
    sch = schedules()
    old = sum(1 for d in sch.values() for e in d["entries"] if e.get("p") == OLD)
    check(old == 0, "no planned entry uses the old name (%d)" % old)
    real_blocks = 0
    for fn, d in sch.items():
        seq = []
        for b in d["blocks"]:
            if b.get("t") == "Seinfeld":
                seq.append(b.get("lb"))
        real_blocks += seq.count("S01E03")
        rounds = [i for i, lb in enumerate(seq) if lb == "S01E03"]
        twice = [i for i in rounds if i + 1 < len(seq) and seq[i + 1] == "S01E03"]
        if seq:
            print("%s Seinfeld: %s" % (fn, " ".join(seq)))
        check(not twice, "%s: S01E03 never twice in a row" % fn)
        n = len(set(seq))
        for a, b in zip(rounds, rounds[1:]):
            check(b - a >= n - 1, "%s: S01E03 once per round of Seinfeld (%d apart, %d episodes)" % (fn, b - a, n))
    check(real_blocks >= 1, "the real S01E03 is planned (%d)" % real_blocks)
    with open(LOG, errors="replace") as f:
        lines = [ln for ln in f if "Library lists a missing file (run Clean library)" in ln]
    print("".join(lines).rstrip())
    check(any(OLD in ln for ln in lines), "kodi.log: 'Library lists a missing file (run Clean library): ...old name'")
    check(not any(REAL in ln for ln in lines), "the real file is never called missing")


def _sched_for(num):
    ch = next(c for c in channels() if c["number"] == int(num))
    return ch, os.path.join(DATA, "schedules", "%s.json" % ch["id"])


def inject(kind, num):
    ch, path = _sched_for(num)
    with open(path) as f:
        d = json.load(f)
    now = time.time() + 20                     # Kodi starts in the meantime
    # the show on air with 10 min left, else the next show (the caller waits for it: /tmp/stale_wait)
    b = next((b for b in d["blocks"] if b["e"] > now and b.get("k") == "show"
              and b["e"] - max(now, b["s"]) >= 600), None)
    if b is None:
        print("FAIL no show block to use: %s" % d["blocks"][:3])
        sys.exit(1)
    with open("/tmp/stale_wait", "w") as f:
        f.write("%d" % max(0, b["s"] - time.time() + 5))
    parts = [e for e in d["entries"] if e.get("k") == "show" and b["s"] <= e["s"] < b["e"]]
    new = OLD if kind == "real" else GONE
    for e in parts:
        e.update(p=new, t="Seinfeld", lb="S01E03" if kind == "real" else "S01E09")
        e.pop("cr", None)
    b.update(t="Seinfeld", lb="S01E03" if kind == "real" else "S01E09")
    with open(path, "w") as f:
        json.dump(d, f)
    with open("/tmp/stale_inject.json", "w") as f:
        json.dump({"s": b["s"], "e": b["e"], "parts": [[e["s"], e["e"], e.get("o", 0)] for e in parts]}, f)
    print("injected %s into %s's block %s-%s (%d parts)" % (new, ch["name"], b["s"], b["e"], len(parts)))


def verify(kind, num):
    ch, path = _sched_for(num)
    with open(path) as f:
        d = json.load(f)
    with open("/tmp/stale_inject.json") as f:
        inj = json.load(f)
    now = time.time()
    parts = [e for e in d["entries"] if e.get("k") == "show" and inj["s"] <= e["s"] < inj["e"]]
    left = [e for e in parts if e["e"] > now]
    bad = OLD if kind == "real" else GONE
    check(not any(e["p"] == bad for e in left), "no remaining part of the slot points at the missing file")
    paths = set(e["p"] for e in left)
    print("remaining parts:", [(round(e["s"] - now), e["p"].rsplit("/", 1)[-1], e.get("o"), e.get("t")) for e in left])
    with open(LOG, errors="replace") as f:
        log = f.read()
    if kind == "real":
        check(paths == {REAL}, "every remaining part airs the real file")
        check(all(abs(float(e.get("o", 0)) - float(p[2])) < 0.01
                  for e, p in zip(parts, inj["parts"])), "the real file keeps the parts' offsets")
        check("the library's other file for Seinfeld S01E03 airs instead" in log, "kodi.log says the real file airs")
    else:
        check(len(paths) == 1, "one stand-in for the whole rest of the slot")
        p = next(iter(paths))
        show = p.split("/tv/")[1].split("/")[0]
        check(show not in ("Cheers", "Bonanza", "Gunsmoke", "Act Show", "Credits Show", "Star Trek TNG"),
              "the stand-in is one of the channel's own comedies (%s), never excluded Cheers or another channel's genre" % show)
        done = [e for e in parts if e.get("si") == GONE]       # from the part on air when it was found
        offs = [float(e.get("o", 0)) for e in done]
        check(bool(offs) and offs == sorted(offs) and offs[0] == 0,
              "the stand-in plays on from part to part (offsets %s)" % offs)
        check(all(e in done for e in left), "every remaining part remembers what it stands in for")
        b = next(b for b in d["blocks"] if abs(b["s"] - inj["s"]) < 0.01)
        sub_t = left[0].get("t") if left else None             # the stand-in's own title (it may be another
        check(b.get("t") == sub_t, "the guide shows the stand-in (%s)" % b.get("t"))   # Seinfeld episode)
        check("stand-in for the rest of the slot" in log, "kodi.log names the stand-in")
    print("RESULT", p if kind != "real" else REAL)


def playing():
    it = rpc("Player.GetItem", {"playerid": 1, "properties": ["file"]}).get("item", {})
    print("PLAYING", it.get("file"))


def clean():
    rpc("VideoLibrary.Clean", {"showdialogs": False})
    time.sleep(10)
    e3 = [e["file"] for e in seinfeld_eps() if (e["season"], e["episode"]) == (1, 3)]
    check(e3 == [REAL], "Clean library left the real S01E03 only")


if __name__ == "__main__":
    cmd = sys.argv[1]
    {"make": make, "plan": plan, "clean": clean, "playing": playing}.get(cmd, lambda: None)() \
        if cmd in ("make", "plan", "clean", "playing") else \
        {"inject": inject, "verify": verify}[cmd](sys.argv[2], sys.argv[3])
    if cmd != "playing":
        print("FAIL" if FAILS else "PASS")
