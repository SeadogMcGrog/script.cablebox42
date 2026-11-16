"""Holidays and specials: the date rules and hours of resources/lib/specials.py,
checked outside Kodi against dates known from the calendar (2026-2030).

    python .claude/tools/specials_check.py [-v]

Ends PASS or FAIL (exit code 1)."""
import datetime
import importlib.util
import os
import sys
import tempfile
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# loaded by file name, so no Kodi stubs and no package import are needed
spec = importlib.util.spec_from_file_location("cb_specials", os.path.join(REPO, "resources", "lib", "specials.py"))
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

VERBOSE = "-v" in sys.argv
D = datetime.date
fails = []
count = 0


def check(what, got, want):
    global count
    count += 1
    ok = got == want
    if not ok:
        fails.append(what)
    if VERBOSE or not ok:
        print("%s  %s: %s%s" % ("ok  " if ok else "FAIL", what, got, "" if ok else "   (expected %s)" % (want,)))


def ts(y, mo, d, h=0, mi=0):
    return time.mktime((y, mo, d, h, mi, 0, 0, 0, -1))


MON, THU, FRI, SUN = 0, 3, 4, 6
RULES = {
    "US Thanksgiving (4th Thursday of November)": (
        {"type": "nth", "n": 4, "weekday": THU, "month": 11}, THU,
        [(11, 26), (11, 25), (11, 23), (11, 22), (11, 28)]),
    "Canadian Thanksgiving (2nd Monday of October)": (
        {"type": "nth", "n": 2, "weekday": MON, "month": 10}, MON,
        [(10, 12), (10, 11), (10, 9), (10, 8), (10, 14)]),
    "Last Monday of May": (
        {"type": "nth", "n": -1, "weekday": MON, "month": 5}, MON,
        [(5, 25), (5, 31), (5, 29), (5, 28), (5, 27)]),
    "Easter Sunday": (
        {"type": "easter", "offset": 0}, SUN,
        [(4, 5), (3, 28), (4, 16), (4, 1), (4, 21)]),
    "Good Friday (2 days before Easter)": (
        {"type": "easter", "offset": -2}, FRI,
        [(4, 3), (3, 26), (4, 14), (3, 30), (4, 19)]),
    "Easter Monday (1 day after Easter)": (
        {"type": "easter", "offset": 1}, MON,
        [(4, 6), (3, 29), (4, 17), (4, 2), (4, 22)]),
    "31 December": (
        {"type": "date", "month": 12, "day": 31}, None,
        [(12, 31)] * 5),
    "Day after US Thanksgiving (shift 1)": (
        {"type": "nth", "n": 4, "weekday": THU, "month": 11, "shift": 1}, FRI,
        [(11, 27), (11, 26), (11, 24), (11, 23), (11, 29)]),
}
YEARS = range(2026, 2031)

print("Date rules, 2026-2030")
for name, (rule, weekday, days) in RULES.items():
    got = [C.date_for(rule, y) for y in YEARS]
    check(name, got, [D(y, m, d) for y, (m, d) in zip(YEARS, days)])
    if weekday is not None:
        check(name + ": weekday", [g.weekday() if g else None for g in got], [weekday] * 5)
    print("      %-46s %s" % (name, "  ".join(g.strftime("%a %d %b %Y") if g else "-" for g in got)))

leap = {"type": "date", "month": 2, "day": 29}
check("29 February skips non-leap years", [C.date_for(leap, y) for y in YEARS],
      [None, None, D(2028, 2, 29), None, None])
check("5th Thursday of November: only when there is one",
      [C.date_for({"type": "nth", "n": 5, "weekday": THU, "month": 11}, y) for y in YEARS],
      [None, None, D(2028, 11, 30), D(2029, 11, 29), None])
check("Last Monday of December", C.date_for({"type": "nth", "n": -1, "weekday": MON, "month": 12}, 2026), D(2026, 12, 28))
check("31 December + 1 lands in the next year", C.date_for({"type": "date", "month": 12, "day": 31, "shift": 1}, 2026),
      D(2027, 1, 1))
check("Easter in other years", [C.easter(y) for y in (1943, 2000, 2011, 2019, 2024, 2025, 2038)],
      [D(1943, 4, 25), D(2000, 4, 23), D(2011, 4, 24), D(2019, 4, 21), D(2024, 3, 31), D(2025, 4, 20), D(2038, 4, 25)])
try:
    from dateutil.easter import easter as du_easter
    check("Easter 1900-2199 against dateutil", [C.easter(y) for y in range(1900, 2200)],
          [du_easter(y) for y in range(1900, 2200)])
except ImportError:
    print("      (dateutil not installed: Easter checked against the table only)")
check("Easter is always a Sunday, 22 March - 25 April (1900-2199)",
      all(C.easter(y).weekday() == SUN and D(y, 3, 22) <= C.easter(y) <= D(y, 4, 25) for y in range(1900, 2200)), True)
check("Ready-made Thanksgiving is the 4th Thursday", dict(C.PRESETS)["thanksgiving"],
      {"type": "nth", "n": 4, "weekday": THU, "month": 11})
