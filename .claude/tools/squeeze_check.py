"""Squeezed credits in the planned schedules (inside the rig, or --data DIR):
every TV episode that airs, where its squeeze starts and why - checked against
the rules on its own (squeezed-credits.md):

  chapters read and usable        -> the chapter rule's start (chapters.analyze "cr")
  no chapters / one / not read    -> the final 30 s, if the episode is 15 min or longer
                                     and plays to its natural end (no pinned-slot cut)
  movies, clips (no episode label)-> none
  last chapter over 3 min         -> none

    python3 squeeze_check.py [HOURS] [-v] [--data DIR]

Ends PASS/FAIL.  (Off-air: tv.squeeze_tick's guard is checked live, see CLAUDE.md.)
"""
import json
import os
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
for lib in ("/root/.kodi/addons/script.cablebox42/resources/lib",
            os.path.join(HERE, "..", "..", "resources", "lib")):
    if os.path.exists(os.path.join(lib, "chapters.py")):
        sys.path.insert(0, lib)
        break
import chapters  # noqa: E402  (no Kodi imports)

TAIL, MIN_LEN = 30.0, 15 * 60.0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    data = "/root/.kodi/userdata/addon_data/script.cablebox42"
    if "--data" in sys.argv:
        data = sys.argv[sys.argv.index("--data") + 1]
        args = [a for a in args if a != data]
    hours = float(args[0]) if args else 12
    verbose = "-v" in sys.argv
    load = lambda n, d: json.load(open(os.path.join(data, n))) if os.path.exists(os.path.join(data, n)) else d
    chs = load("chapters.json", {})
    durs = load("durations.json", {})
    now = time.time()
    seen, bad, why = Counter(), [], Counter()
    for fn in sorted(os.listdir(os.path.join(data, "schedules"))):
        sched = load(os.path.join("schedules", fn), {})
        ents = [e for e in sched.get("entries", []) if e.get("k") == "show"]
        # a programme = consecutive parts of one file in one block; its last part decides
        for i, e in enumerate(ents):
            nxt = ents[i + 1] if i + 1 < len(ents) else None
            if nxt and nxt.get("p") == e.get("p") and nxt["s"] - e["e"] < 1200 and nxt.get("o", 0) > e.get("o", 0):
                if e.get("cr") is not None:
                    bad.append("%s %s: cr on a part that isn't the last" % (fn, e.get("t")))
                continue
            if e["e"] < now or e["s"] > now + hours * 3600:
                continue
            if any(b["s"] <= now < b["e"] and b["s"] <= e["s"] < b["e"] for b in sched.get("blocks", [])):
                seen["on air now (kept as planned, not checked)"] += 1
                continue
            p, cr = e.get("p"), e.get("cr")
            full = durs.get(p, 0)
            o_end = float(e.get("o", 0)) + (e["e"] - e["s"])
            raw = chs.get(p)
            info = chapters.analyze(raw.get("d") or 0, raw.get("ch")) if raw and raw.get("ch") else None
            if not e.get("lb"):
                want, kind = None, "movie / clip: none"
            elif info is not None and info.get("why") not in ("no chapters", "one chapter"):
                c = info.get("cr")
                ok = c is not None and float(e.get("o", 0)) - 0.5 <= c < o_end - 5
                want = round(c, 2) if ok else None
                kind = "chapters: %s" % ("credits rule" if ok else "no squeeze (last chapter over 3 min / none)")
            elif full and full < MIN_LEN:
                want, kind = None, "no chapters, under 15 min: none"
            elif full and o_end < full - 1:
                want, kind = None, "no chapters, cut off by a pinned slot: none"
            elif not full:
                want, kind = cr, "length unknown (not checked)"
            else:
                want = round(full - TAIL, 2)
                kind = "no chapters%s: final 30 s" % ("" if raw else " (not read yet)")
            seen[kind] += 1
            if (want is None) != (cr is None) or (want is not None and abs(want - cr) > 1.0):
                bad.append("%s %s %s: squeeze at %s, rule says %s (%s)" % (
                    fn, e.get("t"), e.get("lb", ""), cr, want, kind))
            elif verbose:
                print("  %-14s %-24s %-8s cr=%-8s %s" % (fn[:14], (e.get("t") or "")[:24], e.get("lb", ""), cr, kind))
    print("programmes in the next %g h:" % hours)
    for k, n in sorted(seen.items()):
        print("  %4d  %s" % (n, k))
    for b in bad[:20]:
        print("FAIL", b)
    print("PASS" if not bad and seen else "FAIL")
    return 1 if bad or not seen else 0


if __name__ == "__main__":
    sys.exit(main())
