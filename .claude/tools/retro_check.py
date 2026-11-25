"""Retro-ad checks on planned schedules, from now:
    python3 retro_check.py [HOURS] [-v] [--data ADDON_DATA] [--db MyVideos.db] [--all-builds]
In the rig by default (a fresh plan, or the files a refresh left).  --data reads any
CableBox data folder (a real Kodi's too; read-only), --db that Kodi's video database
(without one the videocassette-in-library check is skipped).  Blocks planned by an
earlier build ("cf" in the block differs from the newest block's) are kept by a
refresh until they've aired: they're set aside and counted, unless --all-builds.
- every break with retro ads: no ad twice, a running gag at most once
- the same ad not again on a channel within 2 hours
- kids' channels (Ad flavour Kids, or Auto -> Kids): only ads marked K, no videocassette
- each ad fits its time of day (or is a fallback 'any time' general ad) and season
- 'Now on videocassette' names a movie in Kodi's library (MyVideos*.db)
- no weather-claiming ad (stage 1 has no weather tie-in)
- video-themed ads (videocassette cards, ads marked "theme": "video"): at most one a
  break, never in two breaks in a row on a channel (a run of back-to-back breaks
  is one break), and at most 1 in 6 of a channel's retro ads on General channels,
  1 in 3 on Movies, 1 in 4 on the rest, over the whole check and in every 6-hour
  window ending at one
- at most 2 retro ads in a house break (4 on Movies channels) and 3 (Movies 4) in a whole run of
  back-to-back breaks (the check's "break": everything between two programmes, or up
  to a station ID card marked "sep"; a house break inside it ends at its station ID card)
- a long end gap (over 4 minutes) is a series of breaks ending on "sep" cards: each
  of those breaks at most 10 retro ads in all (ads.per_gap_break; the per-break 2 / run 3 caps
  are for other breaks); prints retro ads per 10
  minutes of long gap
- prints per channel: retro ads per break, station ID seconds per break, the share of breaks with a video ad,
  the share of video ads among retro ads, and the scheduler's own count of retro
  turns that found nothing to fit (schedule state "retro_stats", if the build keeps it)
- every retro card lasts its whole jingle plus START (0.45 s for Kodi to start the
  sound) and nothing starts before it ends: a jingle is never cut short
-v prints every break's retro ads.  Ends PASS/FAIL."""
import glob
import json
import wave
import os
import sqlite3
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
D = "/root/.kodi/userdata/addon_data/script.cablebox42"
DB = None
argv = sys.argv[1:]
for flag in ("--data", "--db"):
    if flag in argv:
        i = argv.index(flag)
        if flag == "--data":
            D = argv[i + 1]
        else:
            DB = argv[i + 1]
        del argv[i:i + 2]
args = [a for a in argv if not a.startswith("-")]
HOURS = float(args[0]) if args else 6
VERBOSE = "-v" in sys.argv
ALL_BUILDS = "--all-builds" in sys.argv
data = json.load(open(REPO + "/resources/ads/ads.json", encoding="utf-8"))
by = {a["id"]: a for a in data["ads"]}
chans = {c["id"]: c for c in json.load(open(D + "/channels.json", encoding="utf-8"))["channels"]}
if DB is None:
    found = sorted(glob.glob("/root/.kodi/userdata/Database/MyVideos*.db"))
    DB = found[-1] if found else None
movies = {r[0]: r[1] for r in sqlite3.connect(DB).execute("select idMovie, c00 from movie")} if DB else None
now = time.time()
START = 0.45
JINGLE = {"pitch": "jingle_pitch.wav", "kids": "jingle_kids.wav", "local": "jingle_local.wav",
          "psa": "jingle_psa.wav", "video": "jingle_video.wav"}
jlen = {}
for fmt, name in JINGLE.items():
    w = wave.open(REPO + "/resources/media/jingles/" + name, "rb")
    jlen[fmt] = w.getnframes() / float(w.getframerate())
    w.close()


def daypart(ts):
    h = time.localtime(ts).tm_hour
    return "morn" if 6 <= h < 11 else "day" if 11 <= h < 17 else "prime" if 17 <= h < 23 else "late"


