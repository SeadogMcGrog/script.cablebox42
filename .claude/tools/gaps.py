"""Break gap checker for the test rig (run inside it):
    python3 /mnt/g/CableBox42/script.cablebox42/.claude/tools/gaps.py [HOURS] [-v]

For every break on every channel (first HOURS of each schedule, default 6):
break length, what its planned items really play (ffprobe), and the leftover
that would show as black.  Also flags a clip planned into a longer slot, a spot
repeated back to back, and a spot repeated before every other spot had a turn.
Ends with PASS/FAIL against break-gaps.md: no break leftover over 0.5 s."""
import collections
import glob
import json
import os
import subprocess
import sys
import time

D = "/root/.kodi/userdata/addon_data/script.cablebox42/schedules"
args = [a for a in sys.argv[1:] if not a.startswith("-")]
HOURS = float(args[0]) if args else 6
VERBOSE = "-v" in sys.argv
_real = {}


def real(p):
    if p not in _real:
        try:
            _real[p] = float(subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).strip())
        except Exception:
            _real[p] = None
    return _real[p]


def hm(ts):
    return time.strftime("%H:%M:%S", time.localtime(ts))


fails = []
summary = []
for f in sorted(glob.glob(D + "/*.json")):
    ents = json.load(open(f))["entries"]
    if not ents:
        continue
    t0 = ents[0]["s"]
    ents = [e for e in ents if e["s"] < t0 + HOURS * 3600]
    ch = os.path.basename(f)[:-5]
    print("\n==== %s  (%s .. %s, %d entries)" % (ch, hm(t0), hm(ents[-1]["e"]), len(ents)))
    holes = [(a["e"], b["s"]) for a, b in zip(ents, ents[1:]) if abs(b["s"] - a["e"]) > 0.01]
    if holes:
        fails.append("%s: %d holes between planned entries" % (ch, len(holes)))
    st = collections.Counter()
    # the channel's spot pool, as far as these hours show it (own promo clips aside)
    pool = set(e["p"] for e in ents if e["k"] == "ad" and e.get("p") and not e.get("pr"))
    worst = 0.0
    brk = []

    def flush():
        global worst
        if not brk:
            return
        L = brk[-1]["e"] - brk[0]["s"]
        items, black, where, notes = 0.0, 0.0, [], []
        seen = []
        for i, e in enumerate(brk):
            slot = e["e"] - e["s"]
            play = slot
            if e.get("p") and e["k"] in ("ad", "bump", "clip"):
                r = real(e["p"])
                if r:
                    play = min(slot, r - e.get("o", 0))
                    if slot - play > 0.5:
                        notes.append("short-in-long %s %.1f/%.1f" % (os.path.basename(e["p"]), play, slot))
                        st["short-in-long"] += 1
            if e["k"] == "ad" and e.get("p") and not e.get("pr"):
                if seen and seen[-1] == e["p"]:
                    notes.append("back-to-back %s" % os.path.basename(e["p"]))
                    st["back-to-back"] += 1
                if e["p"] in seen and len(set(seen)) < len(pool):
                    notes.append("early repeat %s" % os.path.basename(e["p"]))
                    st["early repeat"] += 1
                seen.append(e["p"])
            items += play
            b = slot - play
            if b > 0.005:
                black += b
                where.append("%s%d:%.2f" % (e["k"][0], i, b))
        st["breaks"] += 1
        if black > 0.5:
            st["leftover>0.5"] += 1
        worst = max(worst, black)
        if VERBOSE or black > 0.5 or notes:
            print("%s brk %6.1fs  items %7.2fs  leftover %5.2fs  [%s] kinds=%s %s" % (
                hm(brk[0]["s"]), L, items, black, " ".join(where),
                "".join(e["k"][0] for e in brk), "; ".join(notes)))
        brk[:] = []

    for e in ents:
        if e["k"] in ("show", "guide", "weather", "offair"):
            flush()
        else:
            brk.append(e)
    flush()
    line = "%s: %d breaks, %d with leftover > 0.5 s, worst %.2f s, short-in-long %d, back-to-back %d, early repeats %d" % (
        ch, st["breaks"], st["leftover>0.5"], worst, st["short-in-long"], st["back-to-back"], st["early repeat"])
    summary.append(line)
    if st["leftover>0.5"] or st["short-in-long"] or st["back-to-back"] or st["early repeat"]:
        fails.append(line)

print("\n==== summary (first %.0f h of each schedule)" % HOURS)
for s in summary:
    print(s)
print("PASS" if not fails else "FAIL:\n  " + "\n  ".join(fails))
