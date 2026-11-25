"""Holiday seasons in the rig (python3 inside CableBoxRig):
    seasons_rig.py case NAME     write a test seasons.json (none = remove it)
    seasons_rig.py show [HOURS]  per channel: planned programmes that count for each season
                                 (by title words), from now on the seasons_today clock
Cases: none, early (Halloween run-up from 15 Sep), canada, easter (two weeks of run-up),
easter_hold (the same with Save for its season on), festivus / festivus_hold (23 Dec, 2 days
of run-up), diwali (dates typed for 2026 and 2027 only)."""
import glob
import json
import os
import sys
import time

D = "/root/.kodi/userdata/addon_data/script.cablebox42"
F = os.path.join(D, "seasons.json")
CASES = {
    "early": {"builtin": {"halloween": {"run_up": {"type": "date", "month": 9, "day": 15}}}},
    "canada": {"builtin": {"thanksgiving": {"from": {"type": "nth", "n": 2, "weekday": 0, "month": 10}}}},
    "easter": {"custom": [{"id": "s_easter", "name": "Easter", "on": True,
                           "run_up": {"type": "easter", "offset": -14}, "from": {"type": "easter", "offset": 0},
                           "days": 1, "words": ["easter", "bunny", "egg"],
                           "tags": "", "genres": "", "hold": False}]},
    "festivus": {"builtin": {"christmas": {"words": ["festivus"]}}},
}
CASES["easter_hold"] = json.loads(json.dumps(CASES["easter"]))
CASES["easter_hold"]["custom"][0]["hold"] = True
# Festivus: 23 Dec, 1 day, 2 days of run-up; its material in the rig: genre Western
CASES["festivus"] = {"custom": [{"id": "s_festivus", "name": "Festivus", "on": True,
                                 "run_up": {"type": "before", "days": 2},
                                 "from": {"type": "date", "month": 12, "day": 23}, "days": 1,
                                 "words": ["festivus"], "tags": "", "genres": "Western", "hold": False}]}
CASES["festivus_hold"] = json.loads(json.dumps(CASES["festivus"]))
CASES["festivus_hold"]["custom"][0]["hold"] = True
# hold by title words that match single episodes ("Friends episode 1", "Seinfeld episode 1"...): a
# hold skips held episodes within a series; a series whose every episode is held still airs
CASES["ep1_hold"] = {"custom": [{"id": "s_ep1", "name": "Episode One Day", "on": True, "run_up": None,
                                 "from": {"type": "date", "month": 12, "day": 23}, "days": 1,
                                 "words": ["episode 1"], "tags": "", "genres": "", "hold": True}]}
# a holiday typed per year (no date for 2028)
CASES["diwali"] = {"custom": [{"id": "s_diwali", "name": "Diwali", "on": True, "run_up": {"type": "before", "days": 3},
                               "from": {"type": "years", "dates": {"2026": [11, 8], "2027": [10, 29]}}, "days": 5,
                               "words": ["diwali"], "tags": "", "genres": "Western", "hold": False}]}


def case(name):
    if name == "none":
        if os.path.exists(F):
            os.remove(F)
        print("seasons.json removed")
        return
    json.dump(CASES[name], open(F, "w"))
    print("seasons.json: %s" % name)


def show(hours):
    t0, t1 = time.time(), time.time() + hours * 3600
    for f in sorted(glob.glob(os.path.join(D, "schedules", "*.json"))):
        ents = [e for e in json.load(open(f))["entries"] if t0 <= e["s"] < t1 and e.get("k") == "show"]
        rows = []
        for e in ents:
            rows.append((time.strftime("%a %H:%M", time.localtime(e["s"])), (e.get("t") or "")[:30],
                         (e.get("sub") or "")[:40]))
        print("%s: %d programmes" % (os.path.basename(f)[:-5], len(rows)))
        for r in rows:
            print("   %s  %-30s %s" % r)


if __name__ == "__main__":
    if sys.argv[1] == "case":
        case(sys.argv[2])
    else:
        show(float(sys.argv[2]) if len(sys.argv) > 2 else 24)
