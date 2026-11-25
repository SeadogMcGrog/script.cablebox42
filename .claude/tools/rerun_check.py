"""Summer reruns in the rig: what each channel has planned from now on, with (R) marks
and episode labels, plus the series bookmarks.  Inside the rig:

    python3 /mnt/g/CableBox42/script.cablebox42/.claude/tools/rerun_check.py [HOURS] [--json OUT]

Read-only.  Run after planning with Summer reruns off, then with rerun_today set to a
June date (blocks planned after the refresh get "rr"), then a September one; compare."""
import glob
import json
import os
import sys
import time

D = os.environ.get("CB_DATA", "/root/.kodi/userdata/addon_data/script.cablebox42")
hours = float(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else 12
out_json = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
now = time.time()
chans = dict((c["id"], c) for c in json.load(open(os.path.join(D, "channels.json")))["channels"])
report = {"series": json.load(open(os.path.join(D, "series.json"))) if os.path.exists(os.path.join(D, "series.json")) else {},
          "channels": {}}
for f in sorted(glob.glob(os.path.join(D, "schedules", "*.json"))):
    cid = os.path.basename(f)[:-5]
    ch = chans.get(cid)
    if not ch or ch["type"] in ("guide", "weather"):
        continue
    d = json.load(open(f))
    ents = d.get("entries", [])
    rows = []
    for b in d.get("blocks", []):
        if b["e"] <= now or b["s"] > now + hours * 3600 or b.get("k") != "show":
            continue
        ep = next((e for e in ents if b["s"] <= e["s"] < b["e"] and e.get("k") == "show"), {})
        rows.append([time.strftime("%a %H:%M", time.localtime(b["s"])), b["t"], ep.get("lb", ""),
                     "R" if b.get("rr") else "", os.path.basename(ep.get("p", ""))])
    last = (d.get("state") or {}).get("last") or {}
    report["channels"][cid] = {"name": ch["name"], "broadcast": ch.get("broadcast"), "blocks": rows,
                               "last": last}
    print("== %s %s (broadcast %s)" % (ch["number"], ch["name"], ch.get("broadcast")))
    for r in rows:
        print("   %-10s %-40s %-7s %s" % (r[0], r[1][:40], r[2], r[3]))
    for k, v in sorted(last.items()):
        print("   last %-45s %s" % (k[:45], os.path.basename(v or "")))
print("== series.json (main bookmarks)")
for k, v in sorted((report["series"].get("shows") or report["series"]).items() if isinstance(report["series"], dict) else []):
    if isinstance(v, str):
        print("   %-45s %s" % (k[:45], os.path.basename(v)))
if out_json:
    json.dump(report, open(out_json, "w"), indent=1)
