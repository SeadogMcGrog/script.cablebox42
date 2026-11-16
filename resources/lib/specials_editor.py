"""Holidays and specials: the editor (Settings > Tools, and a channel's Schedule group).

The list is a menu (changes save as you go, Done at the bottom).  Adding a special is
step-by-step: Back on any step cancels it and nothing is saved; it ends on a
Cancel / Add special question.  The rules, hours and calendar.json are specials.py;
what airs on the day is scheduler.py.

Saving replans the channels a special is on and the channels whose shows it now
keeps off, each from the end of what is on air (replan); no other channel is touched.
"""
import datetime
import json
import time

import xbmc
import xbmcgui

from . import kodiutil as K
from . import channels as C
from . import scheduler
from . import specials
from . import manager as M
from . import planner as P
from .kodiutil import _

D = M.D
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December")
SEASON = {"halloween": _("Halloween"), "thanksgiving": _("Thanksgiving"), "christmas": _("Christmas")}
PRESET = {"newyear": _("New Year's Day"), "valentine": _("Valentine's Day"), "easter": _("Easter"),
          "halloween": _("Halloween"), "thanksgiving": _("Thanksgiving (US)"), "christmaseve": _("Christmas Eve"),
          "christmas": _("Christmas Day"), "newyearseve": _("New Year's Eve")}
ORDERS = (("continue", _("Continue where last year's marathon stopped"), _("in order, continuing each year")),
          ("first", _("From the first episode"), _("from the first episode")),
          ("random", _("Random"), _("random")))
DOT = u"  ·  "


# ------------------------------------------------------------------ words
def now():
    """The clock specials go by (the real one, unless the test setting moves today)."""
    return time.time() + scheduler.specials_shift(K.schedule_cfg())


def today():
    return datetime.date.fromtimestamp(now())


def month(m, short=False):
    """Kodi's own month names (January = 21, Jan = 51)."""
    try:
        s = xbmc.getLocalizedString((50 if short else 20) + m)
    except Exception:
        s = ""
    return s or (MONTHS[m - 1][:3] if short else MONTHS[m - 1])


def date_text(day):
    """'Thu 26 Nov', with the year when it isn't this one."""
    txt = "%s %d %s" % (P.day_names()[day.weekday()], day.day, month(day.month, True))
    return txt if day.year == today().year else "%s %d" % (txt, day.year)


def nth_names():
    return [_("1st"), _("2nd"), _("3rd"), _("4th"), _("Last")]


def when_text(when):
    """A rule in words: '31 December', '4th Thursday of November', 'Good Friday'."""
    kind = when.get("type")
    if kind == "date":
        txt = "%d %s" % (when["day"], month(when["month"]))
    elif kind == "nth":
        n = when["n"]
        txt = _("%s %s of %s") % (nth_names()[4 if n == -1 else n - 1] if n in (1, 2, 3, 4, -1) else _("5th"),
                                  P.day_names(False)[when["weekday"]], month(when["month"]))
    else:
        off = when.get("offset", 0)
        txt = {0: _("Easter Sunday"), -2: _("Good Friday"), 1: _("Easter Monday")}.get(off) or (
            (_("%d days after Easter") % off) if off > 0 else (_("%d days before Easter") % -off))
    shift = when.get("shift", 0)
    if shift == 1:
        return _("The day after %s") % txt
    if shift == -1:
        return _("The day before %s") % txt
    if shift:
        return (_("%d days after %s") if shift > 0 else _("%d days before %s")) % (abs(shift), txt)
    return txt


def repeat_text(sp):
    return _("Every year") if sp.get("repeat") != "once" else _("Only in %d") % sp.get("year", 0)


def hours_text(blk):
    a, b = specials.span(blk)
    if (a, b) == (0, 1440):
        return _("all day")
    if (a, b) == (360, 1800):
        return _("broadcast day")
    return "%s - %s" % (P.clock(a), P.clock(b))


def source_text(blk):
    season = scheduler.ChannelSchedule._holiday_source(blk)
    if season is not None:
        return _("%s episodes") % SEASON.get(season, season)
    srcs = blk.get("sources") or [{}]
    return P.source_label(srcs[0]) + ((" +%d" % (len(srcs) - 1)) if len(srcs) > 1 else "")


def order_text(blk, row=True):
    for key, label, short in ORDERS:
        if key == blk.get("order"):
            return short if row else label
    return ""


def chan(chans, cid):
    for c in chans:
        if c["id"] == cid:
            return c
    return None


