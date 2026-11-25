"""Replay a real Kodi's breaks through this repo's scheduler._fill, offline and read-only:
    python .claude/tools/fill_replay.py ADDON_DATA_DIR [HOURS]
Takes each break's length (and whether it ends a programme) from the existing
schedules, the channel's commercials and bumps from durations.json (folder names as in
settings.xml), and fills it again with the new code.  Prints the old and new leftover
(planned black: clips shorter than their slots, plus slots no clip covers)."""
import collections
import json
import os
import random
import sys
import tempfile
import types
import xml.etree.ElementTree as ET

TMP = tempfile.mkdtemp()


class Dummy(object):
    def __init__(self, *a, **k):
        pass

    def __call__(self, *a, **k):
        return Dummy()

    def __getattr__(self, name):
        return Dummy()

    def __str__(self):
        return TMP

    __fspath__ = __str__


def stub(name, **kw):
    m = types.ModuleType(name)
    m.__getattr__ = lambda attr: Dummy()
    for k, v in kw.items():
        setattr(m, k, v)
    sys.modules[name] = m


class _Addon(Dummy):
    def getAddonInfo(self, key):
        return TMP if key in ("profile", "path") else "script.cablebox42"

    def getSetting(self, key):
        return ""

    def getLocalizedString(self, i):
        return ""


stub("xbmc", LOGINFO=1, LOGDEBUG=0, LOGERROR=4, LOGWARNING=2, log=lambda *a, **k: None,
     translatePath=lambda p: TMP)
stub("xbmcvfs", translatePath=lambda p: TMP, exists=lambda p: False)
stub("xbmcaddon", Addon=_Addon)
stub("xbmcgui")
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "resources"))
from lib import scheduler  # noqa: E402

D = sys.argv[1]
HOURS = float(sys.argv[2]) if len(sys.argv) > 2 else 24
dur = json.load(open(os.path.join(D, "durations.json"), encoding="utf-8"))
cfg = {}
for s in ET.parse(os.path.join(D, "settings.xml")).getroot():
    cfg[s.get("id")] = s.text or ""


def pool(folder):
    if not folder:
        return []
    f = os.path.normcase(os.path.normpath(folder))
    return [{"path": p, "dur": d, "title": os.path.basename(p)} for p, d in dur.items()
            if 0 < d <= 600 and os.path.normcase(os.path.normpath(p)).startswith(f)]


ads_all, bumps_all = pool(cfg.get("commercials_path")), pool(cfg.get("bumps_path"))


class Fake(object):
    CARD_MIN, CARD_MAX, ABSORB = scheduler.ChannelSchedule.CARD_MIN, scheduler.ChannelSchedule.CARD_MAX, \
        scheduler.ChannelSchedule.ABSORB
    _pack = scheduler.ChannelSchedule._pack
    _fill = scheduler.ChannelSchedule._fill
    _add_promo = scheduler.ChannelSchedule._add_promo

    def __init__(self, promo_rate):
        self.data = {"entries": []}
        self.promo_rate = promo_rate

    def _add(self, s, e, kind, **kw):
        d = {"s": s, "e": e, "k": kind}
        d.update(kw)
        self.data["entries"].append(d)

    def _promo_for_break(self, t, room):
        return {"dur": 15.0} if room >= 25 and random.random() < self.promo_rate else None


def leftover(ents):
    b = 0.0
    for e in ents:
        if e.get("p") and e["k"] in ("ad", "bump"):
            r = dur.get(e["p"])
            if r:
                b += max(0.0, (e["e"] - e["s"]) - (r - e.get("o", 0)))
    return b


old_tot = new_tot = 0.0
worst_new = 0.0
n = over = 0
repeats = collections.Counter()
import time  # noqa: E402
now = time.time()
for f in sorted(os.listdir(os.path.join(D, "schedules"))):
    ents = json.load(open(os.path.join(D, "schedules", f), encoding="utf-8")).get("entries") or []
    ents = [e for e in ents if now <= e["s"] < now + HOURS * 3600]
    brk, prev = [], None
    groups = []
    for e in ents + [{"k": "show", "s": 0, "e": 0}]:
        if e["k"] in ("show", "guide", "weather", "offair"):
            if brk:
                groups.append((brk, e))
            brk = []
        else:
            brk.append(e)
    if not groups:
        continue
    has_promos = sum(1 for g, _ in groups for e in g if e["k"] == "promo") / float(len(groups))
    for g, nxt in groups:
        L = g[-1]["e"] - g[0]["s"]
        mid = nxt.get("k") == "show" and nxt.get("o", 0) > 1
        ads = ads_all if any(e["k"] == "ad" for e in g) else []
        bumps = bumps_all if any(e["k"] == "bump" for e in g) else []
        fk = Fake(min(1.0, has_promos))
        rng = random.Random("%s|%.0f" % (f, g[0]["s"]))
        endpos = fk._fill(g[0]["s"], L, ads, bumps, rng, final=not mid, absorb=mid)
        new = leftover(fk.data["entries"])
        old = leftover(g)
        old_tot += old
        new_tot += new
        worst_new = max(worst_new, new)
        n += 1
        over += new > 0.5
        spots = [e["p"] for e in fk.data["entries"] if e["k"] == "ad"]
        repeats["back-to-back"] += sum(1 for a, b in zip(spots, spots[1:]) if a == b)
        repeats["absorbed s"] += (g[0]["s"] + L) - endpos
print("%d breaks replayed (%d commercials, %d bumps known)" % (n, len(ads_all), len(bumps_all)))
print("old planned leftover %.1f s total; new %.1f s total, worst break %.2f s, breaks over 0.5 s: %d" % (
    old_tot, new_tot, worst_new, over))
print("back-to-back spots: %d; seconds absorbed by early programme parts: %.1f" % (
    repeats["back-to-back"], repeats["absorbed s"]))
