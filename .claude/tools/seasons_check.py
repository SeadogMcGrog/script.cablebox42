"""Holiday seasons: resources/lib/seasons.py checked outside Kodi (Windows or the rig).

    python .claude/tools/seasons_check.py [-v] [REF]

1. With no seasons.json, phase() gives the same (season, level) as the reference
   seasons.py (git REF, default 5407b15 = ~all6) for every day 2020-2035, for every
   combination of the three On switches and the three intensities; and again with
   the built-in rules written out explicitly in a seasons.json.
2. out_of_season() / holiday_of() agree with the reference on sample titles.
3. New cases: Canadian Thanksgiving, Easter, a window across New Year, 29 February,
   which season wins, extra title words, holds of the viewer's own seasons, and
   clean() dropping broken entries.
Ends PASS or FAIL (exit code 1)."""
import datetime
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LIB = os.path.join(REPO, "resources", "lib")
VERBOSE = "-v" in sys.argv
args = [a for a in sys.argv[1:] if a != "-v"]
REF = args[0] if args else "5407b15"

LIBRARY_STUB = '''
def rpc(*a, **k):
    return {}
def _filtered_movies(*a):
    return []
def _filtered_shows(*a):
    return []
def episodes_for(*a):
    return []
'''
KODIUTIL_STUB = '''
def log(*a, **k):
    pass
PROFILE = %r
'''


def package(name, seasons_src, profile):
    """A package `name` with seasons.py, the real specials.py and stub library/kodiutil."""
    root = os.path.join(TMP, name)
    os.makedirs(root)
    open(os.path.join(root, "__init__.py"), "w").close()
    open(os.path.join(root, "library.py"), "w").write(LIBRARY_STUB)
    open(os.path.join(root, "kodiutil.py"), "w").write(KODIUTIL_STUB % profile)
    shutil.copy(os.path.join(LIB, "specials.py"), os.path.join(root, "specials.py"))
    open(os.path.join(root, "seasons.py"), "w", encoding="utf-8").write(seasons_src)
    return importlib.import_module(name + ".seasons")


TMP = tempfile.mkdtemp(prefix="seasons_check_")
sys.path.insert(0, TMP)
ref_src = subprocess.check_output(["git", "-C", REPO, "show", "%s:resources/lib/seasons.py" % REF]).decode("utf-8")
OLD = package("cb_old", ref_src, TMP)
NEW = package("cb_new", open(os.path.join(LIB, "seasons.py"), encoding="utf-8").read(), TMP)

fails = []
count = [0]


def check(what, got, want):
    count[0] += 1
    ok = got == want
    if not ok:
        fails.append(what)
    if VERBOSE or not ok:
        print("%s  %s: %s%s" % ("ok  " if ok else "FAIL", what, got, "" if ok else "   (expected %s)" % (want,)))


def ts(day, hour=12):
    return time.mktime((day.year, day.month, day.day, hour, 0, 0, 0, 0, -1))


def cfg(on=True, intensity=1, hold=True, flags=(True, True, True), extra=None):
    sc = {"on": on, "intensity": intensity, "hold": hold}
    for name, f in zip(("halloween", "thanksgiving", "christmas"), flags):
        sc[name] = {"on": f, "ads": "", "bumps": "", "tags": None, "genres": None}
    if extra is not None:
        NEW.apply_file(sc, extra)
    return {"seasons": sc}


D = datetime.date
DAYS = []
d = D(2020, 1, 1)
while d <= D(2035, 12, 31):
    DAYS.append(d)
    d += datetime.timedelta(days=1)

# ---------------------------------------------------------------- 1. same as the reference
explicit = {"builtin": {n: {k: NEW.RULES[n][k] for k in NEW.RULE_KEYS} for n in NEW.BUILTIN}}
for label, extra in (("no seasons.json", None), ("built-in rules written out", explicit)):
    diff = 0
    first = None
    combos = 0
    for on in (True, False):
        for intensity in (0, 1, 2):
            for f in range(8):
                flags = (bool(f & 1), bool(f & 2), bool(f & 4))
                c_old = cfg(on, intensity, flags=flags)
                c_new = cfg(on, intensity, flags=flags, extra=extra)
                combos += 1
                for day in DAYS:
                    t = ts(day)
                    a, b = OLD.phase(t, c_old), NEW.phase(t, c_new)
                    if a != b:
                        diff += 1
                        first = first or (day, flags, intensity, a, b)
    check("phase, %s: days x combinations that differ (%d days, %d combinations)" % (label, len(DAYS), combos),
          (diff, first), (0, None))

