"""Holidays and specials in the rig: write a test calendar.json, list what each
channel has planned around its specials, and check the plan.  Inside the rig:

    python3 /mnt/g/CableBox42/script.cablebox42/.claude/tools/specials_rig.py CMD

    case NAME     write calendar.json for a test case (see CASES; A+B for several);
                  'none' removes it
    aired         forget the undo logs, as if everything planned had aired (a refresh
                  then keeps the bookmarks where the plan left them: "a year later")
    show [HOURS]  blocks from now on (default 30 h), with the special's name, (R),
                  episode labels and the marathon / rerun bookmarks; then the checks:
                    - a special's hours hold only its programmes (or a Station Break)
                    - no programme crosses a special's start or end
                    - a special's blocks move only event: bookmarks
                    - its shows are on no other channel at the same time
                  --none=CHANNEL_ID: that channel has nothing for its special (no holiday
                  episodes): its normal programming is expected there
                  Ends PASS or FAIL.

The test setting specials_today (YYYY-MM-DD, with `kodi21-test-vm.sh setting`) makes
today count as that date; times are shown on that clock.  CB_DATA=DIR reads another
addon_data.  Lineup: lineup-specials.json."""
import glob
import importlib.util
import json
import os
import re
import sys
import time

D = os.environ.get("CB_DATA", "/root/.kodi/userdata/addon_data/script.cablebox42")
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "cb_specials", os.path.join(HERE, "..", "..", "resources", "lib", "specials.py"))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
CAL = os.path.join(D, "calendar.json")
# --none=CHANNEL_ID[,ID]: channels whose special has nothing to air (normal programming expected)
NONE = [x for a in sys.argv if a.startswith("--none=") for x in a[7:].split(",")]

TV = lambda title: [{"type": "tvshow", "value": title}]        # noqa: E731
THANKSGIVING = {"type": "nth", "n": 4, "weekday": 3, "month": 11}
CASES = {
    # Thanksgiving all day on Keystone: Seinfeld in order, continuing next year
    "thanksgiving": [
        {"id": "tg0001", "name": "Turkey Day Marathon", "repeat": "yearly", "when": THANKSGIVING, "blocks": [
            {"channel": "keys0003", "start": "00:00", "end": "00:00", "sources": TV("Seinfeld"), "order": "continue"}]}],
    # New Year's Eve 6 PM - 6 AM on Beacon (off-air 01:00-05:00, The Fugitive pinned at 06:00)
    "nye": [
        {"id": "nye001", "name": "New Year's Eve", "repeat": "yearly", "when": {"type": "date", "month": 12, "day": 31},
         "blocks": [{"channel": "beac0004", "start": "18:00", "end": "06:00", "sources": TV("Friends"), "order": "first"}]}],
    # Christmas Day on three channels: holiday episodes for a broadcast day, a movie at 8 PM, shorts at random
    "christmas": [
        {"id": "xmas01", "name": "Christmas Day", "repeat": "yearly", "when": {"type": "date", "month": 12, "day": 25},
         "blocks": [
             {"channel": "keys0003", "start": "06:00", "end": "06:00",
              "sources": [{"type": "holiday", "season": "christmas"}], "order": "continue"},
             {"channel": "film0006", "start": "20:00", "end": "23:00",
              "sources": [{"type": "movie", "value": ["The Long Field"]}], "order": "first"},
             {"channel": "kids0007", "start": "06:00", "end": "06:00", "sources": TV("Shorties"), "order": "random"}]}],
    # Thanksgiving episodes only: Keystone has some (Westerns, with thanksgiving_genres=Western), Kid Stuff none
    "holiday": [
        {"id": "tgeps1", "name": "Thanksgiving Episodes", "repeat": "yearly", "when": THANKSGIVING, "blocks": [
            {"channel": "keys0003", "start": "00:00", "end": "00:00",
             "sources": [{"type": "holiday", "season": "thanksgiving"}], "order": "continue"},
            {"channel": "kids0007", "start": "00:00", "end": "00:00",
             "sources": [{"type": "holiday", "season": "thanksgiving"}], "order": "continue"}]}],
    # A special in June on a channel that reruns in the summer
    "june": [
        {"id": "june01", "name": "June Special", "repeat": "yearly", "when": {"type": "date", "month": 6, "day": 15},
         "blocks": [{"channel": "keys0003", "start": "00:00", "end": "00:00", "sources": TV("Friends"),
                     "order": "continue"}]}],
    # for "added today" (case tonight YYYY-MM-DD): Beacon until 22:50, an end no episode fits before
    "tonight": [
        {"id": "tonite", "name": "Tonight Only", "repeat": "yearly", "when": {"type": "date", "month": 1, "day": 1},
         "blocks": [{"channel": "beac0004", "start": "00:00", "end": "22:50", "sources": TV("Taxi"),
                     "order": "continue"}]}],
    # 29 February: the list says "skips this year" in a non-leap year
    "leap": [
        {"id": "leap01", "name": "Leap Day", "repeat": "yearly", "when": {"type": "date", "month": 2, "day": 29},
         "blocks": [{"channel": "keys0003", "start": "00:00", "end": "00:00", "sources": TV("Friends"),
                     "order": "random"}]}],
    # this year only, on 1 July 2026
    "once": [
        {"id": "once01", "name": "One Time Only", "repeat": "once", "year": 2026,
         "when": {"type": "date", "month": 7, "day": 1},
         "blocks": [{"channel": "keys0003", "start": "00:00", "end": "00:00", "sources": TV("Friends"),
                     "order": "first"}]}],
}


