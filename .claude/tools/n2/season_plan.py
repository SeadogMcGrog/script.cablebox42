"""What the N2's plan airs for the holiday seasons (seasons-n2-test.md step 6).

    python .claude/tools/n2/season_plan.py NAME

Copies the add-on's schedules (read only) to G:\\CableBox42\\n2\\logs\\all9\\plan-NAME\\ and prints,
per channel, the programmes of the next 24 h whose title, episode title or file name has a
Christmas word (seasons.py's list), and the season picks the scheduler recorded (`srecent`)."""
import glob
import io
import json
import os
import re
import sys
import tarfile
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
import n2  # noqa: E402

WORDS = ["christmas", "xmas", "x-mas", "santa", "santa claus", "noel", "jingle", "sleigh", "reindeer",
         "rudolph", "frosty", "grinch", "scrooge", "christmas carol", "nutcracker", "mistletoe",
         "yule", "yuletide", "nativity", "north pole", "snowman", "elves", "stocking",
         "miracle on 34th street", "wonderful life", "home alone", "holiday inn", "white christmas",
         "deck the halls", "silent night", "winter wonderland", "kringle", "feliz navidad"]
RX = re.compile(r"(?<![a-z])(" + "|".join(re.escape(w) for w in sorted(WORDS, key=len, reverse=True)) + r")(?![a-z])",
                re.I)

name = sys.argv[1]
out = os.path.join(r"G:\CableBox42\n2\logs\all9", "plan-" + name)
os.makedirs(out, exist_ok=True)
data = n2.ssh("cd /storage/.kodi/userdata/addon_data/script.cablebox42 && tar czf - schedules channels.json settings.xml")
tarfile.open(fileobj=io.BytesIO(data)).extractall(out)
chans = json.load(open(os.path.join(out, "channels.json"), encoding="utf-8"))
chans = chans["channels"] if isinstance(chans, dict) else chans
num = {c["id"]: (c["number"], c["name"]) for c in chans}
st = re.search(r'id="seasons_today"[^>]*>([^<]*)<', open(os.path.join(out, "settings.xml"), encoding="utf-8").read())
print("plan %s (seasons_today=%r), taken %s" % (name, st.group(1) if st else "", time.strftime("%H:%M:%S")))
t0 = time.time()
tot_x = tot = 0
for f in sorted(glob.glob(os.path.join(out, "schedules", "*.json"))):
    d = json.load(open(f, encoding="utf-8"))
    cid = os.path.basename(f)[:-5]
    shows = []
    seen = set()
    for e in d.get("entries", []):
        if e.get("k") == "show" and t0 <= e["s"] < t0 + 86400:
            key = (e.get("p"), e.get("o"))
            if (e.get("p"), round(e["s"])) in seen:
                continue
            seen.add((e.get("p"), round(e["s"])))
            shows.append(e)
    xmas = [e for e in shows if RX.search(" ".join((e.get("t") or "", e.get("sub") or "",
                                                     os.path.basename(e.get("p") or ""))))]
    rec = d.get("state", {}).get("srecent", {})
    tot += len(shows)
    tot_x += len(xmas)
    if xmas or rec:
        n, nm = num.get(cid, ("?", cid))
        titles = sorted(set("%s%s" % (e.get("t") or "", (": " + e["sub"]) if e.get("sub") else "") for e in xmas))
        print("  %3s %-24s %3d of %3d programmes with a Christmas word; season picks recorded: %d  %s"
              % (n, nm[:24], len(xmas), len(shows), len(rec), "; ".join(titles)[:150]))
print("all channels: %d of %d programmes in the next 24 h have a Christmas word" % (tot_x, tot))