def chan_name(ch):
    return "%d %s" % (ch["number"], ch["name"])


def block_text(chans, blk):
    ch = chan(chans, blk.get("channel"))
    return "%s: %s, %s" % (chan_name(ch) if ch else "?", source_text(blk), hours_text(blk))


# ------------------------------------------------------------------ calendar.json
def load(chans=None):
    """A copy of the specials to change freely.  Blocks of channels that are gone
    are left out, and specials with none left; 'this year only' ones that have
    passed go when it is saved."""
    cal = json.loads(json.dumps(specials.load()))
    if chans is not None:
        ids = set(c["id"] for c in chans)
        for sp in cal:
            sp["blocks"] = [b for b in sp["blocks"] if b.get("channel") in ids]
        cal = [sp for sp in cal if sp["blocks"]]
    return [sp for sp in cal if not specials.expired(sp, now())]


def save(cal, cids=(), sp=None):
    """Write calendar.json, then plan again - from the end of what is on air - the
    channels in `cids` and the channels whose shows `sp` now keeps off."""
    specials.save(cal, now=now())
    scheduler.forget_specials()
    todo = set(cids)
    try:
        lineup = scheduler.Lineup(K.schedule_cfg())
        if sp is not None:
            todo |= kept_off(lineup, sp)
        replan(lineup, todo)
    except Exception as exc:
        K.log_err("Holidays and specials, planning again: %s" % exc)


def kept_off(lineup, sp):
    """Channels that have one of the special's shows planned during its hours."""
    off = scheduler.specials_shift(lineup.cfg)
    day, _skipped = specials.next_date(sp, time.time() + off)
    out = set()
    if not day:
        return out
    for blk in sp["blocks"]:
        ch = chan(lineup.channels, blk.get("channel"))
        if not ch:
            continue
        titles = set(t.lower() for t in lineup.schedule(ch, ensure=False)._special_titles(blk))
        if not titles:
            continue
        st, en = specials.window(blk, day)
        for c in lineup.channels:
            if c["id"] == ch["id"] or c["type"] in ("guide", "weather"):
                continue
            other = lineup.schedule(c, ensure=False)
            if any(b.get("k") == "show" and b["t"].lower() in titles for b in other.blocks_between(st - off, en - off)):
                out.add(c["id"])
    return out


def replan(lineup, cids):
    """Cut these channels after what is on air (all of them first: bookmarks go back
    before anything is planned again), then plan them.  Holds TOOL_BUSY like a tool."""
    cids = [c for c in lineup.channels if c["id"] in cids]
    if not cids:
        return
    home = xbmcgui.Window(10000)
    mine = not home.getProperty(M.TOOL_BUSY)
    if mine:
        home.setProperty(M.TOOL_BUSY, "specials")
    try:
        t = time.time()
        with lineup.lock:
            for c in cids:
                s = lineup.schedule(c, ensure=False)
                s.reload()
                if s.data["entries"] and s.data["until"] >= t:
                    s.cut(t)
                s.data["hash"] = s.full_hash()
                s.save()
            for c in cids:
                try:
                    lineup.schedule(c, ensure=False).ensure(t)
                except Exception as exc:
                    K.log("Schedule build failed for %s: %s" % (c.get("name"), exc))
        K.log("Holidays and specials: planned again: %s" % ", ".join(c["name"] for c in cids), xbmc.LOGINFO)
    finally:
        if mine:
            home.clearProperty(M.TOOL_BUSY)


# ------------------------------------------------------------------ deleting a channel
def on_channel(cid):
    """Names of the specials with programming on this channel."""
    t = now()
    return [sp["name"] for sp in specials.load()
            if any(b.get("channel") == cid for b in sp["blocks"]) and not specials.expired(sp, t)]


def drop_channel(cid):
    """The channel is deleted: its blocks go, and specials left with none."""
    cal = json.loads(json.dumps(specials.load()))
    if not any(b.get("channel") == cid for sp in cal for b in sp["blocks"]):
        return
    for sp in cal:
        sp["blocks"] = [b for b in sp["blocks"] if b.get("channel") != cid]
    specials.save([sp for sp in cal if sp["blocks"]], now=now())
    scheduler.forget_specials()