def seasons(ts):
    lt = time.localtime(ts)
    m, d = lt.tm_mon, lt.tm_mday
    s = set()
    if (m == 11 and d >= 15) or (m == 12 and d <= 24):
        s.add("holiday")
    for name, months in (("winter", (12, 1, 2)), ("newyear", (1,)), ("spring", (3, 4, 5)), ("summer", (6, 7, 8)),
                         ("school", (8,)), ("fall", (9, 10, 11)), ("halloween", (10,))):
        if m in months:
            s.add(name)
    return s


def flavour(c):
    f = c.get("ad_flavour") or "auto"
    if f != "auto":
        return f
    if c.get("type") == "movies":
        return "M"
    g = [s.get("value") for s in c.get("sources", []) if s.get("type") == "tvgenre"]
    if g and any(x in ("Children", "Kids") for x in g) and all(x in ("Children", "Kids", "Animation", "Family") for x in g):
        return "K"
    if g and any(x in ("Sport", "Sports") for x in g):
        return "S"
    return "G"


def is_video(e):
    return e["ad"] == "video" or by.get(e["ad"], {}).get("theme") == "video"


def kids(c):
    f = c.get("ad_flavour") or "auto"
    if f != "auto":
        return f == "K"
    g = [s.get("value") for s in c.get("sources", []) if s.get("type") == "tvgenre"]
    return bool(g) and any(x in ("Children", "Kids") for x in g) and \
        all(x in ("Children", "Kids", "Animation", "Family") for x in g)


bad = []
stats = {"breaks with retro ads": 0, "retro ads": 0, "videocassette": 0, "off-time fallbacks": 0,
         "shortest margin s": 99.0}
