"""The guide channel's grid, Prevue style: short channel labels, listing details
fitted to a cell, and the scroll-ad rows between the last channel and the first.

No skin or player code here (tv.fill_guide lays the rows out); reads only the
viewer's optional guide.txt (never writes to the station folder).
"""
import re
import time

from . import promos
from . import stations
from .kodiutil import _

CELL_W = (460, 460, 440)            # the three listing cells' label widths (skin list 50)
CALL_W = 270
LADDER_CALL = (("font37", 37), ("font27", 27), ("font12", 25), ("font10", 23))
LADDER_CELL = (("font27", 27), ("font12", 25))
SPEEDS = (3.0, 2.5, 1.7)            # seconds per row: Slow / Normal / Fast
_SKIP_WORDS = ("the", "and", "of", "&", "a", "channel", "network")
_OWN_ADS = {}                       # folder -> (read at, lines)
_OWN_TTL = 600


def speed(index):
    try:
        return SPEEDS[int(index)]
    except (ValueError, IndexError, TypeError):
        return SPEEDS[1]


def short_call(name, call):
    """The channel cell's label: the station's call letters, else a short
    uppercase abbreviation of the name (at most 5 letters): 'Shorties TV' -> 'STV',
    'Chameleon' -> 'CHAM', 'Red Thread TV' -> 'RTTV', 'The Exploration Channel' -> 'EXPL'."""
    call = (call or "").strip()
    if call:
        return call.upper()
    words = [w for w in re.split(r"[^0-9A-Za-z]+", name or "") if w]
    keep = [w for w in words if w.lower() not in _SKIP_WORDS] or words
    if not keep:
        return ""
    if len(keep) == 1:
        w = keep[0].upper()
        return w if len(w) <= 5 else w[:4]
    out = ""
    for w in keep:
        # short all-capitals words stay whole (TV, HBO, 42)
        out += w if (w.isupper() or w.isdigit()) and len(w) <= 3 else w[0].upper()
    return out[:5]


def details(info, rerun=False, special=""):
    """The listing's details in the order they're dropped last to first: the name of
    the special it airs in ('Taxi \u00b7 Turkey Day Marathon'), '(R)' for a summer rerun, movies
    '(1990)' and 'PG-13'; then '(CC)' and '(Stereo)'."""
    from . import library
    out = ([u"\u00b7 " + special] if special else []) + ([_("(R)")] if rerun else [])
    if info:
        if info.get("kind") == "movie":
            if info.get("year"):
                out.append("(%s)" % info["year"])
            code = library.mpaa_code(info.get("mpaa"))
            if code:
                out.append(code)
        if info.get("cc"):
            out.append(_("(CC)"))
        if info.get("stereo"):
            out.append(_("(Stereo)"))
    return out


def fit_cell(title, extra, width):
    """(text, font, two-line text) for a listing cell: the details go before the
    title is shrunk, and the title is never cut (smaller font, then two lines:
    font 'two', a value no font name ends like - font12 ends in 2)."""
    for k in range(len(extra), -1, -1):
        txt = " ".join([title] + list(extra[:k]))
        f = promos.fit_font(txt, width, LADDER_CELL, promos.TWO_23)
        if not f.endswith("2"):
            return txt, f, ""
    f = promos.fit_font(title, width, promos.LADDER_27, promos.TWO_23)
    return (title, f, "") if not f.endswith("2") else (title, "two", promos.two_lines(title))


def call_fit(text):
    f = promos.fit_font(text, CALL_W, LADDER_CALL, promos.TWO_23)
    return (f, "") if not f.endswith("2") else ("two", promos.two_lines(text))


def builtin_ads():
    """Fictional cable-company lines (no real brands)."""
    return [_("Add a premium channel today!  Call your cable company."),
            _("Pay-Per-View: call 555-0142 to order."),
            _("Ask about our Movie Lovers package."),
            _("Two months of premium channels, half price."),
            _("Moving?  Take your cable with you.  Call 555-0199."),
            _("Remote not working?  Free replacement at the cable office."),
            _("New this month: more channels on the basic tier."),
            _("Watch the big fight live on Pay-Per-View."),
            _("Cable installation: just $9.95 this month."),
            _("Thank you for choosing cable.")]


def own_ads(folder):
    """The guide channel's guide.txt (one ad per line; '#' lines are notes), read-only."""
    if not folder:
        return []
    hit = _OWN_ADS.get(folder)
    if hit and time.time() - hit[0] < _OWN_TTL:
        return hit[1]
    lines = []
    for f in ("guide.txt", "Guide.txt", "GUIDE.TXT"):
        text = promos._read_text(stations._join(folder, f))
        if text:
            lines = [ln.strip() for ln in text.lstrip(u"﻿").splitlines()
                     if ln.strip() and not ln.strip().startswith("#")]
            break
    _OWN_ADS[folder] = (time.time(), lines)
    return lines