# no seasons.json leaves the config exactly as the settings made it (no extra keys: no needless refresh)
c = cfg()
before = repr(c)
NEW.apply_file(c["seasons"], None)
check("apply_file(None) changes nothing", repr(c), before)
c = cfg()
NEW.apply_file(c["seasons"], {"builtin": {}, "custom": []})
check("an empty seasons.json changes nothing", repr(c), before)

# ---------------------------------------------------------------- 2. holds agree with the reference
TITLES = ["A Charlie Brown Christmas", "Treehouse of Horror V", "The Thanksgiving Show", "Ghost Story",
          "Seinfeld", "The Contest", "Home Alone", "Hocus Pocus", "Pumpkin Patch", "Turkey Day",
          "Halloween", "The Great Pumpkin", "Planes, Trains and Automobiles", "Boo!", "Silent Night"]
diff = []
for hold in (True, False):
    for f in (7, 6, 0):
        flags = (bool(f & 1), bool(f & 2), bool(f & 4))
        for day in (D(2026, 7, 4), D(2026, 10, 31), D(2026, 10, 15), D(2026, 11, 26), D(2026, 12, 10),
                    D(2026, 12, 25), D(2027, 1, 2)):
            for title in TITLES:
                it = {"path": "/tv/%s.mkv" % title, "title": title, "sub": ""}
                a = OLD.out_of_season(it, ts(day), cfg(hold=hold, flags=flags))
                b = NEW.out_of_season(it, ts(day), cfg(hold=hold, flags=flags))
                if a != b:
                    diff.append((title, day, hold, flags, a, b))
check("out_of_season agrees with the reference (%d cases)" % (2 * 3 * 7 * len(TITLES)), diff[:3], [])
diff = [t for t in TITLES if OLD.holiday_of({"path": "/x/" + t, "title": t}) !=
        NEW.holiday_of({"path": "/x/" + t, "title": t}, cfg())]
check("holiday_of agrees with the reference", diff, [])


# ---------------------------------------------------------------- 3. new cases
def phase(day, extra, **kw):
    s, lv = NEW.phase(ts(day), cfg(extra=extra, **kw))
    return s, round(lv, 4)


CA = {"builtin": {"thanksgiving": {"from": NEW.THANKSGIVING_CA}}}
check("Canada: 2nd Monday of October 2026 is Thanksgiving (beats Halloween's run-up)",
      phase(D(2026, 10, 12), CA)[0], "thanksgiving")
check("Canada: the day before is Halloween's run-up", phase(D(2026, 10, 11), CA)[0], "halloween")
check("Canada: US Thanksgiving Day 2026 is nothing", phase(D(2026, 11, 26), CA), (None, 0.0))
check("Canada: Christmas run-up still from the day after the US date", phase(D(2026, 11, 27), CA)[0], "christmas")
check("Canada 2027: 11 October", phase(D(2027, 10, 11), CA), ("thanksgiving", 1.0))
check("US 2026: 26 November", phase(D(2026, 11, 26), None), ("thanksgiving", 1.0))

EARLY = {"builtin": {"halloween": {"run_up": {"type": "date", "month": 9, "day": 15}}}}
check("Halloween run-up from 15 September: 15 Sep is its first day", phase(D(2026, 9, 15), EARLY),
      ("halloween", 0.1))
check("... 14 Sep is nothing", phase(D(2026, 9, 14), EARLY), (None, 0.0))
check("... 30 Oct ends at the top of the ramp", phase(D(2026, 10, 30), EARLY), ("halloween", 0.45))
check("... 31 Oct is the big day", phase(D(2026, 10, 31), EARLY), ("halloween", 1.0))
check("Halloween with its own intensity Lots", phase(D(2026, 10, 1), {"builtin": {"halloween": {"intensity": 2}}}),
      ("halloween", 0.25))


def custom(sid, name, run_up, frm, days=1, **kw):
    c = {"id": sid, "name": name, "on": True, "run_up": run_up, "from": frm, "days": days}
    c.update(kw)
    return c


