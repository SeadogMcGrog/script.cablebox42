"""Captions off must win over Kodi's per-file 'subtitles on' (rig; Kodi running, TV off):

    python3 cc_off_check.py setup          two .srt files next to every movie, and Kodi's own
                                           per-file memory set to subtitles on (each movie is
                                           played, subtitles switched on, stopped: Kodi saves it)
    python3 cc_off_check.py run off|on|unset [N] [--reshow]
                                           tune in mid-film on Drama Movies (6) N times (10);
                                           --reshow: switch Kodi's remembered track back on
                                           2.6 s (odd rounds) or 7 s (even) in, as Windows
                                           Kodi 21 did by itself; unset: no cc_on in
                                           state.json (never chosen), must act as off
    python3 cc_off_check.py clean          remove the .srt files and the per-file settings

The lineup must have Drama Movies on 6 and another channel on 4 (lineup-gaps.json).
'run' sets cc_on in state.json, starts the TV on 4, and each round waits for a moment the
film on 6 has 20+ s to go, presses Up (4 -> 6), and samples Kodi's subtitle state every
0.2 s for 14 s.  off: PASS when subtitles are never on screen for 2 s or more and are
off for the last 3 s, never on screen outside CableBox's black cover before a re-show,
and the CC setting (state.json) is still off after the round, every round (each time on screen is reported).  on: PASS when subtitles are on with a track of the
preferred kind (a subtitle file next to the video) from 5 s on, every round."""
import glob
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time

ADDON = "script.cablebox42"
DATA = "/root/.kodi/userdata/addon_data/%s/" % ADDON
SCHED = DATA + "schedules/%s.json"
DB = sorted(glob.glob("/root/.kodi/userdata/Database/MyVideos*.db"))[-1]
MOVIES = sorted(glob.glob("/root/library/movies/*/*.mp4"))
CH6 = "film0006"
SRTS = (".en.srt", ".Clean.srt")
DEBUG = "--debug" in sys.argv


class _Conn(object):
    """One JSON-RPC connection kept open: a connection per call while Kodi announces
    playback events crashed Kodi 21's Announce thread in the rig (signal 11)."""
    sock = None
    buf = ""
    n = 0


def _connect():
    _Conn.sock = socket.create_connection(("127.0.0.1", 9090), 10)
    _Conn.buf = ""


def _rpc(method, params=None):
    if _Conn.sock is None:
        _connect()
    _Conn.n += 1
    rid = _Conn.n
    _Conn.sock.sendall(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method,
                                   "params": params or {}}).encode())
    dec = json.JSONDecoder()
    while True:
        while True:                                   # whole objects in the buffer
            rest = _Conn.buf.lstrip()
            if not rest:
                _Conn.buf = ""
                break
            try:
                obj, n = dec.raw_decode(rest)
            except ValueError:
                _Conn.buf = rest
                break
            _Conn.buf = rest[n:]
            if obj.get("id") == rid:                  # announcements have no id: skipped
                return obj.get("result")
        chunk = _Conn.sock.recv(65536)
        if not chunk:
            raise OSError("closed")
        _Conn.buf += chunk.decode(errors="replace")


def rpc(method, params=None):
    for _i in range(3):
        try:
            return _rpc(method, params)
        except (socket.timeout, OSError):
            try:
                _Conn.sock.close()
            except Exception:
                pass
            _Conn.sock = None
            time.sleep(1)
    return None


def send(a):
    subprocess.call(["kodi-send", "--action=%s" % a], stdout=subprocess.DEVNULL)


def video_pid():
    for p in rpc("Player.GetActivePlayers") or []:
        if p.get("type") == "video":
            return p["playerid"]
    return None


def state():
    """(file, time s, subtitle enabled, current subtitle name)"""
    pid = video_pid()
    if pid is None:
        return None, 0, False, ""
    it = (rpc("Player.GetItem", {"playerid": pid, "properties": ["file"]}) or {}).get("item") or {}
    pr = rpc("Player.GetProperties", {"playerid": pid,
                                      "properties": ["subtitleenabled", "currentsubtitle", "time"]}) or {}
    t = pr.get("time") or {}
    secs = t.get("hours", 0) * 3600 + t.get("minutes", 0) * 60 + t.get("seconds", 0)
    cur = pr.get("currentsubtitle") or {}
    return it.get("file", ""), secs, bool(pr.get("subtitleenabled")), cur.get("name") or ""