# ------------------------------------------------------------------ the list
def open_list(cid=None):
    """Tools > Holidays and specials; with cid, the same list for one channel."""
    while True:
        chans = C.load()
        air = [c for c in chans if c["type"] in M.AIR_TYPES]
        if not air:
            D.ok(M.TITLE, _("Add a channel first."))
            return
        only = chan(chans, cid) if cid else None
        cal = load(chans)
        ups = [u for u in specials.upcoming(cal, now())
               if not cid or any(b["channel"] == cid for b in u[1]["blocks"])]
        rows = [M._menu_row(_("[B]+ Add a special[/B]"),
                            _("A marathon or a holiday lineup on a date, back every year"))]
        for day, sp, skipped in ups:
            blocks = sp["blocks"]
            detail = block_text(chans, blocks[0]) if len(blocks) == 1 else _("%d channels") % len(
                set(b["channel"] for b in blocks))
            if today().year in skipped:
                detail += DOT + _("skips this year")
            rows.append(M._menu_row("%s%s%s" % (sp["name"], DOT, date_text(day)), detail))
        head = (_("Holidays and specials - %s") % only["name"]) if only else _("Holidays and specials")
        i = M.done_select(head, rows, useDetails=True)
        if i < 0:
            return
        if i == 0:
            sid = add_special(cal, chans, cid)
            if sid:
                special_page(sid)
        else:
            special_page(ups[i - 1][1]["id"])


# ------------------------------------------------------------------ adding: step by step
def ask_when():
    """(rule, a name for it) or None."""
    i = D.select(_("When?"), [_("A date..."), _("A weekday of a month..."), _("Easter..."),
                              _("A ready-made holiday...")])
    if i < 0:
        return None
    months = [month(m) for m in range(1, 13)]
    name = None
    if i == 0:
        m = D.select(_("Month"), months)
        if m < 0:
            return None
        last = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[m]
        d = D.select(months[m], [str(k) for k in range(1, last + 1)])
        if d < 0:
            return None
        when = {"type": "date", "month": m + 1, "day": d + 1}
    elif i == 1:
        n = D.select(_("Which one in the month?"), nth_names())
        if n < 0:
            return None
        wd = D.select(_("Weekday"), P.day_names(False))
        if wd < 0:
            return None
        m = D.select(_("Month"), months)
        if m < 0:
            return None
        when = {"type": "nth", "n": -1 if n == 4 else n + 1, "weekday": wd, "month": m + 1}
    elif i == 2:
        j = D.select(_("Easter"), [_("Easter Sunday"), _("Good Friday (2 days before)"),
                                   _("Easter Monday (1 day after)"), _("Days before Easter..."),
                                   _("Days after Easter...")])
        if j < 0:
            return None
        off = (0, -2, 1)[j] if j < 3 else None
        if off is None:
            v = D.numeric(0, _("How many days?"), "1")
            if not v or int(v) < 1:
                return None
            off = min(int(v), 300) * (-1 if j == 3 else 1)
        when = {"type": "easter", "offset": off}
    else:
        j = D.select(_("A ready-made holiday"), [PRESET[k] for k, _r in specials.PRESETS])
        if j < 0:
            return None
        key, rule = specials.PRESETS[j]
        when = dict(rule)
        name = _("Thanksgiving") if key == "thanksgiving" else PRESET[key]
    j = D.select(when_text(when), [_("On the day itself"), _("The day after"), _("The day before"),
                                   _("Move by days...")])
    if j < 0:
        return None
    if j in (1, 2):
        when["shift"] = 1 if j == 1 else -1
    elif j == 3:
        v = D.numeric(0, _("How many days?"), "1")
        if not v or int(v) < 1:
            return None
        n = min(int(v), 300)
        k = D.select(when_text(when), [_("%d days later") % n, _("%d days earlier") % n])
        if k < 0:
            return None
        when["shift"] = n if k == 0 else -n
    return when, (name if name and not when.get("shift") else when_text(when))


def next_year(when):
    """(year, date) of the rule's next date from today on, or (None, None)."""
    t = today()
    for y in range(t.year - 1, t.year + specials.LOOKAHEAD + 1):
        d = specials.date_for(when, y)
        if d and d >= t:
            return y, d
    return None, None


def ask_repeat(when):
    """('yearly', None) / ('once', year) or None."""
    year, day = next_year(when)
    if year is None:
        return None
    once = (_("This year only (%s)") if day.year == today().year else _("Next time only (%s)")) % date_text(day)
    j = D.select(_("How often?"), [_("Every year"), once])
    if j < 0:
        return None
    return ("yearly", None) if j == 0 else ("once", year)


