"""Real-time, self-building schedules.

There is no separate "build the station" step.  Each channel keeps a rolling
schedule file that is extended on demand (when you tune in, when the guide
needs it, or by the background service).  Programme picks are seeded from the
channel id and the wall-clock slot, so a 'strip' channel airs the same show at
the same time every weekday, while series always advance episode by episode.
"""
import bisect
import math
import os
import random
import threading
import time

from .kodiutil import SCHEDULE_DIR, load_json, save_json, log, ensure_dirs
from . import library
from . import channels as chmod
from .kodiutil import _

DAY = 86400


# ----------------------------------------------------------------- time utils
def local_tod(ts):
    lt = time.localtime(ts)
    return lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec + (ts - int(ts)), lt.tm_wday


def floor_slot(ts, slot):
    tod, _wday = local_tod(ts)
    return ts - (tod % slot)


def ceil_slot(ts, slot):
    f = floor_slot(ts, slot)
    return f if abs(f - ts) < 0.001 else f + slot


def hm(s):
    """'HH:MM' -> seconds after midnight."""
    try:
        h, m = str(s).split(":")[:2]
        return (int(h) % 24) * 3600 + int(m) * 60
    except ValueError:
        return 0


def _day_ok(days, wday):
    if not days or days == "all":
        return True
    if days == "weekdays":
        return wday < 5
    if days == "weekends":
        return wday >= 5
    if isinstance(days, list):
        return wday in days
    return True


def in_window(ts, win):
    tod, wday = local_tod(ts)
    a, b = hm(win.get("start", "00:00")), hm(win.get("end", "00:00"))
    if a == b:
        inside = True
    elif a < b:
        inside = a <= tod < b
    else:
        inside = tod >= a or tod < b
        if tod < b:  # we are in the after-midnight tail: judge by yesterday
            wday = (wday - 1) % 7
    return inside and _day_ok(win.get("days"), wday)


def window_end(ts, win):
    tod, _wday = local_tod(ts)
    b = hm(win.get("end", "00:00"))
    delta = (b - tod) % DAY
    if delta < 1:
        delta = DAY
    return ts + delta


def local_midnight(ts):
    tod, _wday = local_tod(ts)
    return ts - tod


def rule_occurrences(rule, t0, t1):
    """(start, end) of every airing of a weekly slot rule overlapping [t0, t1)."""
    days = rule.get("days")
    if days in (None, "all"):
        days = list(range(7))
    elif days == "weekdays":
        days = [0, 1, 2, 3, 4]
    elif days == "weekends":
        days = [5, 6]
    length = max(1, int(rule.get("minutes", 30))) * 60
    out = []
    m = local_midnight(t0) - DAY
    while m < t1 + DAY:
        wday = time.localtime(m + 43200).tm_wday
        if wday in days:
            st = local_midnight(m + 43200) + hm(rule.get("start", "00:00"))
            if st < t1 and st + length > t0:
                out.append((st, st + length))
        m = local_midnight(m + DAY + 43200)
    return out