def srt(label, length=1500):
    out = []
    for n, s in enumerate(range(0, length, 5)):
        h, m, x = s // 3600, s // 60 % 60, s % 60
        out.append("%d\n%02d:%02d:%02d,000 --> %02d:%02d:%02d,500\n%s line at %d s\n"
                   % (n + 1, h, m, x, h, m, x + 4, label, s))
    return "\n".join(out)


def setup():
    for f in MOVIES:
        base = f[:-4]
        for suffix in SRTS:
            with open(base + suffix, "w") as fh:
                fh.write(srt(suffix.strip(".").split(".")[0]))
    for f in MOVIES:
        rpc("Player.Open", {"item": {"file": f}})
        for _i in range(40):
            time.sleep(0.25)
            if video_pid() is not None and state()[1] > 1:
                break
        pid = video_pid()
        rpc("Player.SetSubtitle", {"playerid": pid, "subtitle": 0, "enable": True})
        time.sleep(1.5)
        print("%s: on=%s %s" % (os.path.basename(f), state()[2], state()[3]))
        rpc("Player.Stop", {"playerid": pid})
        time.sleep(2)
    con = sqlite3.connect(DB)
    rows = con.execute("SELECT f.strFilename, s.SubtitlesOn, s.SubtitleStream FROM settings s "
                       "JOIN files f ON f.idFile = s.idFile").fetchall()
    con.close()
    on = [r for r in rows if r[0].endswith(".mp4") and r[1]]
    print("Kodi's per-file memory, subtitles on: %d of %d movies" % (len(on), len(MOVIES)))
    sys.exit(0 if len(on) == len(MOVIES) else 1)


def clean():
    for f in MOVIES:
        for suffix in SRTS:
            if os.path.exists(f[:-4] + suffix):
                os.remove(f[:-4] + suffix)
    con = sqlite3.connect(DB)
    con.execute("DELETE FROM settings WHERE idFile IN (SELECT idFile FROM files WHERE strFilename LIKE '%.mp4' "
                "AND idPath IN (SELECT idPath FROM path WHERE strPath LIKE '/root/library/movies/%'))")
    con.commit()
    con.close()
    print("removed the .srt files and the movies' per-file settings")


def film_window(min_left=20, min_in=30):
    """(start of a tune-in moment, entry) when the film on 6 has min_left s to go and
    has been on min_in s (so the TV opens it partway in)."""
    now = time.time()
    for e in json.load(open(SCHED % CH6))["entries"]:
        if e.get("k") != "show" or "/movies/" not in e.get("p", ""):
            continue
        t = max(now + 1, e["s"] + min_in)
        if t + min_left <= e["e"]:
            return t, e
    return None, None


def set_cc(on):
    st_file = DATA + "state.json"
    st = json.load(open(st_file)) if os.path.exists(st_file) else {}
    if on is None:
        st.pop("cc_on", None)
    else:
        st["cc_on"] = on
    json.dump(st, open(st_file, "w"))


def cc_setting():
    """CableBox's saved CC setting (state.json's cc_on)."""
    st_file = DATA + "state.json"
    return (json.load(open(st_file)) if os.path.exists(st_file) else {}).get("cc_on")


def stretches(samples):
    """[(from, to)] seconds the subtitles were on screen."""
    out, cur = [], None
    for t, _f, _s, en, _n, *_c in samples:
        if en and cur is None:
            cur = [t, t]
        elif en:
            cur[1] = t
        elif cur is not None:
            out.append(tuple(cur))
            cur = None
    if cur is not None:
        out.append(tuple(cur))
    return out