KIDS_GENRES = ("animation", "family", "children", "children's", "kids")
SPORTS_GENRES = ("sport", "sports", "football", "soccer", "basketball", "baseball", "hockey", "boxing",
                 "wrestling", "motorsport", "golf", "tennis")
KIDS_STATIONS = ("chameleon", "animation_station")


def kids_channel(ch):
    """A kids' channel for the guide's colours: Ad flavour Kids (set or automatic),
    or a built-in kids' station (Chameleon with its CAM Jr. block, Animation Station)."""
    from . import ads
    return ch.get("station") in KIDS_STATIONS or ads.flavour(ch) == "K"


def category(info, kids_ch=False):
    """The listing cell's colour: 'movie' (any movie), 'sports', 'kids' or '' (the row's blue).
    From the library's genres; on a kids' channel every programme counts as kids."""
    if info and info.get("kind") == "movie":
        return "movie"
    genres = [g.lower() for g in (info or {}).get("genre") or []]
    if any(g in SPORTS_GENRES for g in genres):
        return "sports"
    if kids_ch or any(g in KIDS_GENRES for g in genres):
        return "kids"
    return ""


def ad_count(channels):
    """Scroll ads a cycle: 1 for a small lineup, up to 3 for a big one."""
    return max(1, min(3, int(round(channels / 8.0))))


# ------------------------------------------------------------------ the top half (stage 3)
# Trailers of movies airing in the next 4 hours, the shows' Extras promo clips and
# commercials, played as runs of one frame rate (one Kodi playlist each, so a TV set
# to switch refresh rate blanks only between runs), with text-and-music stretches
# between them.  Each half hour is planned from a seed of channel + slot start and
# joined at the clock, like every other channel.
TOP_HOURS = 4
RUN_MIN, RUN_MAX = 120.0, 240.0          # s of video in a run
TEXT_MIN, TEXT_MAX = 60.0, 120.0         # s of text and guide music between runs
CLIP_MAX = 240.0                         # longer clips are left out
TOP_FILE = "guide_top.json"


def top_candidates(lineup, now, guide_ch=None, cfg=None):
    """The clips the top half can play: [{path, dur, kind, title, at, num, call}]
    (kind 'trailer' / 'promo' / 'ad'; at/num/call: the next airing it advertises).
    Frame rates aren't looked at here (see measured)."""
    from . import library, promos
    out, seen = [], set()
    trailers = library.movie_trailers()
    for ch in lineup.channels:
        if ch.get("type") not in ("network", "movies", "loop"):
            continue
        sched = lineup.schedule(ch, ensure=False)
        br = stations.brand(ch, now)
        call = short_call(br["name"], br["call"])
        for b in sched.blocks_between(now, now + TOP_HOURS * 3600):
            if b.get("k") != "show" or b["s"] < now - 60 or b["t"] in seen:
                continue
            e = sched.entry_at(b["s"] + 0.01)
            path = e.get("p") if e and e.get("k") == "show" else ""
            if not path:
                continue
            seen.add(b["t"])
            base = {"title": b["t"], "at": b["s"], "num": ch["number"], "call": call}
            if path in trailers:
                out.append(dict(base, path=trailers[path], dur=0.0, kind="trailer"))
            elif not ch.get("type") == "movies":
                for c in promos.extras_promos(path, b["t"])[:2]:
                    out.append(dict(base, path=c["path"], dur=float(c["dur"]), kind="promo"))
    # commercials: the guide channel's own when its station folder has any, else everyone's
    ads = []
    if guide_ch:
        folder = stations.kind_folder(stations.brand(guide_ch, now)["folder"], "commercials")
        ads = library.filler_pool(folder) if folder else []
    if not ads:
        ads = library.filler_pool((cfg or {}).get("commercials_path") or "")
    for a in ads:
        out.append({"path": a["path"], "dur": float(a["dur"]), "kind": "ad", "title": "", "at": 0,
                    "num": "", "call": ""})
    return out


def measured(clips):
    """The clips with a known frame rate and length (durations.json), each with its
    family ('23.976', '29.97', '25'...); the rest are waiting for the service."""
    from . import library, musicvideos
    d = library.durations()
    out = []
    for c in clips:
        fps = d.fps(c["path"])
        dur = c["dur"] or d.get(c["path"], probe_if_missing=False)
        fam = musicvideos.family(fps) if fps else ""
        if fam and 0 < dur <= CLIP_MAX:
            out.append(dict(c, dur=float(dur), fam=fam))
    return out