kinds = {}
gaps = {}                           # channel -> [long gaps, their seconds, retro ads in them]
breaks = {}                         # channel -> [breaks, with retro ads, with a video-themed one, retro ads in them]
shares = {}                         # channel -> [video-themed, videocassette, all] in the window
WINDOW = 6 * 3600
for f in sorted(glob.glob(D + "/schedules/*.json")):
    cid = os.path.basename(f)[:-5]
    c = chans.get(cid)
    if not c:
        continue
    sched = json.load(open(f, encoding="utf-8"))
    ents = sched["entries"]
    # blocks planned by an earlier build (a refresh keeps what's on air): set aside
    blocks = sched.get("blocks") or []
    newest = blocks[-1].get("cf") if blocks else None
    old = [(b["s"], b["e"]) for b in blocks if b.get("cf") != newest]
    if old and not ALL_BUILDS:
        kept = [e for e in ents if any(s <= e["s"] < e2 for s, e2 in old)]
        if kept:
            stats["entries from an earlier build (set aside)"] = \
                stats.get("entries from an earlier build (set aside)", 0) + len(kept)
            last_old = max(e2 for _s, e2 in old)
            ents = [e for e in ents if e["s"] >= last_old]
    # long end gaps: retro ads per 10 minutes
    span, n_retro = None, 0
    for e in ents + [{"k": "show", "s": 0, "e": 0}]:
        if e["k"] in ("show", "clip", "offair", "guide", "weather"):
            if span and span[1] - span[0] > 240 and span[0] >= now:
                g = gaps.setdefault(cid, [0, 0.0, 0])
                g[0] += 1
                g[1] += span[1] - span[0]
                g[2] += n_retro
            span, n_retro = None, 0
            continue
        span = [e["s"], e["e"]] if span is None else [span[0], e["e"]]
        n_retro += e["k"] == "retro"
    seen = {}                      # ad key -> last start
    num, den = {"M": (1, 3), "G": (1, 6)}.get(flavour(c), (1, 4))
    prev = [False]                 # did the last break have a video-themed ad?
    after_sep = [False]            # the break before this one ended on a long gap's "sep" card
    cap, run_cap = (4, 4) if flavour(c) == "M" else (2, 3)
    gap_cap = max(10, cap)          # one of a long gap's breaks (ads.per_gap_break)
    hist = []                      # (start, video-themed?) of every retro ad
    brk = []

    def check(brk):
        if not brk:
            return
        rs = [e for e in brk if e["k"] == "retro"]
        bk = breaks.setdefault(cid, [0, 0, 0, 0, 0.0])   # breaks, with retro ads, with a video ad, retro ads, ID s
        if brk[0]["s"] >= now:
            bk[4] += sum(e["e"] - e["s"] for e in brk if e["k"] == "card" and e.get("sub") == "id")
            sub, n_sub = [], 0
            for j, e in enumerate(brk):
                n_sub += e["k"] == "retro"
                if e["k"] == "card" and (j + 1 == len(brk) or brk[j + 1]["k"] != "card"):
                    sub.append(n_sub)
                    n_sub = 0
            sub.append(n_sub)
            when = time.strftime("%H:%M", time.localtime(brk[0]["s"]))
            gap_brk = after_sep[0] or bool(brk[-1].get("sep"))
            if gap_brk and sum(sub) > gap_cap:
                bad.append("%s %s: %d retro ads in one of a long gap's breaks (cap %d) %s" % (
                    cid, when, sum(sub), gap_cap, sub))
            if not gap_brk and max(sub) > cap:
                bad.append("%s %s: %d retro ads in one house break (cap %d) %s" % (cid, when, max(sub), cap, sub))
            if not gap_brk and sum(sub) > run_cap:
                bad.append("%s %s: %d retro ads in a run of back-to-back breaks (cap %d) %s" % (
                    cid, when, sum(sub), run_cap, sub))
        vid = any(is_video(e) for e in rs)
        if brk[0]["s"] >= now:
            bk[0] += 1
            if vid and prev[0]:
                bad.append("%s %s: a video-themed ad in two breaks in a row" % (
                    cid, time.strftime("%H:%M", time.localtime(brk[0]["s"]))))
        prev[0] = vid
        if not rs:
            return
        stats["breaks with retro ads"] += 1
        keys = [("V%s" % e.get("mv")) if e["ad"] == "video" else e["ad"] for e in rs]
        if len(keys) != len(set(keys)):
            bad.append("%s %s: an ad twice in one break %s" % (cid, time.strftime("%H:%M", time.localtime(rs[0]["s"])), keys))
        vids = [k for k, e in zip(keys, rs) if is_video(e)]
        if brk[0]["s"] >= now:
            bk[1] += 1
            bk[2] += bool(vids)
            bk[3] += len(rs)
        if len(vids) > 1:
            bad.append("%s %s: %d video-themed ads in one break %s" % (
                cid, time.strftime("%H:%M", time.localtime(rs[0]["s"])), len(vids), vids))
        gags = [by[e["ad"]].get("gag") for e in rs if e["ad"] in by and by[e["ad"]].get("gag")]
        if len(gags) != len(set(gags)):
            bad.append("%s: a running gag twice in one break %s" % (cid, gags))
        if VERBOSE:
            print(cid, time.strftime("%a %H:%M", time.localtime(brk[0]["s"])),
                  " ".join(("%s%s:%.0fs" % (e["k"], "/" + str(e.get("ad") or e.get("h") or e.get("sub") or ""),
                                            e["e"] - e["s"])) for e in brk))

    for j, e in enumerate(ents):
        if e["k"] == "retro" and e["s"] >= now:
            fmt = "video" if e["ad"] == "video" else by.get(e["ad"], {}).get("fmt", "pitch")
            room = e["e"] - e["s"] - jlen[fmt]
            stats["shortest margin s"] = round(min(stats["shortest margin s"], room), 2)
            if room < START - 0.01:
                bad.append("%s %s: %s card %.2f s for a %.2f s jingle" % (
                    cid, time.strftime("%H:%M:%S", time.localtime(e["s"])), e["ad"], e["e"] - e["s"], jlen[fmt]))
            if j + 1 < len(ents) and ents[j + 1]["s"] < e["e"] - 0.01:
                bad.append("%s: the item after %s starts before its card ends" % (cid, e["ad"]))
        if e["k"] in ("show", "clip", "offair", "guide", "weather"):
            if e["s"] >= now - 3 * 3600:
                check(brk)
            brk = []
            after_sep[0] = False
            continue
        brk.append(e)
        if e.get("sep"):               # a long gap's card: the break ends here, the next one starts
            if e["s"] >= now - 3 * 3600:
                check(brk)
            brk = []
            after_sep[0] = True
        if e["k"] != "retro":
            continue
        k = ("V%s" % e.get("mv")) if e["ad"] == "video" else e["ad"]
        hist.append((e["s"], is_video(e)))
        if is_video(e) and e["s"] >= now:
            win = [v for s, v in hist if s > e["s"] - WINDOW]
            if sum(win) * den > len(win) * num:
                bad.append("%s %s: %d of the last %d retro ads (6 h) video-themed, cap %d in %d" % (
                    cid, time.strftime("%H:%M", time.localtime(e["s"])), sum(win), len(win), num, den))
        if k in seen and e["s"] - seen[k] < 7200 - 1 and e["s"] >= now:
            bad.append("%s: %s again after %.0f min" % (cid, k, (e["s"] - seen[k]) / 60))
        seen[k] = e["s"]
        if not (now <= e["s"] < now + HOURS * 3600):
            continue
        stats["retro ads"] += 1
        sh = shares.setdefault(cid, [0, 0, 0])
        sh[0] += is_video(e)
        sh[1] += e["ad"] == "video"
        sh[2] += 1
        kinds[e["ad"][0] if e["ad"] != "video" else "video"] = kinds.get(e["ad"][0] if e["ad"] != "video" else "video", 0) + 1
        if e["ad"] == "video":
            stats["videocassette"] += 1
            if movies is not None and e.get("mv") not in movies:
                bad.append("%s: videocassette movie %s not in the library" % (cid, e.get("mv")))
            if kids(c):
                bad.append("%s: videocassette on a kids' channel" % cid)
            continue
        ad = by.get(e["ad"])
        if not ad:
            bad.append("%s: unknown ad %s" % (cid, e["ad"]))
            continue
        if kids(c) and "K" not in ad["flav"]:
            bad.append("%s: %s (not K) on a kids' channel" % (cid, e["ad"]))
        if ad.get("claims"):
            bad.append("%s: %s claims the weather" % (cid, e["ad"]))
        if ad.get("season") and not seasons(e["s"]).intersection(ad["season"]):
            bad.append("%s: %s out of season" % (cid, e["ad"]))
        if (ad.get("time") and daypart(e["s"]) not in ad["time"]) or \
                (ad.get("hours") and not ad["hours"][0] <= time.localtime(e["s"]).tm_hour <= ad["hours"][1]):
            stats["off-time fallbacks"] += 1
    check(brk)
    sh = shares.get(cid)
    if sh and sh[0] * den > sh[2] * num:
        bad.append("%s: %d of %d retro ads video-themed, cap %d in %d" % (cid, sh[0], sh[2], num, den))
