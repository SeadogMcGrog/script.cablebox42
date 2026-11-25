"""Open DTS files at many start points in plain Kodi on the N2 and record how Kodi's
passthrough parser reads the first frame (the 18 Nov wedge: syncword 0x5b48fc8e / 0xb1656a49).

    python .claude/tools/n2/dts_starts.py OUT N [SEED]      N starts per file, random positions
    python .claude/tools/n2/dts_starts.py OUT at FILE SECS   one start

Per start: Player.Open with resume at the position, 3 s, then the new kodi.log lines: the
SyncDTS line (kind, channels, syncword, framesize) and 'Unable to open the requested channel
layout'.  On a wedge it stops the player and runs the recovery CableBox's watchdog uses
(passthrough off 1 s, on again), then checks the errors stopped.  Never changes any other
setting; puts passthrough back to what it was on any exit.  Results: OUT.tsv in n2/logs/dts/."""
import os
import random
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import n2  # noqa: E402

FILES = ["/var/media/Elements/Kodi/TV Shows/Planet Earth II (2016)/Season 1/Planet Earth II - S01E03 - Jungles.mkv",
         "/var/media/Elements/Kodi/TV Shows/Earthflight (2011)/Earthflight (2011) S01E01.mkv"]
LOG = "/storage/.kodi/temp/kodi.log"
SYNC = re.compile(r"SyncDTS - (\S+(?: \S+)?) stream detected \((\d+) channels.*syncword: (0x[0-9a-f]+).*framesize (\d+)")
WEDGE = "Unable to open the requested channel layout"


def log_size():
    return int(n2.ssh("stat -c %%s %s" % LOG).decode().strip())


def log_since(pos):
    return n2.ssh("tail -c +%d %s" % (pos + 1, LOG)).decode("utf-8", "replace")


def passthrough():
    return n2.rpc("Settings.GetSettingValue", {"setting": "audiooutput.passthrough"})["value"]


def set_pt(v):
    n2.rpc("Settings.SetSettingValue", {"setting": "audiooutput.passthrough", "value": bool(v)})


def stop():
    for p in n2.rpc("Player.GetActivePlayers") or []:
        n2.rpc("Player.Stop", {"playerid": p["playerid"]})


def recover(orig_pt):
    """What the watchdog does: stop, passthrough off 1 s, on again; True if the errors stop."""
    stop()
    time.sleep(0.5)
    t0 = time.time()
    set_pt(False)
    time.sleep(1.0)
    set_pt(orig_pt)
    time.sleep(1.5)
    pos = log_size()
    time.sleep(2.0)
    n = log_since(pos).count(WEDGE)
    print("    recovery: passthrough off/on, %d layout errors in the 2 s after (%.1f s)" % (n, time.time() - t0))
    return n == 0


def one(f, secs, out, orig_pt):
    pos = log_size()
    h, rest = divmod(int(secs), 3600)
    m, s = divmod(rest, 60)
    n2.rpc("Player.Open", {"item": {"file": f},
                           "options": {"resume": {"hours": h, "minutes": m, "seconds": s, "milliseconds": 0}}})
    time.sleep(3.0)
    new = log_since(pos)
    m_ = SYNC.search(new)
    kind, ch, sw, fs = (m_.groups() if m_ else ("-", "-", "-", "-"))
    errs = new.count(WEDGE)
    bad = kind == "dts" and sw not in ("0x7ffe8001",)
    print("  %-14s %7.1f s  %-8s %2s ch  %s  frame %5s  layout errors %d%s"
          % (os.path.basename(f)[:14], secs, kind, ch, sw, fs, errs, "   <- BAD" if bad or errs else ""))
    rec = ""
    if errs:
        rec = "recovered" if recover(orig_pt) else "STILL STUCK"
    out.write("%s\t%.1f\t%s\t%s\t%s\t%s\t%d\t%s\n" % (os.path.basename(f), secs, kind, ch, sw, fs, errs, rec))
    out.flush()
    return errs, rec


def main():
    name = sys.argv[1]
    d = os.path.join(n2.ROOT, "logs", "dts")
    os.makedirs(d, exist_ok=True)
    orig_pt = passthrough()
    print("passthrough is %s" % orig_pt)
    try:
        with open(os.path.join(d, name + ".tsv"), "a") as out:
            if sys.argv[2] == "at":
                one(sys.argv[3], float(sys.argv[4]), out, orig_pt)
                return
            n = int(sys.argv[2])
            rnd = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 42)
            for f in FILES:
                for _i in range(n):
                    errs, rec = one(f, rnd.uniform(5, 3000), out, orig_pt)
                    if rec == "STILL STUCK":
                        print("stopping: the recovery didn't clear it")
                        return
    finally:
        stop()
        if passthrough() != orig_pt:
            set_pt(orig_pt)
        print("passthrough back to %s" % passthrough())


if __name__ == "__main__":
    main()