def top_plan(seed, length, clips):
    """[{k: 'run', s, e, fam, clips: [...]} | {k: 'text', s, e}] covering [0, length)
    exactly (seconds from the slot's start).  Runs: 2-4 minutes of one frame-rate
    family, trailers and promos taking turns with commercials; then 1-2 minutes of
    text.  No clip twice in a slot.  Nothing measured: one text stretch."""
    import random as _r
    rng = _r.Random(seed)
    fams = {}
    for c in clips:
        fams.setdefault(c["fam"], []).append(c)
    for f in fams:
        fams[f].sort(key=lambda c: c["path"])
        rng.shuffle(fams[f])
    used, out, t = set(), [], 0.0
    while t < length:
        left = length - t
        avail = dict((f, [c for c in cs if c["path"] not in used]) for f, cs in fams.items())
        avail = dict((f, cs) for f, cs in avail.items() if cs)
        if left < TEXT_MIN + 30 or not avail:
            out.append({"k": "text", "s": t, "e": length})
            break
        # the family: weighted by how much it has, so every rate takes turns
        names = sorted(avail)
        weights = [sum(c["dur"] for c in avail[f]) for f in names]
        x, fam = rng.random() * sum(weights), names[-1]
        for f, w in zip(names, weights):
            x -= w
            if x <= 0:
                fam = f
                break
        goal = min(rng.uniform(RUN_MIN, RUN_MAX), left - TEXT_MIN)
        feature = [c for c in avail[fam] if c["kind"] != "ad"]
        ads = [c for c in avail[fam] if c["kind"] == "ad"]
        run, dur, turn = [], 0.0, 0
        while (feature or ads) and dur < goal:
            src = feature if (turn % 2 == 0 and feature) or not ads else ads
            c = src.pop(0)
            if dur + c["dur"] > min(RUN_MAX, left - TEXT_MIN):
                continue                         # too long for what's left of this run: another one
            run.append(c)
            used.add(c["path"])
            dur += c["dur"]
            turn += 1
        if not run:
            out.append({"k": "text", "s": t, "e": length})
            break
        out.append({"k": "run", "s": t, "e": t + dur, "fam": fam, "clips": run})
        t += dur
        gap = min(rng.uniform(TEXT_MIN, TEXT_MAX), length - t)
        if length - t - gap < TEXT_MIN + 30:
            gap = length - t                     # the slot's last stretch takes the rest
        out.append({"k": "text", "s": t, "e": t + gap})
        t += gap
    return out


def top_at(plan, offset):
    """(index, item) of the plan at offset seconds into the slot."""
    for i, it in enumerate(plan):
        if it["s"] <= offset < it["e"]:
            return i, it
    return len(plan) - 1, plan[-1]


def caption(c, clock, now=None):
    """'Tonight 8:00 PM · 12 PIX' for a trailer or promo, '' for a commercial.
    clock: the TV's time format (tv.fmt_time)."""
    if c.get("kind") == "ad" or not c.get("at"):
        return ""
    lt = time.localtime(c["at"])
    hhmm = clock(c["at"])
    when = (_("Tonight %s") if lt.tm_hour >= 17 else _("Today %s")) % hhmm
    if time.localtime(now or time.time()).tm_yday != lt.tm_yday:
        when = _("Tomorrow %s") % hhmm
    return u"%s  ·  %s %s" % (when, c.get("num", ""), c.get("call", ""))


class TopReader(object):
    """The service's background reader, for the top half: the frame rate (and length)
    of each clip it could play, one file at a time, into durations.json.  The list
    is rebuilt every 10 minutes; read-only (probe reads headers)."""
    REBUILD = 600.0

    def __init__(self):
        self.todo, self.built = [], 0.0

    def step(self):
        """Measure one clip; False when there's nothing to measure now."""
        from . import kodiutil as K, library, probe, scheduler
        now = time.time()
        if not self.todo and now - self.built < self.REBUILD:
            return False
        if not self.todo:
            self.built = now
            if K.setting_int("guide_top", 0) != 0:
                return False                     # Text only: nothing to measure
            cfg = K.schedule_cfg()
            lineup = scheduler.Lineup(cfg)
            gch = next((c for c in lineup.channels if c.get("type") == "guide"), None)
            if gch is None:
                return False
            d = library.durations()
            self.todo = [c["path"] for c in top_candidates(lineup, now, gch, cfg) if d.fps(c["path"]) is None]
            if self.todo:
                K.log("guide top half: %d clips to measure" % len(self.todo))
            return False
        p = self.todo.pop(0)
        d = library.durations()
        if d.fps(p) is None:
            info = probe.media_info(p) or {}
            d.set_fps(p, info.get("fps") or 0)
            if info.get("dur"):
                d.learn(p, info["dur"])
            if not self.todo or len(self.todo) % 20 == 0:
                d.save()
        return True