def ask_hours(blk=None):
    """(start, end) as 'HH:MM', or None."""
    j = D.select(_("Which hours?"), [_("All day (midnight to midnight)"),
                                     _("Broadcast day (%s to %s next morning)") % (P.clock(360), P.clock(360)),
                                     _("Choose hours...")])
    if j < 0:
        return None
    if j == 0:
        return "00:00", "00:00"
    if j == 1:
        return "06:00", "06:00"
    a = M.ask_time(_("Starts at"), (blk or {}).get("start", "18:00"))
    if not a:
        return None
    b = M.ask_time(_("Ends at (earlier than the start: the next morning)"), (blk or {}).get("end", "06:00"))
    if not b:
        return None
    return P.hhmm(P.mins(a)), P.hhmm(P.mins(b))


def ask_source(sp):
    """One source for a block, or None.  For Halloween, Thanksgiving and Christmas:
    also the holiday episodes of the channel's own shows."""
    season = specials.season_of(sp["when"])
    if season:
        j = D.select(_("What to air?"), [_("%s episodes of this channel's shows") % SEASON[season],
                                         _("Choose programming...")])
        if j < 0:
            return None
        if j == 0:
            return {"type": "holiday", "season": season}
    return M.pick_source()


def ask_order(current=None):
    keys = [o[0] for o in ORDERS]
    j = D.select(_("Episode order"), [o[1] for o in ORDERS], preselect=keys.index(current) if current in keys else 0)
    return keys[j] if j >= 0 else None


def ask_block(chans, sp, cid=None):
    """A new block for the special: channel, hours, what to air, order.  None on Back."""
    air = [c for c in chans if c["type"] in M.AIR_TYPES]
    ch = chan(air, cid) if cid else None
    if ch is None:
        j = D.select(_("Which channel?"), ["%3d  %s" % (c["number"], c["name"]) for c in air])
        if j < 0:
            return None
        ch = air[j]
    hours = ask_hours()
    if not hours:
        return None
    src = ask_source(sp)
    if not src:
        return None
    order = ask_order()
    if not order:
        return None
    return {"channel": ch["id"], "start": hours[0], "end": hours[1], "sources": [src], "order": order}


def checks(cal, sp, blk, chans):
    """The questions before a block is saved.  False: cancelled.  'Replace' takes the
    blocks it replaces out of `cal` (and out of `sp`) here."""
    ch = chan(chans, blk["channel"])
    if not ch:
        return False
    lineup = scheduler.Lineup(K.schedule_cfg())
    sched = lineup.schedule(ch, ensure=False)
    season = sched._holiday_source(blk)
    if season is not None:
        pool = sched._special_pool(blk)
        if not pool["series"] and not pool["singles"]:
            D.ok(_("Holidays and specials"), _("%s has no %s episodes.[CR]It will air its normal programming "
                                                "on the day.") % (ch["name"], SEASON.get(season, season)))
    day, _skipped = specials.next_date(dict(sp, blocks=[blk]), now())
    if not day:
        return True
    st, en = specials.window(blk, day)
    others = [o for o in cal if o["id"] != sp["id"]]
    same = specials.between(others, st, en, blk["channel"])
    own = [b for b in sp["blocks"] if b is not blk and b["channel"] == blk["channel"]
           and specials.window(b, day)[0] < en and specials.window(b, day)[1] > st]
    if same or own:
        names = []
        for name in [w[2]["name"] for w in same] + ([sp["name"]] if own else []):
            if name not in names:
                names.append(name)
        if not M.confirm_remove(_("%s already has %s in those hours.[CR]Replace it?") % (ch["name"], ", ".join(names)),
                                _("Replace")):
            return False
        for _a, _b, o, ob in same:
            if ob in o["blocks"]:
                o["blocks"].remove(ob)
        for b in own:
            sp["blocks"].remove(b)
        cal[:] = [o for o in cal if o["blocks"] or o["id"] == sp["id"]]
        others = [o for o in cal if o["id"] != sp["id"]]
    titles = dict((t.lower(), t) for t in sched._special_titles(blk))
    if titles:
        for _a, _b, o, ob in specials.between(others, st, en):
            och = chan(chans, ob["channel"])
            if not och or och["id"] == ch["id"]:
                continue
            both = [titles[t.lower()] for t in lineup.schedule(och, ensure=False)._special_titles(ob)
                    if t.lower() in titles]
            if both:
                if not M.confirm(_("%s is also in %s on %s at the same time.") % (both[0], o["name"], och["name"]),
                                 _("Keep both")):
                    return False
                break
    return True


