"""state.json under concurrent writers: no key may ever be lost (fix for the 18 Nov CC wipe).

    python .claude/tools/state_race.py [ROUNDS] [--old]

Runs the add-on's real kodiutil (xbmc stubbed) in a temp profile: 2 processes x 2 threads
(as the TV, its captions thread, the service and a menu do in Kodi) each change their own
keys ROUNDS times (default 3000), with the TV-start pattern of read-then-update mixed in.
Seeded keys (cc_on, last_channel, last_channel_id, gui_sounds_orig) are checked on every
read and at the end, and each writer's counter must equal its rounds (no lost update).
--old runs the same load_json/save_json read-modify-write the add-on used before ~all10,
to show the test catches the bug.  Linux (flock) and Windows (msvcrt) both work."""
import os as _os
import sys as _sys
_sys.path[:] = [p for p in _sys.path if _os.path.abspath(p or ".") != _os.path.dirname(_os.path.abspath(__file__))]  # tools/queue.py hides the stdlib
import multiprocessing  # noqa: E402
import os
import sys
import tempfile
import threading
import time
import types

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SEED = {"cc_on": False, "cc_lang": "eng", "last_channel": 7, "last_channel_id": "c7",
        "gui_sounds_orig": 1, "tip_menu": 1}


def stub_kodi(profile):
    xbmc = types.ModuleType("xbmc")
    xbmc.LOGDEBUG, xbmc.LOGINFO, xbmc.LOGWARNING, xbmc.LOGERROR = 0, 1, 2, 3
    xbmc.log = lambda msg, level=0: (sys.stderr.write(msg + "\n") if level >= 3 else None)
    xbmcaddon = types.ModuleType("xbmcaddon")

    class Addon(object):
        def __init__(self, *a):
            pass

        def getAddonInfo(self, k):
            return {"name": "CableBox 42", "path": REPO, "profile": profile}.get(k, "")

        def getSetting(self, k):
            return ""
    xbmcaddon.Addon = Addon
    xbmcvfs = types.ModuleType("xbmcvfs")
    xbmcvfs.translatePath = lambda p: p
    for m in (xbmc, xbmcaddon, xbmcvfs):
        sys.modules[m.__name__] = m
    sys.path.insert(0, os.path.join(REPO, "resources", "lib"))
    import kodiutil
    return kodiutil


def worker(profile, wid, rounds, old, out):
    K = stub_kodi(profile)
    errors = []

    def check(st, where):
        if old:
            st = st or {}
        for k in SEED:
            if k not in st:
                errors.append("%s: %s lost (%s)" % (where, k, sorted(st)))
                return

    def thread(tid):
        key = "n_%d_%d" % (wid, tid)
        for i in range(1, rounds + 1):
            if old:
                st = K.load_json(K.STATE_FILE, {})
                check(st, key)
                st[key] = i
                if i % 7 == 0:
                    st["cc_on"] = st.get("cc_on", False)       # the captions _remember pattern
                K.save_json(K.STATE_FILE, st)
            else:
                check(K.load_state(), key)
                if i % 5 == 0:                                 # the fn pattern (setup_skipped, notes)
                    def bump(st, key=key, i=i):
                        st[key] = i
                        st.setdefault("setup_skipped", [])
                    K.update_state(fn=bump)
                else:
                    K.update_state({key: i, "specials_view": "calendar" if i % 2 else "list"})
                if i % 7 == 0:
                    K.update_state({"cc_on": False, "cc_lang": "eng"})
            if len(errors) > 20:
                break
    ts = [threading.Thread(target=thread, args=(t,)) for t in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    out.put((wid, errors))


def main():
    rounds = int(next((a for a in sys.argv[1:] if a.isdigit()), 3000))
    old = "--old" in sys.argv
    profile = tempfile.mkdtemp(prefix="cb42race")
    K = stub_kodi(profile)
    K.save_json(K.STATE_FILE, dict(SEED))
    q = multiprocessing.Queue()
    t0 = time.time()
    ps = [multiprocessing.Process(target=worker, args=(profile, w, rounds, old, q)) for w in range(2)]
    for p in ps:
        p.start()
    res = [q.get() for _ in ps]
    for p in ps:
        p.join()
    try:
        final = K._read_state(K.STATE_FILE)
    except Exception as exc:
        final = {"<unreadable>": str(exc)}
    errs = [e for _w, es in res for e in es]
    lost_end = [k for k in SEED if final.get(k) != SEED[k] and not (k == "cc_on" and final.get(k) is False)]
    counters = {"n_%d_%d" % (w, t): final.get("n_%d_%d" % (w, t)) for w in range(2) for t in range(2)}
    short = {k: v for k, v in counters.items() if v != rounds}
    leftovers = [f for f in os.listdir(profile) if f.endswith(".tmp")]
    print("%s code, 2 processes x 2 threads x %d rounds in %.1f s" % ("old" if old else "new", rounds, time.time() - t0))
    print("  reads that missed a seeded key: %d%s" % (len(errs), (" e.g. " + errs[0]) if errs else ""))
    print("  seeded keys wrong at the end: %s" % (lost_end or "none"))
    print("  writers' counters (want %d each): %s" % (rounds, counters))
    print("  temp files left: %d" % len(leftovers))
    ok = not errs and not lost_end and not short and not leftovers
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