def run(mode, rounds, reshow):
    """reshow: switch Kodi's remembered track (0) back on partway in, as Windows Kodi 21
    did ~2.6 s after CableBox's check; odd rounds at 2.6 s, even rounds at 7 s."""
    want_on = mode == "on"
    want_cc = None if mode == "unset" else want_on
    rpc("Player.Stop", {"playerid": 1})
    set_cc(want_cc)
    send("RunScript(%s,watch,4)" % ADDON)
    time.sleep(14)
    fails = 0
    for r in range(1, rounds + 1):
        t, e = film_window()
        while t is None:
            time.sleep(5)
            t, e = film_window()
        if t - time.time() > 0:
            time.sleep(t - time.time())
        send("Up")                                     # 4 -> 6
        t0 = time.time()
        samples = []
        film_at, reshown = None, None
        at = 2.6 if r % 2 else 7.0
        while time.time() - t0 < 14:
            f, secs, en, name = state()
            lab = rpc("XBMC.GetInfoLabels", {"labels": ["Window(Home).Property(cablebox42.cover)",
                                                        "System.CurrentWindow", "Window.Property(mode)"]}) or {}
            cov = lab.get("Window(Home).Property(cablebox42.cover)") == "1"   # CableBox's black cover (tv.set_cover)
            if en and not cov and DEBUG:
                print("   %.2f s: subtitles on, cover %r, window %r, mode %r" % (
                    time.time() - t0, lab.get("Window(Home).Property(cablebox42.cover)"), lab.get("System.CurrentWindow"),
                    lab.get("Window.Property(mode)")))
            now = time.time() - t0
            samples.append((now, f, secs, en, name, cov))
            if "/movies/" in (f or "") and film_at is None:
                film_at = now
            if reshow and film_at is not None and reshown is None and now - film_at >= at:
                pid = video_pid()
                rpc("Player.SetSubtitle", {"playerid": pid, "subtitle": 0, "enable": True})
                reshown = now
            time.sleep(0.2)
        film = [x for x in samples if "/movies/" in (x[1] or "")]
        if not film:
            print("round %d: the film never came up - skipped" % r)
            send("Down")
            time.sleep(4)
            continue
        start = film[-1][2] - (film[-1][0] - film[0][0])
        st = stretches(film)
        tail = [x for x in film if x[0] >= film[-1][0] - 3]
        if want_on:
            late = [x for x in film if x[0] >= 5]
            ok = bool(late) and all(x[3] and "external" in x[4].lower() for x in late)
            what = "on with %s" % (late[-1][4] if late else "-")
        else:
            # never stays: each time on screen is short, and off at the end
            longest = max([b - a for a, b in st] or [0])
            # at tune-in Kodi may switch on the subtitles it remembers for the file; the black
            # cover stays up until CableBox's first captions check: none of it visible
            seen = [x for x in film if x[3] and not x[5] and (reshown is None or x[0] < reshown)]
            ok = longest < 2.0 and not any(x[3] for x in tail) and not seen
            what = ", ".join("on %.1f-%.1f s" % ab for ab in st) or "never on screen"
            what += "; visible (not under the cover) before any re-show: %d samples" % len(seen)
            if reshown is not None:
                what += " (re-shown at %.1f s)" % reshown
        # the CC setting changes only with CableBox's own CC button / menu: never because
        # Kodi switched subtitles on by itself (its per-file memory, a re-show)
        cc = cc_setting()
        if cc != want_cc:
            ok = False
            what += "; CC SETTING IS NOW %s" % ("ON" if cc else cc)
        fails += not ok
        print("round %d: %s from %d s in | %s | %s" % (r, os.path.basename(e["p"]), start, what,
                                                       "ok" if ok else "FAIL"))
        send("Down")                                   # back to 4 for the next tune-in
        time.sleep(4)
    send("Back")                                       # TV off
    time.sleep(3)
    print("CC setting afterwards: %s" % {True: "on", False: "off"}.get(cc_setting(), cc_setting()))
    print("%s%s: %s (%d of %d rounds failed)" % (mode, " --reshow" if reshow else "",
                                                 "PASS" if not fails else "FAIL", fails, rounds))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "setup":
        setup()
    elif cmd == "clean":
        clean()
    elif cmd == "run" and len(sys.argv) > 2 and sys.argv[2] in ("off", "on", "unset"):
        args = [x for x in sys.argv[3:] if not x.startswith("--")]
        run(sys.argv[2], int(args[0]) if args else 10, "--reshow" in sys.argv)
    else:
        print(__doc__)
        sys.exit(2)
