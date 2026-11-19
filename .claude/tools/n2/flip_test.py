"""Fast channel flipping on the N2 with the TV on (the 18 Nov DTS wedge, ~all10 brief item 3).

    python .claude/tools/n2/flip_test.py NAME MINUTES SECS_PER_CHANNEL CH,CH,...

Types each channel as three digits (CableBox tunes at once), round and round the list,
for MINUTES.  Afterwards from kodi.log (and kodi.old.log if Kodi restarted): misread DTS
frames, 'Unable to open the requested channel layout', CableBox's 'DTS start: opened at 0'
and 'audio watch' lines, every SyncDTS/AC3 detection; and from polling every channel
change: Kodi answering, its pid (a restart), the playing file and whether its time moves.
Writes n2/logs/dts/NAME.txt and NAME-kodi.log.  Changes no setting."""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import n2  # noqa: E402
import dts_starts as D  # noqa: E402

name, minutes, per = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
chans = [int(x) for x in sys.argv[4].split(",")]
out_dir = os.path.join(n2.ROOT, "logs", "dts")
lines = []


def say(s):
    print(s)
    lines.append(s)


def pid():
    return n2.ssh("pidof kodi.bin", check=False).decode().strip()


pid0 = pid()
start = D.log_size()
t0 = time.time()
i = 0
stalls = 0
restarts = 0
last_file, last_time = None, None
while time.time() - t0 < minutes * 60:
    ch = chans[i % len(chans)]
    i += 1
    try:
        for d in "%03d" % ch:
            n2.rpc("Input.ExecuteAction", {"action": "number" + d}, timeout=5)
            time.sleep(0.08)
    except Exception as exc:
        say("%6.1f  tune %d: Kodi not answering (%s)" % (time.time() - t0, ch, exc))
    time.sleep(per)
    try:
        lab = n2.labels("Player.Filenameandpath", "Player.Time", "VideoPlayer.AudioCodec")
        f = os.path.basename(lab["Player.Filenameandpath"])
        say("%6.1f  ch %2d  %-55s %-9s %s" % (time.time() - t0, ch, f[:55], lab["VideoPlayer.AudioCodec"], lab["Player.Time"]))
    except Exception as exc:
        say("%6.1f  ch %2d  Kodi not answering (%s)" % (time.time() - t0, ch, exc))
        stalls += 1
    p = pid()
    if p and p != pid0:
        restarts += 1
        say("        Kodi restarted (pid %s -> %s)" % (pid0, p))
        pid0 = p
        start = 0
        time.sleep(30)                       # back on the TV (audiowatch.resume_tv)
log = n2.ssh("cat /storage/.kodi/temp/kodi.log", check=False).decode("utf-8", "replace")
old = n2.ssh("cat /storage/.kodi/temp/kodi.old.log", check=False).decode("utf-8", "replace") if restarts else ""
text = (old + log) if restarts else log[start:] if start <= len(log) else log
open(os.path.join(out_dir, name + "-kodi.log"), "w", encoding="utf-8").write(text)
syncs = re.findall(r"SyncDTS - (\S+(?: \S+)?) stream detected .*?syncword: (0x[0-9a-f]+)", text)
ac3 = len(re.findall(r"TrySyncAC3 - \S+ stream detected", text))
truehd = len(re.findall(r"TrueHD|SyncTrueHD", text))
bad = [s for s in syncs if s[0] == "dts" and s[1] not in ("0x7ffe8001",)]
say("")
say("%d channel changes in %.1f min, %.1f s each" % (i, (time.time() - t0) / 60, per))
say("DTS detections %d (%s), misread %d; AC3 detections %d; TrueHD lines %d"
    % (len(syncs), ", ".join("%s %s" % k for k in sorted(set(syncs)))[:200], len(bad), ac3, truehd))
say("layout errors %d; CableBox DTS opened-at-0 starts %d; audio watch lines %d; Kodi restarts %d; "
    "polls with no answer %d" % (text.count(D.WEDGE), text.count("DTS start: opened at 0"),
                                  text.count("audio watch"), restarts, stalls))
for l in text.splitlines():
    if "audio watch" in l or "DTS start: seek failed" in l:
        say("  " + l[11:23] + " " + l.split("> ", 1)[-1][:150])
open(os.path.join(out_dir, name + ".txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