EASTER = {"custom": [custom("s_easter", "Easter", {"type": "easter", "offset": -14},
                            {"type": "easter", "offset": 0})]}
check("Easter 2027 (28 March) is its big day", phase(D(2027, 3, 28), EASTER), ("s_easter", 1.0))
check("Easter run-up starts 14 March 2027", phase(D(2027, 3, 14), EASTER), ("s_easter", 0.1))
check("13 March 2027 is nothing", phase(D(2027, 3, 13), EASTER), (None, 0.0))
check("Easter Monday 2027 is nothing", phase(D(2027, 3, 29), EASTER), (None, 0.0))
check("Easter 2030 (21 April)", phase(D(2030, 4, 21), EASTER), ("s_easter", 1.0))
check("Easter switched off", phase(D(2027, 3, 28), {"custom": [dict(EASTER["custom"][0], on=False)]}),
      (None, 0.0))
check("all seasons off (Settings) switches yours off too", phase(D(2027, 3, 28), EASTER, on=False), (None, 0.0))

NY = {"custom": [custom("s_ny", "New Year", {"type": "date", "month": 12, "day": 26},
                        {"type": "date", "month": 12, "day": 31}, 2)]}
check("New Year run-up on 26 Dec 2026", phase(D(2026, 12, 26), NY)[0], "s_ny")
check("Christmas Day still Christmas", phase(D(2026, 12, 25), NY), ("christmas", 1.0))
check("31 Dec 2026 big day", phase(D(2026, 12, 31), NY), ("s_ny", 1.0))
check("1 Jan 2027 big day (across New Year)", phase(D(2027, 1, 1), NY), ("s_ny", 1.0))
check("2 Jan 2027 nothing", phase(D(2027, 1, 2), NY), (None, 0.0))
check("26 Dec 2027 run-up again", phase(D(2027, 12, 26), NY)[0], "s_ny")

LEAP = {"custom": [custom("s_leap", "Leap Day", {"type": "date", "month": 2, "day": 22},
                          {"type": "date", "month": 2, "day": 29})]}
check("29 February 2028 big day", phase(D(2028, 2, 29), LEAP), ("s_leap", 1.0))
check("22 February 2028 run-up", phase(D(2028, 2, 22), LEAP)[0], "s_leap")
check("2027 has no leap day: 28 Feb nothing", phase(D(2027, 2, 28), LEAP), (None, 0.0))
check("2027 has no leap day: 1 Mar nothing", phase(D(2027, 3, 1), LEAP), (None, 0.0))

TWO = {"custom": [custom("s_a", "A", {"type": "date", "month": 10, "day": 20}, {"type": "date", "month": 10, "day": 25}),
                  custom("s_b", "B", None, {"type": "date", "month": 10, "day": 25})]}
check("a big day beats a run-up (yours over Halloween's run-up)", phase(D(2026, 10, 25), TWO)[0], "s_a")
check("two big days: the higher in the list", phase(D(2026, 10, 25), {"custom": TWO["custom"][::-1]})[0], "s_b")
check("two run-ups: the higher in the list (Halloween first)", phase(D(2026, 10, 21), TWO)[0], "halloween")

LONG = {"custom": [custom("s_long", "Two weeks", {"type": "before", "days": 3}, {"type": "date", "month": 7, "day": 1}, 14)]}
check("14 big days: 1 July is the first", phase(D(2026, 7, 1), LONG), ("s_long", 1.0))
check("14 big days: 14 July is the last", phase(D(2026, 7, 14), LONG), ("s_long", 1.0))
check("14 big days: 15 July is nothing", phase(D(2026, 7, 15), LONG), (None, 0.0))
check("run-up 3 days before: 28 June starts it", phase(D(2026, 6, 28), LONG), ("s_long", 0.1))
check("run-up 3 days before: 30 June ends it", phase(D(2026, 6, 30), LONG), ("s_long", 0.45))
check("run-up 3 days before: 27 June is nothing", phase(D(2026, 6, 27), LONG), (None, 0.0))
check("days past 14 are cut to 14", phase(D(2026, 7, 20), {"custom": [dict(LONG["custom"][0], days=30)]}), (None, 0.0))
check("a built-in's own name", cfg(extra={"builtin": {"christmas": {"name": "Noel"}}})["seasons"]["christmas"]["name"],
      "Noel")