print(" ".join("%s: %s" % kv for kv in stats.items()), "| by kind:", kinds)
for cid in sorted(shares):
    v, vc, n = shares[cid]
    nb, nr, nv, na, ids = breaks.get(cid, [0, 0, 0, 0, 0.0])
    print("  %-10s %-2s breaks %3d (%3d with retro ads, %4.1f each; station ID %4.1f s a break)  retro ads %4d  videocassette %3d (%2.0f%%)  "
          "video-themed %3d (%2.0f%%)  breaks with a video ad %3d (%2.0f%% of breaks with retro ads)" % (
              cid, flavour(chans[cid]), nb, nr, float(na) / max(1, nr), ids / max(1, nb), n, vc, 100.0 * vc / n, v, 100.0 * v / n,
              nv, 100.0 * nv / max(1, nr)))
    try:
        st = json.load(open(D + "/schedules/%s.json" % cid))["state"].get("retro_stats")
    except Exception:
        st = None
    if st and st.get("turns"):
        t = st["turns"]
        print("  %-13s picker turns %d: an ad placed %d (%.0f%%), nothing fits %d (%.0f%%), "
              "an ad but no room left %d (%.0f%%), would repeat the last house ad %d" % (
                  "", t, st.get("placed", 0), 100.0 * st.get("placed", 0) / t, st.get("none", 0),
                  100.0 * st.get("none", 0) / t, st.get("long", 0), 100.0 * st.get("long", 0) / t, st.get("repeat", 0)))
for cid in sorted(gaps):
    n, secs, r = gaps[cid]
    print("  %-10s long end gaps (over 4 min): %d, %.0f min in all, %d retro ads = %.1f per 10 min of gap" % (
        cid, n, secs / 60, r, 600.0 * r / max(1.0, secs)))
for b in bad:
    print("FAIL", b)
print("PASS" if not bad and stats["retro ads"] else "FAIL")