def add_special(cal, chans, cid=None):
    """The steps of a new special; its id when it was added, None when cancelled."""
    r = ask_when()
    if not r:
        return None
    when, name = r
    rep = ask_repeat(when)
    if not rep:
        return None
    name = (D.input(_("Name"), name) or "").strip()
    if not name:
        return None
    sp = {"id": specials.new_id(), "name": name, "when": when, "repeat": rep[0], "blocks": []}
    if rep[0] == "once":
        sp["year"] = rep[1]
    blk = ask_block(chans, sp, cid)
    if not blk or not checks(cal, sp, blk, chans):
        return None
    sp["blocks"].append(blk)
    day, _skipped = specials.next_date(sp, now())
    text = "%s%s%s[CR]%s[CR]%s" % (date_text(day) if day else when_text(when), DOT, repeat_text(sp),
                                   block_text(chans, blk), order_text(blk, row=False))
    if not M.confirm(text, _("Add special"), heading=name):
        return None
    cal.append(sp)
    save(cal, [blk["channel"]], sp)
    D.notification(M.TITLE, _("%s added") % name, time=2500)
    return sp["id"]


# ------------------------------------------------------------------ a special's page
def special_page(sid):
    """One special: its name, date, channels; changes save as you go."""
    while True:
        chans = C.load()
        cal = load(chans)
        sp = specials.find(cal, sid)
        if not sp:
            return
        day, skipped = specials.next_date(sp, now())
        rows = [("name", _("Name: %s") % sp["name"], ""),
                ("when", _("When: %s") % when_text(sp["when"]),
                 (_("Next: %s") % date_text(day)) + ((DOT + _("skips this year")) if today().year in skipped else "")
                 if day else ""),
                ("repeat", _("Repeats: %s") % repeat_text(sp), "")]
        for k, b in enumerate(sp["blocks"]):
            rows.append(("block:%d" % k, block_text(chans, b), order_text(b)))
        rows += [("add", _("[B]+ Add another channel[/B]"), _("More programming for this special, on any channel")),
                 ("preview", _("[B]Preview the day[/B]"), _("What will air, channel by channel")),
                 ("remove", _("[COLOR red]Remove this special[/COLOR]"), "")]
        head = "%s%s%s" % (sp["name"], DOT, date_text(day)) if day else sp["name"]
        i = M.done_select(head, [M._menu_row(r[1], r[2]) for r in rows], useDetails=True)
        if i < 0:
            return
        key = rows[i][0]
        mine = [b["channel"] for b in sp["blocks"]]
        if key == "name":
            v = (D.input(_("Name"), sp["name"]) or "").strip()
            if v and v != sp["name"]:
                sp["name"] = v
                save(cal, mine)
        elif key == "when":
            r = ask_when()
            if r and r[0] != sp["when"]:
                sp["when"] = r[0]
                if sp.get("repeat") == "once":
                    sp["year"] = next_year(r[0])[0] or sp["year"]
                if all(checks(cal, sp, b, chans) for b in list(sp["blocks"]) if b in sp["blocks"]):
                    save(cal, mine, sp)
        elif key == "repeat":
            rep = ask_repeat(sp["when"])
            if rep:
                sp["repeat"] = rep[0]
                sp.pop("year", None)
                if rep[0] == "once":
                    sp["year"] = rep[1]
                save(cal, mine)
        elif key.startswith("block:"):
            edit_block(cal, sp, sp["blocks"][int(key[6:])], chans)
        elif key == "add":
            blk = ask_block(chans, sp)
            if blk and checks(cal, sp, blk, chans):
                sp["blocks"].append(blk)
                save(cal, mine + [blk["channel"]], sp)
                D.notification(M.TITLE, _("%s added") % block_text(chans, blk), time=2500)
        elif key == "preview":
            preview(sp, chans)
        elif key == "remove":
            if M.confirm_remove(_("Remove %s?[CR]Its channels air their normal programming on the day.") % sp["name"]):
                cal.remove(sp)
                save(cal, mine)
                return


