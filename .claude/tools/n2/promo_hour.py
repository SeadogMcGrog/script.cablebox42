"""Promo audio gate, Step 2 (briefs/promo-audio-n2-test.md): CableBox's TV with promos and mixed house ads on.

    python .claude/tools/n2/promo_hour.py MINUTES_PER_CHANNEL CH,CH,... [TAG]

Turns the TV on at the first channel, types each next channel (three digits) every MINUTES, polls every
2 s (read-only): the playing file, the TV window's mode (video / promo / house / retro ...), System.FPS,
the audio codec, Kodi's pid.  Logs every change of file or mode, FPS while a card is up, and at the end
kodi.log's counts (layout errors, DTS misreads, audio watch, Traceback).  Turns the TV off at the end.
If Kodi restarts (pid change), the TV is opened again on the current channel, so the rest of the hour
still watches something.  A moment with another window and no file playing is logged (with the window).
Writes n2/logs/promo-audio/hour[-TAG].txt and hour[-TAG]-kodi.log (kodi.old.log included after a
restart).  Changes no setting."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import n2  # noqa: E402

try:                                          # file names with any character (a full-width quote stopped a run)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

per = float(sys.argv[1]) * 60
chans = [int(x) for x in sys.argv[2].split(",")]
TAG = ("-" + sys.argv[3]) if len(sys.argv) > 3 else ""
OUT = os.path.join(n2.ROOT, "logs", "promo-audio")
lines = []
fps_card, fps_video = [], []


def say(s):
    print(s, flush=True)
    lines.append(s)


def pid():
    return n2.ssh("pidof kodi.bin", check=False).decode().strip()


def tune(ch):
    for d in "%03d" % ch:
        n2.rpc("Input.ExecuteAction", {"action": "number" + d}, timeout=5)
        time.sleep(0.08)


since = time.strftime("%H:%M:%S")
pid0 = pid()
say("== promo hour from %s, %d min a channel: %s (Kodi pid %s)" % (since, per / 60, chans, pid0))
n2.rpc("Addons.ExecuteAddon", {"addonid": "script.cablebox42", "params": ["watch", str(chans[0])]})
t0 = time.time()
cur_ch, last, stalls = chans[0], None, 0
restarts, reopened_at = [], t0          # t0: the TV was just turned on
other_win = [None]


def tv_back(why):
    """Open the TV again on the current channel (Kodi restarted, or the TV window closed)."""
    global reopened_at, last
    reopened_at = time.time()
    try:
        n2.rpc("Addons.ExecuteAddon", {"addonid": "script.cablebox42", "params": ["watch", str(cur_ch)]})
        say("%7.1f  TV opened again on %d (%s)" % (time.time() - t0, cur_ch, why))
    except Exception as exc:
        say("%7.1f  TV could not be opened again (%s)" % (time.time() - t0, exc))
    last = None

say("%7.1f  TV on, channel %d" % (0, cur_ch))
for i, ch in enumerate(chans):
    if i:
        tune(ch)
        cur_ch = ch
        say("%7.1f  tune %d" % (time.time() - t0, ch))
    end = t0 + per * (i + 1)
    while time.time() < end:
        time.sleep(2)
        try:
            lab = n2.labels("Player.Filenameandpath", "Window.Property(mode)", "System.FPS", "VideoPlayer.AudioCodec",
                            "MusicPlayer.Codec", "System.CurrentWindow")
        except Exception as exc:
            stalls += 1
            say("%7.1f  Kodi not answering (%s)" % (time.time() - t0, exc))
            continue
        win = lab["System.CurrentWindow"]
        if not win.startswith("script") and not lab["Player.Filenameandpath"]:
            # between two items Kodi can report its busy dialog and no file: only a restart
            # (a new pid) reopens the TV; a "watch" sent while the TV is on takes it to Home
            if win != other_win[0]:
                say("%7.1f  ch %2d  window %r, no file playing" % (time.time() - t0, cur_ch, win))
                other_win[0] = win
            if time.time() - reopened_at > 60:
                p = pid()
                if p and p != pid0:
                    say("%7.1f  Kodi pid changed %s -> %s (a restart)" % (time.time() - t0, pid0, p))
                    restarts.append(time.strftime("%H:%M:%S"))
                    pid0 = p
                    time.sleep(15)                  # let Kodi's start-up settle
                    tv_back("after a Kodi restart")
                    continue
        else:
            other_win[0] = None
        mode = lab["Window.Property(mode)"]
        fps = float(lab["System.FPS"] or 0)
        (fps_card if mode in ("promo", "house", "retro", "station", "upnext") else fps_video).append(fps)
        key = (os.path.basename(lab["Player.Filenameandpath"]), mode)
        if key != last:
            say("%7.1f  ch %2d  %-8s %-50s audio=%-9s fps=%5.1f %s" % (
                time.time() - t0, cur_ch, mode or "-", key[0][:50], lab["VideoPlayer.AudioCodec"] or lab["MusicPlayer.Codec"],
                fps, "" if lab["System.CurrentWindow"].startswith("script") else lab["System.CurrentWindow"]))
            last = key
    p = pid()
    if p and p != pid0:
        say("%7.1f  Kodi pid changed %s -> %s (a restart)" % (time.time() - t0, pid0, p))
        restarts.append(time.strftime("%H:%M:%S"))
        pid0 = p
n2.rpc("Input.ExecuteAction", {"action": "stop"}, timeout=5)
say("%7.1f  TV off (Stop)" % (time.time() - t0))
time.sleep(3)
log = n2.read_log(None)
if restarts:                                  # the part before the restart is in kodi.old.log
    log = n2.ssh("cat %s" % n2.R_LOG.replace("kodi.log", "kodi.old.log"), check=False).decode("utf-8", "replace") + chr(10) + log
win = [l for l in log.splitlines() if l[11:19] >= since]


def count(s):
    return sum(s in l for l in win)


med = lambda xs: sorted(xs)[len(xs) // 2] if xs else 0  # noqa: E731
say("-- polls: %d with a card up (median FPS %.1f), %d otherwise (median FPS %.1f); Kodi not answering %d" % (
    len(fps_card), med(fps_card), len(fps_video), med(fps_video), stalls))
say("-- Kodi restarts: %s" % (", ".join(restarts) or "none"))
for s in ("requested channel layout", "syncword: 0x5b48fc8e", "audio watch", "Traceback", "DTS start",
          "Opened device \"hdmi", "Opened device \"surround71"):
    say("-- kodi.log %-30s %d" % (s, count(s)))
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "hour%s.txt" % TAG), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
with open(os.path.join(OUT, "hour%s-kodi.log" % TAG), "w", encoding="utf-8") as f:
    f.write("\n".join(win) + "\n")