check("Every ready-made holiday is a valid rule", [k for k, r in C.PRESETS if not C.valid(r)], [])
check("Broken rules give no date", [C.date_for(r, 2026) for r in (
    None, {}, {"type": "date", "month": 13, "day": 1}, {"type": "date", "month": 2, "day": 30},
    {"type": "nth", "n": 0, "weekday": 3, "month": 11}, {"type": "nth", "n": 4, "weekday": 7, "month": 11},
    {"type": "moon"}, {"type": "easter", "offset": "x"})], [None] * 8)

print("Hours")
tg = {"id": "tg0001", "name": "Thanksgiving", "repeat": "yearly", "when": RULES["US Thanksgiving (4th Thursday of November)"][0],
      "blocks": [{"channel": "c24", "start": "00:00", "end": "00:00", "sources": [{"type": "show"}], "order": "continue"}]}
nye = {"id": "nye001", "name": "New Year's Eve", "repeat": "yearly", "when": {"type": "date", "month": 12, "day": 31},
       "blocks": [{"channel": "c31", "start": "18:00", "end": "06:00", "sources": [{"type": "show"}], "order": "first"}]}
bday = {"id": "bd0001", "name": "Christmas Day", "repeat": "yearly", "when": {"type": "date", "month": 12, "day": 25},
        "blocks": [{"channel": "c05", "start": "06:00", "end": "06:00", "sources": [], "order": "random"},
                   {"channel": "c09", "start": "20:00", "end": "23:00", "sources": [], "order": "first"}]}
once = {"id": "once01", "name": "One-off", "repeat": "once", "year": 2026, "when": {"type": "date", "month": 7, "day": 1},
        "blocks": [{"channel": "c24", "start": "12:00", "end": "14:00", "sources": [], "order": "first"}]}
ALL = [tg, nye, bday, once]


def on(ch, *when):
    sp, _b, st, en = C.at(ALL, ch, ts(*when))
    return (sp["name"], time.strftime("%d %b %H:%M", time.localtime(st)), time.strftime("%d %b %H:%M", time.localtime(en))) \
        if sp else None


check("All day: midnight to midnight", C.window(tg["blocks"][0], D(2026, 11, 26)), (ts(2026, 11, 26), ts(2026, 11, 27)))
check("Broadcast day: 6 AM to 6 AM", C.window(bday["blocks"][0], D(2026, 12, 25)), (ts(2026, 12, 25, 6), ts(2026, 12, 26, 6)))
check("6 PM to 6 AM", C.window(nye["blocks"][0], D(2026, 12, 31)), (ts(2026, 12, 31, 18), ts(2027, 1, 1, 6)))
check("Thanksgiving 2026 at 00:00", on("c24", 2026, 11, 26, 0, 0), ("Thanksgiving", "26 Nov 00:00", "27 Nov 00:00"))
check("Thanksgiving 2026 at 23:59", on("c24", 2026, 11, 26, 23, 59), ("Thanksgiving", "26 Nov 00:00", "27 Nov 00:00"))
check("Friday after: nothing", on("c24", 2026, 11, 27, 0, 0), None)
check("Wednesday before, 23:59: nothing", on("c24", 2026, 11, 25, 23, 59), None)
check("Thanksgiving 2027 is 25 November", on("c24", 2027, 11, 25, 12), ("Thanksgiving", "25 Nov 00:00", "26 Nov 00:00"))
check("26 November 2027: nothing", on("c24", 2027, 11, 26, 12), None)
check("Another channel on Thanksgiving: nothing", on("c31", 2026, 11, 26, 12), None)
check("New Year's Eve 17:59: nothing", on("c31", 2026, 12, 31, 17, 59), None)
check("New Year's Eve 18:00", on("c31", 2026, 12, 31, 18), ("New Year's Eve", "31 Dec 18:00", "01 Jan 06:00"))
check("1 January 03:00: still on", on("c31", 2027, 1, 1, 3), ("New Year's Eve", "31 Dec 18:00", "01 Jan 06:00"))
check("1 January 06:00: over", on("c31", 2027, 1, 1, 6), None)
check("1 January 2026 03:00 (last year's)", on("c31", 2026, 1, 1, 3), ("New Year's Eve", "31 Dec 18:00", "01 Jan 06:00"))
check("Christmas Day 05:59 on the broadcast-day channel: nothing", on("c05", 2026, 12, 25, 5, 59), None)
check("Boxing Day 05:59: still on", on("c05", 2026, 12, 26, 5, 59), ("Christmas Day", "25 Dec 06:00", "26 Dec 06:00"))
check("Christmas Day 20:30 on the movie channel", on("c09", 2026, 12, 25, 20, 30), ("Christmas Day", "25 Dec 20:00", "25 Dec 23:00"))
check("This year only: on in 2026", on("c24", 2026, 7, 1, 13), ("One-off", "01 Jul 12:00", "01 Jul 14:00"))
check("This year only: not in 2027", on("c24", 2027, 7, 1, 13), None)

