"""House break checks in the rig (planned schedules, from now):
    python3 house_check.py [HOURS]
- cross-channel promos name a programme that starts at that time on that channel
- no house ad twice in one break (same system ad, same other channel, same show)
- no show promoted twice in a row on a channel
- system ads only for channels that exist (weather also needs a place)
- mix mode: at most one house ad per commercial break
- a gap (the run of back-to-back breaks between two programmes): the same promo target
  (show, own channel or another) not twice within 10 minutes nor more than 3 times; each
  system ad and each retro ad at most once; before off-air, the promo for the channel's
  first show after it ('tomorrow at 5:00') at most twice"""
import glob
import json
import os
import sys
import time

D = os.environ.get("CB_DATA", "/root/.kodi/userdata/addon_data/script.cablebox42")
HOURS = float(sys.argv[1]) if len(sys.argv) > 1 else 6
chans = {c["id"]: c for c in json.load(open(D + "/channels.json"))["channels"]}
types = set(c["type"] for c in chans.values())
sched = {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob(D + "/schedules/*.json")}
now = time.time()
bad = []
BREAK = ("retro", "promo", "house", "card", "bump", "ad")
SPACING, MAX_GAP, OFFAIR_MAX = 600, 3, 2
stats = {"gaps": 0, "long gaps": 0, "gaps before off-air": 0, "gap promos named": 0,
         "most promos for one show in a gap": 0, "house breaks": 0, "cross promos": 0, "cross checked": 0, "system ads": 0, "own promos": 0,
         "mixed breaks": 0}
