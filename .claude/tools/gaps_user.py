"""Step 0 on the maintainer's own (Windows Kodi) schedules, read-only.
python gaps_user.py ADDON_DATA_DIR HOURS"""
import json, os, sys, time, glob, collections

D, HOURS = sys.argv[1], float(sys.argv[2])
dur = json.load(open(os.path.join(D, "durations.json"), encoding="utf-8"))
chans = {c["id"]: c for c in json.load(open(os.path.join(D, "channels.json"), encoding="utf-8"))["channels"]}
now = time.time()
tot = collections.Counter()
per_item_gaps = []
unknown = set()
rows = []
for f in sorted(glob.glob(os.path.join(D, "schedules", "*.json"))):
    cid = os.path.basename(f)[:-5]
    c = chans.get(cid, {})
    ents = json.load(open(f, encoding="utf-8")).get("entries") or []
    ents = [e for e in ents if now <= e["s"] < now + HOURS * 3600]
    if not ents:
        continue
    brk = []
    st = collections.Counter()

    def flush():
        if not brk:
            return
        L = brk[-1]["e"] - brk[0]["s"]
        black, where, kinds = 0.0, [], ""
        for i, e in enumerate(brk):
            slot = e["e"] - e["s"]
            kinds += e["k"][0]
            if e.get("p") and e["k"] in ("ad", "bump", "clip"):
                r = dur.get(e["p"])
                if not r:
                    unknown.add(e["p"])
                    continue
                b = slot - (r - e.get("o", 0))
                if b > 0.005:
                    black += b
                    per_item_gaps.append(b)
                    where.append("start" if i == 0 else "end" if i == len(brk) - 1 else "mid")
                elif b < -0.05:
                    st["cut-off spots"] += 1
        st["breaks"] += 1
        st["break_s"] += L
        if black > 0.05:
            st["with leftover"] += 1
            st["leftover_s"] += black
            st["max"] = max(st["max"], black)
            for w in where:
                st["at " + w] += 1
            if black >= 4:
                st["leftover >= 4 s"] += 1
        for k in kinds:
            st["kind " + k] += 1
        brk[:] = []

    for e in ents:
        if e["k"] == "show":
            flush()
        elif e["k"] in ("guide", "weather", "offair"):
            flush()
        else:
            brk.append(e)
    flush()
    if st["breaks"]:
        rows.append((c.get("number"), c.get("name"), c.get("type"), st))
        tot.update({k: v for k, v in st.items() if k != "max"})
        tot["max"] = max(tot["max"], st["max"])

for n, name, typ, st in sorted(rows, key=lambda r: r[0] or 0):
    print("%3s %-22s %-8s breaks %3d  with leftover %3d  avg leftover/break %5.2f s  max %6.2f s  >=4s %2d  cut-off spots %3d  where s/m/e %d/%d/%d" % (
        n, (name or "")[:22], typ, st["breaks"], st["with leftover"], st["leftover_s"] / st["breaks"], st["max"],
        st["leftover >= 4 s"], st["cut-off spots"], st["at start"], st["at mid"], st["at end"]))
print("ALL: breaks %d, with leftover %d, leftover %.0f s of %.0f s of break time; max %.2f s" % (
    tot["breaks"], tot["with leftover"], tot["leftover_s"], tot["break_s"], tot["max"]))
g = sorted(per_item_gaps)
if g:
    print("per-item black gaps: n=%d median %.2f p90 %.2f max %.2f; >2s: %d" % (
        len(g), g[len(g) // 2], g[int(len(g) * .9)], g[-1], sum(1 for x in g if x > 2)))
print("kinds:", {k: v for k, v in tot.items() if k.startswith("kind")})
print("clips with no known duration in durations.json:", len(unknown), list(unknown)[:5])
ds = [v for k, v in dur.items() if "Commercials" in k]
print("commercials in durations.json: %d; whole-second lengths: %d; length spread: %s" % (
    len(ds), sum(1 for v in ds if abs(v - round(v)) < 0.005),
    collections.Counter(int(round(v / 5.0) * 5) for v in ds).most_common(8)))