def shift():
    try:
        xml = open(os.path.join(D, "settings.xml"), encoding="utf-8").read()
    except OSError:
        return 0, ""
    m = re.search(r'<setting id="specials_today"[^>]*>([^<]*)</setting>', xml)
    fake = (m.group(1) if m else "").strip()
    if not fake:
        return 0, ""
    y, mo, d = [int(x) for x in fake.split("-")]
    lt = time.localtime()
    midnight = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    return time.mktime((y, mo, d, 0, 0, 0, 0, 0, -1)) - midnight, fake


def clock(t, off):
    return time.strftime("%a %d %b %H:%M", time.localtime(t + off))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    if cmd == "case":
        name = sys.argv[2]
        if name == "none":
            if os.path.exists(CAL):
                os.remove(CAL)
            print("calendar.json removed")
            return 0
        todo = [sp for n in name.split("+") for sp in CASES[n]]      # case A+B: several at once
        if len(sys.argv) > 3:               # case NAME TODAY: the special's date is 'today' (YYYY-MM-DD)
            y, mo, d = [int(x) for x in sys.argv[3].split("-")]
            for sp in todo:
                sp["when"] = {"type": "date", "month": mo, "day": d}
        with open(CAL, "w", encoding="utf-8") as f:
            json.dump({"specials": todo}, f)
        print("calendar.json: %s" % ", ".join("%s (%d blocks)" % (sp["name"], len(sp["blocks"])) for sp in todo))
        return 0
    if cmd == "aired":
        for f in sorted(glob.glob(os.path.join(D, "schedules", "*.json"))):
            d = json.load(open(f))
            d["undo"] = []
            json.dump(d, open(f, "w"))
        print("undo logs emptied: what is planned counts as aired")
        return 0

    hours = float(sys.argv[2]) if len(sys.argv) > 2 else 30
    off, fake = shift()
    now = time.time()
    chans = dict((c["id"], c) for c in json.load(open(os.path.join(D, "channels.json")))["channels"])
    cal = S.load(CAL)
    print("now %s%s; %d specials" % (clock(now, off), (" (specials_today %s)" % fake) if fake else "", len(cal)))
    plans = {}
    for f in sorted(glob.glob(os.path.join(D, "schedules", "*.json"))):
        cid = os.path.basename(f)[:-5]
        if cid in chans and chans[cid]["type"] not in ("guide", "weather"):
            plans[cid] = json.load(open(f))
    fails = []
    for cid, d in plans.items():
        ch = chans[cid]
        blocks = [b for b in d.get("blocks", []) if b["e"] > now and b["s"] < now + hours * 3600]
        wins = [(st - off, en - off, sp) for st, en, sp, _b in S.between(cal, now + off, now + hours * 3600 + off, cid)]
        print("\n%d %s  (planned to %s)" % (ch["number"], ch["name"], clock(d.get("until", 0), off)))
        for st, en, sp in wins:
            print("   special: %s  %s - %s" % (sp["name"], clock(st, off), clock(en, off)))
        prev = None
        for b in blocks:
            mark = ("  [%s]" % b["sp"]) if b.get("sp") else ""
            line = "%s  %-34s %-9s%s%s" % (clock(b["s"], off), b["t"][:34], b.get("lb", "") or
                                             ("" if b.get("k") == "show" else b.get("k")) or b.get("sub", "")[:24],
                                             " (R)" if b.get("rr") else "", mark)
            key = (b["t"], bool(b.get("sp")), bool(b.get("rr")), b.get("k"))
            if "-v" in sys.argv or key != prev or b.get("sp"):
                print("   " + line)
            prev = key
            for st, en, sp in wins:
                if b["s"] < st - 0.5 < b["e"] - 0.5 or b["s"] < en - 0.5 < b["e"] - 0.5:
                    fails.append("%s: %s at %s crosses the edge of %s" % (ch["name"], b["t"], clock(b["s"], off), sp["name"]))
                inside = b["s"] >= st - 0.5 and b["e"] <= en + 0.5
                if inside and b["s"] > now and not b.get("sp") and b.get("t") != "Station Break" and cid not in NONE:     # what is on air stays
                    fails.append("%s: %s at %s is not part of %s" % (ch["name"], b["t"], clock(b["s"], off), sp["name"]))
                if not inside and b.get("sp") == sp["name"] and not any(
                        b["s"] >= s2 - 0.5 and b["e"] <= e2 + 0.5 for s2, e2, _x in wins):
                    fails.append("%s: %s at %s is marked %s outside its hours" % (ch["name"], b["t"], clock(b["s"], off), sp["name"]))
            if b.get("sp") and cid in NONE:
                fails.append("%s: %s at %s is marked %s, but the channel has nothing for it" % (
                    ch["name"], b["t"], clock(b["s"], off), b["sp"]))
            if b.get("sp"):
                if b.get("rr"):
                    fails.append("%s: %s at %s is a rerun inside a special" % (ch["name"], b["t"], clock(b["s"], off)))
                for u in d.get("undo", []):
                    if abs(u[0] - b["s"]) < 0.01 and not str(u[2]).startswith(("event:", "ev:")):
                        fails.append("%s: the special's block at %s moved %s (%s)" % (ch["name"], clock(b["s"], off), u[2], u[1]))
                for oid, od in plans.items():
                    if oid == cid:
                        continue
                    for ob in od.get("blocks", []):
                        if ob.get("k") == "show" and ob["t"].lower() == b["t"].lower() and ob["s"] < b["e"] and ob["e"] > b["s"]:
                            fails.append("%s airs %s at %s during %s on %s" % (
                                chans[oid]["name"], ob["t"], clock(ob["s"], off), b["sp"], ch["name"]))
        st_ = d.get("state", {})
        marks = dict((k, os.path.basename(v or "-")) for k, v in st_.get("last", {}).items()
                     if k.startswith(("event:", "rule:")) or k.endswith(":rerun"))
        for k in sorted(marks):
            print("   bookmark %s = %s" % (k, marks[k]))
        for k in sorted(k for k in st_ if k.startswith("ev:")):
            print("   %s = %s" % (k, st_[k]))
    series = os.path.join(D, "series.json")
    if os.path.exists(series):
        shows = json.load(open(series)).get("shows", {})
        print("\nshared bookmarks: " + ", ".join("%s=%s" % (k, os.path.basename((v or {}).get("last") or "-"))
                                                 for k, v in sorted(shows.items())))
        for k in shows:
            if k.startswith("event:"):
                fails.append("a marathon bookmark is shared: %s" % k)
    print()
    for f in sorted(set(fails)):
        print("FAIL  " + f)
    print("FAIL" if fails else "PASS")
    return 1 if fails else 0


sys.exit(main())