# ----------------------------------------------------------------- schedule
class ChannelSchedule(object):
    def __init__(self, ch, cfg):
        self.ch = ch
        self.cfg = cfg
        self.path = os.path.join(SCHEDULE_DIR, "%s.json" % ch["id"])
        self.mtime = 0
        self.data = None
        self._starts = []
        self._bstarts = []
        self.reload()

    # -- persistence
    def reload(self):
        try:
            mt = os.path.getmtime(self.path)
        except OSError:
            mt = 0
        if self.data is not None and mt == self.mtime:
            return
        self.mtime = mt
        d = load_json(self.path, {})
        d.setdefault("hash", "")
        d.setdefault("entries", [])
        d.setdefault("blocks", [])
        d.setdefault("until", 0)
        d.setdefault("state", {})
        d["state"].setdefault("last", {})
        d["state"].setdefault("recent", {})
        self.data = d
        self._index()

    def save(self):
        ensure_dirs()
        save_json(self.path, self.data)
        try:
            self.mtime = os.path.getmtime(self.path)
        except OSError:
            pass

    def _index(self):
        self._starts = [e["s"] for e in self.data["entries"]]
        self._bstarts = [b["s"] for b in self.data["blocks"]]

    @property
    def slot(self):
        return int(self.ch.get("slot", 30)) * 60

    # -- public api
    def needs_work(self, now=None):
        """Cheap check: is the schedule stale or running short?"""
        now = now or time.time()
        self.reload()
        d = self.data
        return (d["hash"] != chmod.config_hash(self.ch) or not d["entries"] or
                d["until"] < now + self.cfg.get("low_water", 3 * 3600))

    def ensure(self, now=None, horizon=None, low_water=None):
        """Make sure the schedule covers now .. now+horizon.  Returns True if changed."""
        now = now or time.time()
        horizon = horizon or self.cfg.get("horizon", 12 * 3600)
        low_water = low_water or self.cfg.get("low_water", 3 * 3600)
        self.reload()
        d = self.data
        h = chmod.config_hash(self.ch)
        changed = False
        if d["hash"] != h or not d["entries"] or d["until"] < now:
            start = floor_slot(now, self.slot or 1800) - (1800 if self.slot else 0)
            d.update(hash=h, entries=[], blocks=[], until=start)
            changed = True
        if d["until"] < now + low_water or changed:
            target = now + horizon
            guard = 0
            while d["until"] < target and guard < 5000:
                d["until"] = self._block(d["until"])
                guard += 1
            changed = True
        if changed:
            cut = now - 3600
            d["entries"] = [e for e in d["entries"] if e["e"] > cut]
            d["blocks"] = [b for b in d["blocks"] if b["e"] > cut]
            self._index()
            self.save()
        return changed

    def entry_at(self, ts):
        i = bisect.bisect_right(self._starts, ts) - 1
        if i >= 0:
            e = self.data["entries"][i]
            if e["s"] <= ts < e["e"]:
                return e
        return None

    def block_at(self, ts):
        i = bisect.bisect_right(self._bstarts, ts) - 1
        if i >= 0:
            b = self.data["blocks"][i]
            if b["s"] <= ts < b["e"]:
                return b
        return None

    def blocks_between(self, t0, t1):
        i = max(0, bisect.bisect_right(self._bstarts, t0) - 1)
        out = []
        for b in self.data["blocks"][i:]:
            if b["s"] >= t1:
                break
            if b["e"] > t0:
                out.append(b)
        return out

    def next_block(self, ts):
        i = bisect.bisect_right(self._bstarts, ts)
        if i < len(self.data["blocks"]):
            return self.data["blocks"][i]
        return None

    # -- generation
    def _daypart(self, t):
        for w in self.ch.get("offair", []):
            if in_window(t, w):
                return "offair", None, True, window_end(t, w)
        for i, dp in enumerate(self.ch.get("dayparts", [])):
            if in_window(t, dp):
                return "dp%d" % i, dp.get("sources", []), False, window_end(t, dp)
        return "base", self.ch.get("sources", []), False, None

    def _add(self, s, e, kind, **kw):
        if e - s <= 0.05:
            return
        ent = {"s": round(s, 3), "e": round(e, 3), "k": kind}
        ent.update({k: v for k, v in kw.items() if v not in (None, "")})
        self.data["entries"].append(ent)

    def _add_block(self, s, e, title, kind="show", sub="", label=""):
        b = {"s": round(s, 3), "e": round(e, 3), "t": title, "k": kind}
        if sub:
            b["sub"] = sub
        if label:
            b["lb"] = label
        self.data["blocks"].append(b)

    def _rules(self):
        return [r for r in self.ch.get("slots", []) if r.get("sources")]

    def _rule_at(self, t):
        """A pinned weekly slot airing at t (with at least a minute left)."""
        for r in self._rules():
            for st, en in rule_occurrences(r, t, t + 1):
                if st <= t < en - 60:
                    return r, st, en
        return None, None, None

    def _next_fixed(self, t, horizon=8 * DAY):
        """Start of the next pinned slot strictly after t (or None)."""
        best = None
        for r in self._rules():
            for st, _en in rule_occurrences(r, t + 1, t + horizon):
                if st > t + 0.5 and (best is None or st < best):
                    best = st
        return best

    def _fillers(self):
        ch = self.ch
        ads = library.filler_pool(ch.get("commercials_path") or self.cfg.get("commercials_path")) \
            if ch.get("commercials") else []
        bumps = library.filler_pool(ch.get("bumps_path") or self.cfg.get("bumps_path")) \
            if ch.get("bumps") else []
        ids = library.filler_pool(ch.get("ids_path")) if ch.get("ids_path") else []
        return ads, bumps, ids

    def _block(self, t):
        ch = self.ch
        slot = self.slot
        if ch["type"] in ("guide", "weather"):
            e = floor_slot(t, 1800) + 1800
            self._add(t, e, ch["type"])
            self._add_block(t, e, _("Program Guide") if ch["type"] == "guide" else _("Local Forecast"),
                            ch["type"])
            return e

        hard = self._next_fixed(t)
        rule, _rs, _re = self._rule_at(t)
        if rule:
            pool = library.resolve(rule["sources"])
            prog = self._pick_rule(pool, t, rule)
            if prog:
                return self._program(t, prog, hard)

        key, sources, offair, until = self._daypart(t)
        if offair:
            end = until if hard is None else min(until, hard)
            return self._offair(t, end, until)

        pool = library.without(library.resolve(sources), ch.get("exclude"))
        room = (hard - t - 2) if hard else None
        prog = self._pick(pool, t, key, maxdur=room)
        if prog:
            return self._program(t, prog, hard)
        if room is not None and (pool["series"] or pool["singles"]):
            # Nothing short enough before the next pinned show: station break.
            ads, bumps, ids = self._fillers()
            rng = random.Random("%s|%.0f|gap" % (ch["id"], t))
            self._fill(t, hard - t, ads, bumps, rng, final=True, ids=ids)
            self._add_block(t, hard, _("Station Break"), "card")
            return hard
        e = t + (slot or 1800)
        if hard:
            e = min(e, hard)
        self._add(t, e, "card", sub="nosignal")
        self._add_block(t, e, _("No Programming"), "card")
        return e

    def _offair(self, t, end, real_end):
        """Sign-off clip, stand-by card (or bars), sign-on clip."""
        ch = self.ch
        style = ch.get("offair_style") or self.cfg.get("offair_style") or "standby"
        rng = random.Random("%s|%.0f|offair" % (ch["id"], t))
        pos = t
        # sign-off only at the real start of the off-air window
        starting = not any(in_window(t - 30, w) for w in ch.get("offair", []))
        if starting and ch.get("signoff_path"):
            clips = [c for c in library.filler_pool(ch["signoff_path"]) if c["dur"] < end - pos - 60]
            if clips:
                c = rng.choice(clips)
                self._add(pos, pos + c["dur"], "clip", p=c["path"], o=0, t=_("Sign-off"))
                pos += c["dur"]
        signon = None
        if end == real_end and ch.get("signon_path"):
            clips = [c for c in library.filler_pool(ch["signon_path"]) if c["dur"] < end - pos - 60]
            if clips:
                signon = rng.choice(clips)
        stop = end - (signon["dur"] if signon else 0)
        self._add(pos, stop, "offair", sub=style)
        if signon:
            self._add(stop, end, "clip", p=signon["path"], o=0, t=_("Sign-on"))
        self._add_block(t, end, _("Off the Air"), "offair")
        return end

    def _program(self, t, prog, hard):
        """Lay one programme out with commercial breaks, ending on a slot
        boundary and never running into the next pinned slot."""
        ch = self.ch
        slot = self.slot
        rng = random.Random("%s|%.0f" % (ch["id"], t))
        dur = float(prog["dur"])
        ads, bumps, ids = self._fillers()

        if slot:
            end = ceil_slot(t + dur + 2, slot)
            nslots = max(1, int(round((end - t) / slot)))
        else:
            end, nslots = t + dur, 1
        if hard is not None and end > hard:
            end = hard
        dur = min(dur, end - t)      # runs into a pinned slot: the network cuts away
        gap = end - t - dur

        k = 0
        if ads and gap >= 90:
            per = self.cfg.get("breaks_per_slot", 2)
            k = max(0, min(per * nslots * slot // 1800 if slot else per, int(gap // 75) - 1))
        if not ch.get("midroll", ch["type"] != "movies"):
            k = 0
        brk = gap / (k + 1)
        points = [dur * i / (k + 1) for i in range(k + 2)]
        pos = t
        for i in range(k + 1):
            seg = points[i + 1] - points[i]
            self._add(pos, pos + seg, "show", p=prog["path"], o=round(prog.get("o0", 0) + points[i], 2),
                      t=prog["title"], sub=prog.get("sub"), lb=prog.get("label"))
            pos += seg
            blen = brk if i < k else end - pos
            pos = self._fill(pos, blen, ads, bumps, rng, final=(i == k), ids=ids if i == k else None)
        self._add_block(t, end, prog["title"], "show", prog.get("sub", ""), prog.get("label", ""))
        return end

    def _fill(self, pos, length, ads, bumps, rng, final, ids=None):
        end = pos + length
        if length < 0.5:
            return end
        bump = None
        # Between programmes a station ID ("you're watching...") beats a bump.
        for pool in ([ids, bumps] if ids else [bumps]):
            fit = [b for b in (pool or []) if b["dur"] <= length]
            if fit:
                bump = rng.choice(fit)
                break
        avail = length - (bump["dur"] if bump else 0)

        # Pack commercials: try several random fills and keep the tightest.
        chosen, remaining = [], avail
        if ads:
            best = None
            for _attempt in range(40):
                pick, rem, used = [], avail, set()
                while True:
                    fit = [a for a in ads if a["dur"] <= rem and a["path"] not in used]
                    if not fit:
                        break
                    a = rng.choice(fit)
                    used.add(a["path"])
                    pick.append(a)
                    rem -= a["dur"]
                if best is None or rem < best[1]:
                    best = (pick, rem)
                if rem < 1.0:
                    break
            chosen, remaining = best

        if chosen:
            # Spread small leftovers as the short black gaps real breaks have.
            gap = remaining / len(chosen) if remaining <= 2.0 * len(chosen) else 0
            for a in chosen:
                self._add(pos, pos + a["dur"] + gap, "ad", p=a["path"], o=0, t=a.get("title"))
                pos += a["dur"] + gap
            remaining -= gap * len(chosen)
            if remaining >= 0.5:
                # Fill the rest with the start of one more spot, cut off by the
                # network - just like a late cable switch-over.
                longer = [a for a in ads if a["dur"] > remaining] or ads
                a = rng.choice(longer)
                self._add(pos, pos + remaining, "ad", p=a["path"], o=0, t=a.get("title"))
                pos += remaining
        elif remaining >= 0.5:
            self._add(pos, pos + remaining, "card", sub="next" if final else "id")
            pos += remaining
        if bump:
            self._add(pos, pos + bump["dur"], "bump", p=bump["path"], o=0)
            pos += bump["dur"]
        if self.data["entries"] and pos < end:
            self.data["entries"][-1]["e"] = round(end, 3)
        return end

    def _next_episode(self, ser, ptr_key):
        eps = ser["episodes"]
        last = self.data["state"]["last"].get(ptr_key)
        idx = 0
        if last:
            for i, e in enumerate(eps):
                if e["path"] == last:
                    idx = (i + 1) % len(eps)
                    break
        return eps[idx]

    def _pick_rule(self, pool, t, rule):
        """Programme for a pinned slot.  'inorder' continues each series where
        that slot left off (its own bookmark), rotating between shows if the
        slot has several; 'random' picks any episode/movie."""
        series, singles = pool["series"], pool["singles"]
        if not series and not singles:
            return None
        rid = "rule:%s" % rule.get("id", "")
        st = self.data["state"]
        if rule.get("order", "inorder") == "random":
            rng = random.Random("%s|%.0f|%s" % (self.ch["id"], t, rid))
            every = [e for ser in series for e in ser["episodes"]] + singles
            return rng.choice(every)
        shows = [("s", ser) for ser in series] + ([("m", None)] if singles else [])
        rr = st.setdefault("rr", {})
        i = rr.get(rid, 0) % len(shows)
        rr[rid] = i + 1
        kind, ser = shows[i]
        if kind == "s":
            ep = self._next_episode(ser, rid + "|" + ser["key"])
            st["last"][rid + "|" + ser["key"]] = ep["path"]
            return ep
        ep = self._next_episode({"episodes": singles}, rid + "|movies")
        st["last"][rid + "|movies"] = ep["path"]
        return ep

    def _pick(self, pool, t, key, maxdur=None):
        series, singles = pool["series"], pool["singles"]
        if maxdur is not None:
            # Only shows whose next episode ends before the next pinned slot.
            series = [ser for ser in series
                      if self._next_episode(ser, ser["key"])["dur"] <= maxdur]
            singles = [it for it in singles if it["dur"] <= maxdur]
        if not series and not singles:
            return None
        cands = [(s, math.sqrt(min(len(s["episodes"]), 60))) for s in series]
        if singles:
            cands.append((None, math.sqrt(min(len(singles), 60)) * (2 if not series else 1)))
        if self.ch.get("lineup", "strip") == "strip":
            tod, wd = local_tod(t)
            dtype = "wd" if wd < 5 else str(wd)
            seed = "%s|%s|%s|%d" % (self.ch["id"], key, dtype, int(tod // 60))
        else:
            seed = "%s|%s|%.0f" % (self.ch["id"], key, t)
        rng = random.Random(seed)
        total = sum(w for _, w in cands)
        x = rng.random() * total
        choice = cands[-1][0]
        for c, w in cands:
            x -= w
            if x <= 0:
                choice = c
                break
        st = self.data["state"]
        if choice is not None:
            ep = self._next_episode(choice, choice["key"])
            st["last"][choice["key"]] = ep["path"]
            return ep
        recent = st["recent"].setdefault(key, [])
        keep = min(len(singles) // 2, 200)
        avoid = set(recent[-keep:]) if keep else set()
        fresh = [s for s in singles if s["path"] not in avoid] or singles
        r2 = random.Random("%s|%.0f|single" % (self.ch["id"], t))
        it = r2.choice(fresh)
        recent.append(it["path"])
        del recent[:-max(keep, 1)]
        return it


class Lineup(object):
    """All channels + their schedules."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.channels = chmod.load()
        self.sched = {}
        self.lock = threading.RLock()   # one schedule build at a time (TV + background builder)

    def reload_channels(self):
        self.channels = chmod.load()
        ids = set(c["id"] for c in self.channels)
        for cid in list(self.sched):
            if cid not in ids:
                del self.sched[cid]
        for c in self.channels:
            if c["id"] in self.sched:
                self.sched[c["id"]].ch = c

    def by_number(self, n):
        for c in self.channels:
            if c["number"] == n:
                return c
        return None

    def schedule(self, ch, ensure=True, now=None):
        s = self.sched.get(ch["id"])
        if s is None:
            s = self.sched[ch["id"]] = ChannelSchedule(ch, self.cfg)
        if ensure:
            try:
                if s.needs_work(now):
                    with self.lock:
                        s.ensure(now)
            except Exception as exc:
                log("Schedule build failed for %s: %s" % (ch.get("name"), exc))
        return s

    def is_ready(self, ch, now=None):
        s = self.schedule(ch, ensure=False)
        return s.block_at(now or time.time()) is not None

    def ensure_all(self, now=None, abort=None):
        for c in self.channels:
            if abort and abort():
                return
            self.schedule(c, True, now)

    def neighbour(self, ch, step):
        if not self.channels:
            return None
        nums = [c["number"] for c in self.channels]
        i = nums.index(ch["number"]) if ch and ch["number"] in nums else -1
        return self.channels[(i + step) % len(self.channels)]
