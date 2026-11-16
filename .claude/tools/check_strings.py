"""Every _("...") literal in resources/lib has a msgid in strings.po, and the house
ad lines too:  python .claude/tools/check_strings.py"""
import glob
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
po = open(os.path.join(REPO, "resources/language/resource.language.en_gb/strings.po"), encoding="utf-8").read()
ids = set(re.findall(r'msgid "(.*)"', po))
miss = []
for f in sorted(glob.glob(os.path.join(REPO, "resources/lib/*.py"))):
    s = open(f, encoding="utf-8").read()
    lits = re.findall(r'_\("((?:[^"\\]|\\.)*)"\)', s)
    for m in lits:
        t = m.encode("utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8") if "\\" in m else m
        if t not in ids:
            miss.append((os.path.basename(f), t))
sys.path.insert(0, os.path.join(REPO, "resources", "lib"))
src = open(os.path.join(REPO, "resources/lib/promos.py"), encoding="utf-8").read()
block = src[src.index("HOUSE_LINES = {"):src.index("def house_card")]
for t in re.findall(r'"([^"]+)"', block):
    if t not in ("guide", "weather") and t not in ids:
        miss.append(("promos.HOUSE_LINES", t))
# the retro-ad texts (resources/ads/ads.json): tools/retro-ads/check_ads.py checks them in full
sys.path.insert(0, os.path.join(REPO, "tools", "retro-ads"))
import check_ads  # noqa: E402
import json  # noqa: E402
_d = json.load(open(os.path.join(REPO, "resources/ads/ads.json"), encoding="utf-8"))
for _ad in _d["ads"]:
    for _f, _t in check_ads.texts(_ad):
        if _f not in check_ads.PLAIN_FIELDS and _t not in ids:
            miss.append(("ads.json " + _ad["id"], _t))
print("missing:", miss or "none")
# numeric ids: each msgctxt once; every id named in settings.xml, the skins, addon.xml or
# Python (getLocalizedString / $LOCALIZE / $ADDON) is in strings.po
ctx = re.findall(r'^msgctxt "#(\d+)"', po, re.M)
seen, dup = set(), []
for i in ctx:
    if i in seen:
        dup.append(i)
    seen.add(i)
used = {}
sx = open(os.path.join(REPO, "resources/settings.xml"), encoding="utf-8").read()
for m in re.findall(r'(?:label|help|lvalues|heading)="([\d|]+)"', sx):
    for i in m.split("|"):
        used.setdefault(i, "settings.xml")
others = glob.glob(os.path.join(REPO, "resources/skins/Default/1080i/*.xml")) + [os.path.join(REPO, "addon.xml")]
others += glob.glob(os.path.join(REPO, "resources/lib/*.py")) + glob.glob(os.path.join(REPO, "*.py"))
for f in others:
    s = open(f, encoding="utf-8").read()
    for i in re.findall(r'(?:\$LOCALIZE\[|\$ADDON\[script\.cablebox42 |getLocalizedString\()(\d+)', s):
        used.setdefault(i, os.path.basename(f))
nonum = sorted((w, i) for i, w in used.items() if int(i) >= 30000 and i not in seen)
print("duplicate ids:", dup or "none")
print("ids used but not in strings.po:", nonum or "none")
bad = miss or dup or nonum
print("FAIL" if bad else "PASS")
sys.exit(1 if bad else 0)