print("Boundaries for the planner")
check("Next change before Thanksgiving is its start", C.next_change(ALL, "c24", ts(2026, 11, 25, 20)), ts(2026, 11, 26))
check("Next change during Thanksgiving is its end", C.next_change(ALL, "c24", ts(2026, 11, 26, 9)), ts(2026, 11, 27))
check("At the start itself: the end", C.next_change(ALL, "c24", ts(2026, 11, 26)), ts(2026, 11, 27))
check("Nothing within 8 days", C.next_change(ALL, "c24", ts(2026, 9, 1)), None)
check("New Year's Eve from 30 December", C.next_change(ALL, "c31", ts(2026, 12, 30, 12)), ts(2026, 12, 31, 18))
check("After midnight: 6 AM", C.next_change(ALL, "c31", ts(2027, 1, 1, 0, 30)), ts(2027, 1, 1, 6))
wk = C.between(ALL, ts(2026, 12, 21), ts(2026, 12, 28))
check("Christmas week: the two Christmas blocks", [(w[2]["name"], w[3]["channel"]) for w in wk],
      [("Christmas Day", "c05"), ("Christmas Day", "c09")])
check("The week after Thanksgiving: nothing", C.between(ALL, ts(2026, 11, 30), ts(2026, 12, 7)), [])

print("The list")
now = ts(2026, 11, 15, 12)
check("Soonest first, from 15 November 2026", [(d.isoformat(), sp["name"]) for d, sp, _s in C.upcoming(ALL, now)],
      [("2026-11-26", "Thanksgiving"), ("2026-12-25", "Christmas Day"), ("2026-12-31", "New Year's Eve")])
check("Thanksgiving evening: still this year's", C.next_date(tg, ts(2026, 11, 26, 22))[0], D(2026, 11, 26))
check("The day after: next year's", C.next_date(tg, ts(2026, 11, 27, 0, 1))[0], D(2027, 11, 25))
check("1 January 03:00: New Year's Eve still on", C.next_date(nye, ts(2027, 1, 1, 3))[0], D(2026, 12, 31))
check("1 January 07:00: next year's", C.next_date(nye, ts(2027, 1, 1, 7))[0], D(2027, 12, 31))
check("This year only, before its date", C.next_date(once, ts(2026, 6, 1))[0], D(2026, 7, 1))
check("This year only, after: gone", (C.next_date(once, now)[0], C.expired(once, now)), (None, True))
check("Every year is never expired", C.expired(tg, ts(2040, 1, 1)), False)
ld = dict(tg, id="leap01", when=leap)
check("29 February from March 2028: 2032, and the list says which years it skips", C.next_date(ld, ts(2028, 3, 1)),
      (D(2032, 2, 29), [2029, 2030, 2031]))
check("29 February from 2026: 2028, skipping 2026 and 2027", C.next_date(ld, ts(2026, 11, 15)), (D(2028, 2, 29), [2026, 2027]))
clash = dict(tg, id="clash1", name="Clash", blocks=[dict(tg["blocks"][0], start="20:00", end="22:00")])
check("Two specials on one channel at the same hours are found", [(o["name"], c) for o, c in C.overlapping(ALL + [clash], clash)],
      [("Thanksgiving", "c24")])
check("No overlap on another channel", C.overlapping(ALL, dict(clash, blocks=[dict(clash["blocks"][0], channel="c31")])), [])
check("Marathon bookmark key", C.bookmark_key(tg, "Mystery Science Theater 3000"), "event:tg0001|tv:Mystery Science Theater 3000")

print("calendar.json")
tmp = os.path.join(tempfile.mkdtemp(prefix="cbcal"), "calendar.json")
check("No file: no specials", C.load(tmp), [])
kept = C.save(ALL, tmp, now=now)
check("Saving drops the passed 'this year only' special", [sp["id"] for sp in kept], ["tg0001", "nye001", "bd0001"])
check("Saved and read back unchanged", C.load(tmp), [tg, nye, bday])
with open(tmp, "w", encoding="utf-8") as f:
    f.write('{"specials": [{"id": "x", "when": {"type": "moon"}}, 7, {"id": "ok", "when": {"type": "easter"},'
            ' "blocks": [{"channel": "c1", "sources": []}, {"start": "01:00"}]}]}')
os.utime(tmp, (time.time() + 5, time.time() + 5))
got = C.load(tmp)
check("Broken entries are left out, the rest kept", [(sp["id"], sp["repeat"], len(sp["blocks"]), sp["blocks"][0]["order"]) for sp in got],
      [("ok", "yearly", 1, "continue")])
with open(tmp, "w", encoding="utf-8") as f:
    f.write("{not json")
os.utime(tmp, (time.time() + 10, time.time() + 10))
check("An unreadable file: no specials", C.load(tmp), [])
os.remove(tmp)
os.rmdir(os.path.dirname(tmp))

print("%d checks, %d failed" % (count, len(fails)))
print("FAIL" if fails else "PASS")
sys.exit(1 if fails else 0)
