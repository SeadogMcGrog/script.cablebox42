"""Chapter-mark breaks on screen (inside the rig, the TV on channel ACT_CH with the
"Act Show" episodes from rig/mkacts.sh: ten acts of 117-129 s, each one solid colour).
Films the screen (25 fps) around every break of the next MINUTES: the last frame
before a break must still be the act that ends (no frame of the next act), and the
first frame after it the next act (no frame of the one before).  Appends one line
per break to /root/break_frames.txt; prints a summary.

    python3 break_frames.py MINUTES [CHANNEL_ID]
"""
import json, os, subprocess, sys, time

D = "/root/.kodi/userdata/addon_data/script.cablebox42/schedules/"
OUT = "/root/break_frames.txt"
MARKS = [0, 121, 247, 369, 498, 619, 743, 864, 991, 1113]     # act starts (s), rig/mkacts.sh
PAL = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255),
       (255, 255, 255), (255, 165, 0), (128, 0, 128), (128, 128, 128)]
NAMES = "red lime blue yellow magenta cyan white orange purple gray".split()
W, H = 4, 2


def grab(start, secs, name):
    """ffmpeg filming the screen from wall time `start` for `secs`, in the background."""
    while time.time() < start:
        time.sleep(0.01)
    t0 = time.time()
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "x11grab", "-framerate", "25",
                          "-video_size", "1280x720", "-i", ":9", "-t", str(secs),
                          "-vf", "crop=640:320:320:110,scale=%d:%d:flags=area" % (W, H),
                          "-f", "rawvideo", "-pix_fmt", "rgb24", name])
    return p, t0


def labels(name):
    raw = open(name, "rb").read()
    n = W * H * 3
    out = []
    for i in range(0, len(raw) - n + 1, n):
        px = [tuple(raw[i + j:i + j + 3]) for j in range(0, n, 3)]
        lab = None
        for k, c in enumerate(PAL):
            if all(max(abs(a - b) for a, b in zip(p, c)) <= 60 for p in px):
                lab = k
                break
        out.append(lab)
    return out


def events(ch, t0, t1):
    ents = json.load(open(D + ch + ".json"))["entries"]
    ev = []
    for i, e in enumerate(ents):
        if e.get("k") != "show":
            continue
        o, end_o = float(e.get("o", 0)), float(e.get("o", 0)) + e["e"] - e["s"]
        nxt = ents[i + 1] if i + 1 < len(ents) else None
        if nxt and nxt.get("k") != "show" and round(end_o) in MARKS[1:] and abs(end_o - round(end_o)) < 0.01:
            ev.append(("end", e["e"], MARKS.index(round(end_o))))    # act (index) that would come next
        if o > 1 and round(o) in MARKS[1:] and abs(o - round(o)) < 0.01:
            ev.append(("start", e["s"], MARKS.index(round(o))))      # act that starts
    return sorted((x for x in ev if t0 < x[1] - 3 and x[1] + 3 < t1), key=lambda x: x[1])


def main():
    mins = float(sys.argv[1]) if len(sys.argv) > 1 else 25
    ch = sys.argv[2] if len(sys.argv) > 2 else "acts0050"
    now = time.time()
    evs = events(ch, now + 5, now + mins * 60)
    print("%d events in the next %g min" % (len(evs), mins))
    bad = 0
    for kind, t, act in evs:
        name = "/root/test/bf_%d.raw" % int(t)
        if kind == "end":
            p, g0 = grab(t - 3.0, 5.0, name)
        else:
            p, g0 = grab(t - 2.0, 5.0, name)
        p.wait()
        lab = labels(name)
        seq = "".join("." if x is None else "0123456789"[x] for x in lab)
        if kind == "end":
            wrong = act                   # the next act must not show before the break
            want = act - 1
        else:
            wrong = act - 1               # the act before must not show after the break
            want = act
        ok = wrong not in lab
        seen = want in lab
        if kind == "end" and seen:
            last = max(i for i, x in enumerate(lab) if x == want)
            note = "last %s frame at %+.2f s on the clock" % (NAMES[want], g0 + (last + 1) / 25.0 - t)
        elif kind == "start" and seen:
            first = min(i for i, x in enumerate(lab) if x == want)
            note = "first %s frame at %+.2f s on the clock" % (NAMES[want], g0 + first / 25.0 - t)
        else:
            note = "%s never seen" % NAMES[want]
        bad += not ok
        line = "%s %-5s act %d->%d %s  %s  %s" % (time.strftime("%H:%M:%S", time.localtime(t)), kind,
                                                 act - 1 if kind == "end" else act - 1, act,
                                                 "OK  " if ok else "FAIL", note, seq)
        print(line)
        open(OUT, "a").write(line + "\n")
        os.remove(name)
    print("PASS" if not bad and evs else "FAIL", "(%d of %d with a frame of the wrong act)" % (bad, len(evs)))


if __name__ == "__main__":
    main()