# extra title words
WORDS = {"builtin": {"christmas": {"words": ["Festivus"]}}}
it = {"path": "/tv/Seinfeld S09E10 The Strike.mkv", "title": "Seinfeld", "sub": "The Strike - Festivus"}
check("an extra Christmas word counts as Christmas material", NEW.is_seasonal(it, "christmas", set(), cfg(extra=WORDS)), True)
check("... and not without it", NEW.is_seasonal(it, "christmas", set(), cfg()), False)
check("... and is held outside Christmas", NEW.out_of_season(it, ts(D(2026, 7, 4)), cfg(extra=WORDS)), True)
check("... and airs in it", NEW.out_of_season(it, ts(D(2026, 12, 10)), cfg(extra=WORDS)), False)
it2 = {"path": "/tv/x.mkv", "title": "Pumpkin Patrol", "sub": ""}
check("an extra Halloween word isn't held (only explicit Halloween is)",
      NEW.out_of_season(it2, ts(D(2026, 7, 4)), cfg(extra={"builtin": {"halloween": {"words": ["patrol"]}}})), False)

# holds of the viewer's own seasons
SHARK = custom("s_shark", "Shark Week", {"type": "date", "month": 7, "day": 25}, {"type": "date", "month": 8, "day": 1},
               7, words=["shark"])
jaws = {"path": "/movies/Jaws.mkv", "title": "Jaws: The Shark", "sub": ""}
check("hold off (the default): a Shark Week film airs in March",
      NEW.out_of_season(jaws, ts(D(2026, 3, 1)), cfg(extra={"custom": [SHARK]})), False)
check("hold on: kept off in March", NEW.out_of_season(jaws, ts(D(2026, 3, 1)),
                                                       cfg(extra={"custom": [dict(SHARK, hold=True)]})), True)
check("hold on: airs in Shark Week", NEW.out_of_season(jaws, ts(D(2026, 8, 3)),
                                                        cfg(extra={"custom": [dict(SHARK, hold=True)]})), False)
check("Christmas hold switched off in the editor only",
      NEW.out_of_season({"path": "/a", "title": "A Charlie Brown Christmas"}, ts(D(2026, 7, 4)),
                        cfg(extra={"builtin": {"christmas": {"hold": False}}})), False)
check("... Thanksgiving still held",
      NEW.out_of_season({"path": "/b", "title": "Turkey Day"}, ts(D(2026, 7, 4)),
                        cfg(extra={"builtin": {"christmas": {"hold": False}}})), True)

# clean()
bad = {"builtin": {"halloween": {"run_up": {"type": "date", "month": 13, "day": 1}, "intensity": 7, "words": "x"},
                   "easter": {"from": {"type": "date", "month": 1, "day": 1}}},
       "custom": [{"id": "nope", "from": {"type": "date", "month": 1, "day": 1}},
                  {"id": "s_ok", "from": {"type": "date", "month": 1, "day": 1}, "days": 2},
                  {"id": "s_ok", "from": {"type": "date", "month": 1, "day": 1}, "days": 2},
                  {"id": "s_bad", "from": {"type": "nth", "n": 9}},
                  {"id": "s_bad2", "from": {"type": "date", "month": 1, "day": 1}, "run_up": {"type": "before", "days": 0}}]}
got = NEW.clean(bad)
check("clean: broken overrides and seasons are left out", (got["builtin"], [c["id"] for c in got["custom"]]),
      ({}, ["s_ok"]))
check("clean: a season keeps its days", got["custom"][0]["days"], 2)
check("clean: a custom season's hold is off unless set", got["custom"][0]["hold"], False)
check("clean(garbage)", NEW.clean([1, 2]), {"builtin": {}, "custom": []})
c = cfg(extra={"custom": [SHARK]})["seasons"]
check("order: built-ins first, then yours", c["order"], ["thanksgiving", "halloween", "christmas", "s_shark"])

shutil.rmtree(TMP, ignore_errors=True)
print("%d checks, %d failed: %s" % (count[0], len(fails), "FAIL" if fails else "PASS"))
sys.exit(1 if fails else 0)