for cid, d in sched.items():
    ents = [e for e in d["entries"] if now <= e["s"] < now + HOURS * 3600]
    brk, last_title = [], None

    def check(brk):
        if not brk:
            return
        house = [e for e in brk if e.get("h") or e["k"] == "retro"]     # retro ads count as house ads
        ads = [e for e in brk if e["k"] == "ad"]
        nxt = [e for e in brk if e["k"] == "card" and e.get("sub") == "next"]
        if nxt and nxt[-1]["e"] - nxt[-1]["s"] > 95:
            bad.append("%s %s: 'Up next' card of %.0f s" % (cid, time.strftime("%T", time.localtime(nxt[-1]["s"])),
                                                           nxt[-1]["e"] - nxt[-1]["s"]))
        if nxt and any(e["s"] > nxt[-1]["s"] for e in brk if e["k"] in ("house", "promo", "card")):
            bad.append("%s %s: 'Up next' isn't the last card" % (cid, time.strftime("%T", time.localtime(nxt[-1]["s"]))))
        if not house:
            return
        if ads:
            stats["mixed breaks"] += 1
            if len(house) > 1:
                bad.append("%s %s: %d house ads in one commercial break" % (cid, time.strftime("%T", time.localtime(brk[0]["s"])), len(house)))
        else:
            stats["house breaks"] += 1
        keys = []
        for e in house:
            if e["k"] == "house":
                keys.append(("sys", e["h"]))
            elif e.get("xc"):
                keys.append(("xc", e["xc"]))
            if e.get("t"):
                keys.append(("t", e["t"], e.get("xc")))
        dup = set(k for k in keys if keys.count(k) > 1)
        if dup:
            bad.append("%s %s: repeated in one break %s" % (cid, time.strftime("%T", time.localtime(brk[0]["s"])), dup))

    def key(e):
        return (e["k"], e.get("h"), e.get("xc")) if e["k"] == "house" or e.get("xc") else None

    prev_last = None
    for e in ents:
        if e["k"] == "show":
            check(brk)
            brk, prev_last = [], None
            continue
        if e["k"] == "card" and e.get("sub") == "id" and brk and not any(x["k"] == "ad" for x in brk):
            # a house break ends on its station ID; at a programme's end several run back to back
            hs = [x for x in brk if x.get("h")]
            if hs and prev_last is not None and key(hs[0]) == prev_last:
                bad.append("%s %s: house break starts with the ad the one before ended on" % (
                    cid, time.strftime("%T", time.localtime(hs[0]["s"]))))
            if hs:
                prev_last = key(hs[-1])
            check(brk + [e])
            brk = []
            continue
        brk.append(e)
        if e["k"] == "promo" and e.get("t"):
            if e["t"] == last_title:
                bad.append("%s %s: %s promoted twice in a row" % (cid, time.strftime("%T", time.localtime(e["s"])), e["t"]))
            last_title = e["t"]
            stats["own promos" if not e.get("xc") else "cross promos"] += 1
        elif e["k"] == "promo" and "pt" not in e:
            last_title = None            # named later (next planning pass or on air): it sits between
            if e.get("xc"):
                stats["cross promos"] += 1
        if e["k"] == "promo" and e.get("xc") and e.get("pt"):
            o = sched.get(e["xc"])
            blk = [b for b in (o or {}).get("blocks", []) if abs(b["s"] - e["pt"]) < 1]
            stats["cross checked"] += 1
            if not blk or blk[0]["t"] != e.get("t"):
                bad.append("%s: cross promo for %s at %s on %s doesn't match its schedule" % (
                    cid, e.get("t"), time.strftime("%T", time.localtime(e["pt"])), e["xc"]))
        if e["k"] == "house":
            stats["system ads"] += 1
            if e["h"] in ("guide", "weather") and e["h"] not in types:
                bad.append("%s: %s ad but no %s channel" % (cid, e["h"], e["h"]))
    check(brk)

    # variety across each gap
    allents = d["entries"]
    i = 0
    while i < len(allents):
        if allents[i]["k"] not in BREAK:
            i += 1
            continue
        j = i
        while j + 1 < len(allents) and allents[j + 1]["k"] in BREAK:
            j += 1
        gap = allents[i:j + 1]
        nxt = allents[j + 1] if j + 1 < len(allents) else None
        i = j + 1
        if not (now <= gap[0]["s"] < now + HOURS * 3600) or nxt is None:
            continue
        when = time.strftime("%T", time.localtime(gap[0]["s"]))
        stats["gaps"] += 1
        stats["long gaps"] += any(e.get("sep") for e in gap)
        named = [(e["t"], e["s"]) for e in gap if e["k"] == "promo" and e.get("t")]
        stats["gap promos named"] += len(named)
        cnt = {}
        for t, s in named:
            cnt[t] = cnt.get(t, 0) + 1
        if cnt:
            stats["most promos for one show in a gap"] = max(stats["most promos for one show in a gap"],
                                                            max(cnt.values()))
        for t, c in cnt.items():
            if c > MAX_GAP:
                bad.append("%s gap %s: %s promoted %d times (max %d)" % (cid, when, t, c, MAX_GAP))
        for k, (t, s) in enumerate(named):
            for t2, s2 in named[k + 1:]:
                if t2 == t and s2 - s < SPACING:
                    bad.append("%s gap %s: %s promoted at %s and again %.0f s later" % (
                        cid, when, t, time.strftime("%T", time.localtime(s)), s2 - s))
        for kind, keyf in (("system ad", lambda e: e["h"] if e["k"] == "house" else None),
                           ("retro ad", lambda e: (("V%s" % e.get("mv")) if e.get("ad") == "video" else e.get("ad"))
                            if e["k"] == "retro" else None)):
            keys = [keyf(e) for e in gap if keyf(e) is not None]
            dup = sorted(set(x for x in keys if keys.count(x) > 1), key=str)
            if dup:
                bad.append("%s gap %s: %s twice in one gap %s" % (cid, when, kind, dup))
        off = [b for b in d["blocks"] if b.get("k") == "offair" and b["s"] - 1 <= nxt["s"] < b["e"]]
        if off:
            stats["gaps before off-air"] += 1
            after = sorted((b for b in d["blocks"] if b.get("k") == "show" and b["s"] >= off[0]["e"] - 1),
                           key=lambda b: b["s"])
            if after:
                t = after[0]["t"]
                c = sum(1 for e in gap if e["k"] == "promo" and e.get("t") == t and not e.get("xc"))
                print("  %s off-air gap %s (%.0f min): '%s' after sign-on promoted %d times" % (
                    cid, when, (gap[-1]["e"] - gap[0]["s"]) / 60, t, c))
                if c > OFFAIR_MAX:
                    bad.append("%s gap %s: %s (after off-air) promoted %d times before sign-off (max %d)" % (
                        cid, when, t, c, OFFAIR_MAX))
for b in bad:
    print("  " + b)
print(stats)
print("PASS" if not bad else "FAIL: %d problems (listed above)" % len(bad))
