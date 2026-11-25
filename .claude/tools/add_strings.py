"""Append every _("...") literal in resources/lib that strings.po lacks, with new ids
after the highest one; then list ids nothing uses any more (settings.xml, skins,
addon.xml, Python by id, or Python by text).

    python .claude/tools/add_strings.py            # add missing, list unused
    python .claude/tools/add_strings.py --drop ID...   # also remove these unused ids"""
import glob
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PO = os.path.join(REPO, "resources/language/resource.language.en_gb/strings.po")


def unescape(m):
    return m.encode("utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8") if "\\" in m else m


def po_escape(t):
    return t.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


po = open(PO, encoding="utf-8").read()
have = {}
for i, t in re.findall(r'msgctxt "#(\d+)"\nmsgid "(.*)"', po):
    have[int(i)] = t
texts = set(have.values())
src = {f: open(f, encoding="utf-8").read() for f in glob.glob(os.path.join(REPO, "resources/lib/*.py"))}
lits = []
for f, s in sorted(src.items()):
    for m in re.findall(r'_\("((?:[^"\\]|\\.)*)"\)', s):
        t = unescape(m)
        if po_escape(t) not in texts and t not in lits:
            lits.append(t)
nxt = max(have) + 1
add = ""
for t in lits:
    add += '\nmsgctxt "#%d"\nmsgid "%s"\nmsgstr ""\n' % (nxt, po_escape(t))
    print("added %d %s" % (nxt, t))
    nxt += 1
if "--drop" in sys.argv:
    for i in sys.argv[sys.argv.index("--drop") + 1:]:
        po2 = re.sub(r'\n(#[^\n]*\n)?msgctxt "#%s"\nmsgid ".*"\nmsgstr ""\n' % i, "\n", po)
        print("dropped %s" % i if po2 != po else "not found %s" % i)
        po = po2
if add or "--drop" in sys.argv:
    open(PO, "w", encoding="utf-8", newline="\n").write(po.rstrip("\n") + "\n" + add)
# unused ids (>= 32000)
sx = open(os.path.join(REPO, "resources/settings.xml"), encoding="utf-8").read()
used = set()
for m in re.findall(r'(?:label|help|lvalues|heading)="([\d|]+)"', sx):
    used.update(int(x) for x in m.split("|"))
others = "".join(open(f, encoding="utf-8").read() for f in
                 glob.glob(os.path.join(REPO, "resources/skins/Default/1080i/*.xml")) + [os.path.join(REPO, "addon.xml")]
                 + list(src) + glob.glob(os.path.join(REPO, "*.py")))
used.update(int(i) for i in re.findall(r'(?:\$LOCALIZE\[|\$ADDON\[script\.cablebox42 |getLocalizedString\()(\d+)', others))
alltext = "".join(src.values())
pyt = set(po_escape(unescape(m)) for m in re.findall(r'_\("((?:[^"\\]|\\.)*)"\)', alltext))
unused = [i for i, t in sorted(have.items()) if i >= 32000 and i not in used and t not in pyt]
print("not used by id or text (may still be used another way, e.g. HOUSE_LINES or ads.json): %d" % len(unused))
for i in unused:
    print("  %d %s" % (i, have[i][:70]))