def edit_block(cal, sp, blk, chans):
    """One channel's programming in a special: hours, what airs, order, remove."""
    rows = [_("Change the hours (%s)") % hours_text(blk), _("Change what airs (%s)") % source_text(blk),
            _("Change the order (%s)") % order_text(blk), _("Remove this channel from the special"), _("Cancel")]
    i = D.select(block_text(chans, blk), rows)
    if i < 0 or i == 4:
        return
    new = dict(blk)
    if i == 0:
        hours = ask_hours(blk)
        if not hours:
            return
        new["start"], new["end"] = hours
    elif i == 1:
        src = ask_source(sp)
        if not src:
            return
        new["sources"] = [src]
    elif i == 2:
        order = ask_order(blk.get("order"))
        if not order:
            return
        new["order"] = order
    elif i == 3:
        last = len(sp["blocks"]) == 1
        text = (_("Remove %s?[CR]It is the special's only channel: %s is removed too.") % (block_text(chans, blk), sp["name"])
                if last else _("Remove %s from %s?") % (block_text(chans, blk), sp["name"]))
        if M.confirm_remove(text):
            sp["blocks"].remove(blk)
            if last:
                cal.remove(sp)
            save(cal, [blk["channel"]])
        return
    if new == blk:
        return
    k = sp["blocks"].index(blk)
    sp["blocks"][k] = new
    if checks(cal, sp, new, chans):
        save(cal, [new["channel"]], sp)


# ------------------------------------------------------------------ preview the day
def preview(sp, chans):
    """What will air on the special's next date, channel by channel (read-only)."""
    from .tv import fmt_time
    cfg = K.schedule_cfg()
    off = scheduler.specials_shift(cfg)
    day, _skipped = specials.next_date(sp, now())
    if not day:
        D.ok(_("Holidays and specials"), _("%s has no date coming up.") % sp["name"])
        return
    lineup = scheduler.Lineup(cfg)
    lines = []
    for blk in sp["blocks"]:
        ch = chan(chans, blk["channel"])
        if not ch:
            continue
        sched = lineup.schedule(ch, ensure=False)
        st, en = specials.window(blk, day)
        st, en = st - off, en - off
        lines.append("[B]%s[/B]   %s%s%s" % (chan_name(ch), hours_text(blk), DOT, order_text(blk)))
        planned = [b for b in sched.blocks_between(st, en) if b.get("sp")]
        if planned:
            for b in planned:
                extra = " ".join(x for x in (b.get("lb", ""), b.get("sub", "")) if x)
                lines.append(_("[B]%8s[/B]   %s   [COLOR grey]%s[/COLOR]") % (fmt_time(b["s"]), b["t"], extra))
            if sched.data["until"] < en - 60:
                lines.append("[COLOR grey]%s[/COLOR]" % _("The rest of the day isn't planned yet."))
        else:
            lines += _simulate(sched, sp, blk, st, en, fmt_time)
        lines.append("")
    D.textviewer("%s%s%s" % (sp["name"], DOT, date_text(day)), "[CR]".join(lines))


def _simulate(sched, sp, blk, st, en, fmt_time):
    """The day as the scheduler would plan it now, without planning it: in-order
    blocks from their bookmarks; a random block just says what it picks from."""
    pool = sched._special_pool(blk)
    series, singles = pool["series"], pool["singles"]
    if not series and not singles:
        return ["[COLOR grey]%s[/COLOR]" % _("Nothing to air: the channel's normal programming.")]
    if blk.get("order") == "random":
        names = [s["title"] for s in series] + ([_("%d movies") % len(singles)] if singles else [])
        return [_("Random picks from: %s") % (", ".join(names[:6]) + (" ..." if len(names) > 6 else ""))]
    rid = "event:%s" % sp["id"]
    state = sched.data.get("state", {})
    cont = blk.get("order") == "continue"
    last = state.get("last", {}) if cont else {}
    turn = (state.get("rr", {}).get(rid, 0) if cont else 0)
    shows = [(ser["key"], ser["episodes"]) for ser in series] + ([("movies", singles)] if singles else [])
    at = {}
    slot = sched.slot
    out, t = [], st
    while t < en - 60 and len(out) < 100:
        for k in range(len(shows)):
            key, eps = shows[(turn + k) % len(shows)]
            if key in at:
                idx = (at[key] + 1) % len(eps)
            else:
                prev = last.get("%s|%s" % (rid, key))
                idx = next(((j + 1) % len(eps) for j, e in enumerate(eps) if e["path"] == prev), 0)
            ep = eps[idx]
            dur = float(ep["dur"])
            if dur > en - t - 2:
                continue
            at[key] = idx
            turn += k + 1
            extra = " ".join(x for x in (ep.get("label") or "", ep.get("sub") or "") if x)
            out.append(_("[B]%8s[/B]   %s   [COLOR grey]%s[/COLOR]") % (fmt_time(t), ep["title"], extra))
            t = min(en, scheduler.ceil_slot(t + dur + 2, slot)) if slot else t + dur
            break
        else:
            break
    return out
