"""Writes resources/settings.xml from the layout below (settings rework Part A) and
adds the new label texts to strings.po.  Dependencies are written by setting id
here; the eq(-n) offsets of the old settings format (rows counted upward in the
category, headings included) are worked out, then read back from the written file
and printed row by row, so a moved row can't silently point at the wrong setting.

    python .claude/tools/gen_settings_xml.py          # write and print
    python .claude/tools/gen_settings_xml.py --check  # print only (reads the file)

Every setting keeps its id, type, values and default (taken from the current
settings.xml); only labels, order, headings and offsets come from here."""
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
XML = os.path.join(REPO, "resources", "settings.xml")
PO = os.path.join(REPO, "resources", "language", "resource.language.en_gb", "strings.po")

# (setting id, new label text or None = keep, enable deps, visible deps)
# deps: list of (setting id, value, negate) joined with '+' (Kodi: and)
H = "lsep"            # a heading: (H, text)


def on(sid):
    return [(sid, "true", False)]


LAYOUT = [
    ("Breaks", [
        (H, "Commercials and bumps"),
        ("commercials_path",),
        ("bumps_path", "Bumps folder"),
        ("breaks_per_slot",),
        ("chapter_breaks",),
        ("chapters_status", None, None, on("chapter_breaks")),
        (H, "House breaks and retro ads"),
        ("house_breaks", "House breaks (the station's own ads and promos)"),
        ("retro_ads", None, [("house_breaks", "2", True)]),
        ("promo_style", "Look of promos and retro ads"),
        # plays under house-break cards and retro ads too (ads.music), so not greyed with Promos
        ("promo_music", "Music in promos and ads"),
        (H, "Promos"),
        ("promos_on",),
        ("promo_every", None, on("promos_on")),
        ("promo_target", None, on("promos_on")),
        ("promo_extras", None, on("promos_on")),
        ("tool_preview_promo", "Preview a promo..."),
    ]),
    ("Channels", [
        (H, "What airs where"),
        ("share_mode",),
        ("shorts_mode",),
        ("skip_short",),
        (H, "Folders"),
        ("stations_folder", "Stations folder (one folder per channel)"),
        ("logo_folder", "Logo folder (images named like the channel)"),
    ]),
    ("On screen", [
        (H, "Banner, logo and rating"),
        ("banner_secs",),
        ("logo_banner",),
        ("logo_bug",),
        ("logo_corner", None, on("logo_bug")),
        ("logo_opacity", None, on("logo_bug")),
        ("rating_box",),
        (H, "Changing channels"),
        ("power_effect",),
        ("static_effect",),
        ("static_sound", None, on("static_effect")),
        ("static_mode", None, on("static_effect") + on("static_sound")),
        (H, "Picture"),
        ("crt_mode",),
        (H, "Captions"),
        ("tool_cckeys", "Remote CC button..."),
    ]),
    ("Guide & Weather", None),          # unchanged, copied as it is
    ("Holidays & events", [
        ("tool_specials", "Plan holidays and specials..."),
        ("tool_seasons", "Edit holiday seasons..."),
        (H, "Automatic holidays"),
        ("seasons_on", "Holiday programming (automatic)"),
        ("season_intensity", None, on("seasons_on")),
        ("season_hold", None, on("seasons_on")),
    ] + [  # the built-ins' own rows: storage for the season editor (seasons_editor.py), not shown
        (sid, label, None, "false") for name in ("halloween", "thanksgiving", "christmas")
        for sid, label in (("%s_on" % name, "%s on" % name.capitalize()),
                           ("%s_commercials" % name, "%s: commercials folder" % name.capitalize()),
                           ("%s_bumps" % name, "%s: bumps folder" % name.capitalize()),
                           ("%s_tags" % name, "%s: tags (comma separated)" % name.capitalize()),
                           ("%s_genres" % name, "%s: genres (comma separated)" % name.capitalize()))
    ] + [
        (H, "Summer"),
        ("summer_reruns", "Summer reruns (June to August)"),
        ("rerun_today",),
        ("specials_today",),
        ("seasons_today",),                 # hidden: a date for testing seasons (the rig)
    ]),
    ("Start-up & library", [
        (H, "Start-up"),
        ("start_channel",),
        ("skip_menu",),
        ("autostart",),
        (H, "Sleep"),
        ("sleep_cec",),
        (H, "Your Kodi library"),
        ("keep_progress", "Keep my watch progress untouched"),
        ("tool_progress",),
    ]),
    ("Tools", [
        (H, "Schedules"),
        ("tool_refresh",),
        ("tool_restart_series",),
        (H, "Check"),
        ("tool_fillers",),
        ("tool_extras",),
        ("tool_chapters",),
        ("tool_skipped",),
        (H, "Reset"),
        ("tool_reset",),
    ]),
    ("Advanced", [
        (H, "Scheduling"),
        ("horizon_hours",),
        ("extras_unrecognised",),
        (H, "Playback and captions"),
        ("av1_mode",),
        ("cc_fullscreen", "Captions: use Kodi's full-screen player"),
        ("cc_nudge", "Captions: rewind 1 second (embedded subtitles)"),
        (H, "Developer"),
        ("dev_tools",),
    ]),
]

# a help line per row: Estuary's add-on settings dialog shows none for the old format
# (rig, 18 Nov: help="id" on tool_specials changed nothing on screen), so none are written
HELP = {}

# a category's comment in the file (as before) and, for the two renamed ones, its new label
COMMENTS = {"Tools": "Tools: maintenance (lineup tools are in the Channel manager)"}


def po_texts():
    po = open(PO, encoding="utf-8").read()
    ids = {}
    for i, t in re.findall(r'msgctxt "#(\d+)"\nmsgid "(.*)"', po):
        ids[int(i)] = t
    return po, ids


def esc(t):
    return t.replace("\\", "\\\\").replace('"', '\\"')


def unesc(t):
    return t.replace('\\"', '"').replace("\\\\", "\\")


def parse(xml):
    """[(category label id, comment, [row tag strings])]"""
    cats = []
    for m in re.finditer(r'(?:<!-- (.*?) -->\s*)?<category label="(\d+)">(.*?)</category>', xml, re.S):
        rows = re.findall(r'<setting [^>]*/>', m.group(3))
        cats.append((int(m.group(2)), m.group(1), rows))
    return cats


def attr(tag, name):
    m = re.search(r' %s="([^"]*)"' % name, tag)
    return m.group(1) if m else None


def set_attr(tag, name, value):
    if value is None:
        return re.sub(r' %s="[^"]*"' % name, "", tag)
    if attr(tag, name) is not None:
        return re.sub(r' %s="[^"]*"' % name, ' %s="%s"' % (name, value), tag)
    return tag.replace("/>", ' %s="%s"/>' % (name, value))


def write():
    xml = open(XML, encoding="utf-8").read()
    po, texts = po_texts()
    by_text = {}
    for i, t in sorted(texts.items()):
        by_text[unesc(t)] = i                 # the last id with a text wins, as in kodiutil._load_ids
    nxt = [max(texts) + 1]
    new = []

    def sid(text):
        if text in by_text:
            return by_text[text]
        i = nxt[0]
        nxt[0] += 1
        by_text[text] = i
        new.append((i, text))
        return i

    old = parse(xml)
    rows_by_id = {}
    cat_by_name = {}
    for lab, com, rows in old:
        cat_by_name[unesc(texts[lab])] = (lab, com, rows)
        for r in rows:
            if attr(r, "id"):
                rows_by_id[attr(r, "id")] = r
    placed = set()
    out = ['<?xml version="1.0" encoding="utf-8" standalone="yes"?>', "<settings>"]
    for name, spec in LAYOUT:
        if spec is None:
            lab, com, rows = cat_by_name[name]
            out += ["    <!-- %s -->" % (com or name), '    <category label="%d">' % lab]
            out += ["        " + r for r in rows]
            out.append("    </category>")
            placed.update(attr(r, "id") for r in rows if attr(r, "id"))
            continue
        lab = cat_by_name[name][0] if name in cat_by_name else sid(name)     # a kept name keeps its id
        out += ["    <!-- %s -->" % COMMENTS.get(name, name), '    <category label="%d">' % lab]
        ids = [r[1] if r[0] == H else r[0] for r in spec]
        for n, row in enumerate(spec):
            if row[0] == H:
                out.append('        <setting label="%d" type="lsep"/>' % sid(row[1]))
                continue
            tag = rows_by_id[row[0]]
            placed.add(row[0])
            if len(row) > 1 and row[1]:
                tag = set_attr(tag, "label", str(sid(row[1])))
            tag = set_attr(tag, "help", str(sid(HELP[row[0]])) if row[0] in HELP else None)
            for key, deps in (("enable", row[2] if len(row) > 2 else None),
                              ("visible", row[3] if len(row) > 3 else None)):
                if deps == "false":
                    tag = set_attr(tag, key, "false")
                    continue
                if deps is None:
                    if key == "enable" and attr(tag, "enable") not in (None, "false"):
                        tag = set_attr(tag, "enable", None)      # an old offset never survives a move
                    continue
                parts = []
                for dep, val, neg in deps:
                    off = ids.index(dep) - n
                    assert off < 0, (row[0], dep)
                    parts.append("%seq(%d,%s)" % ("!" if neg else "", off, val))
                tag = set_attr(tag, key, "+".join(parts))
            out.append("        " + tag)
        out.append("    </category>")
    out.append("</settings>")
    missing = set(rows_by_id) - placed
    assert not missing, "settings left out: %s" % sorted(missing)
    open(XML, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    if new:
        add = "".join('\nmsgctxt "#%d"\nmsgid "%s"\nmsgstr ""\n' % (i, esc(t)) for i, t in new)
        open(PO, "w", encoding="utf-8", newline="\n").write(po.rstrip("\n") + "\n" + add)
    print("new strings: %s" % (", ".join("%d %s" % n for n in new) or "none"))


def check():
    """Read settings.xml back: every row with its label and what each offset points at."""
    _po, texts = po_texts()
    bad = 0
    for lab, com, rows in parse(open(XML, encoding="utf-8").read()):
        print("\n[%s]" % unesc(texts[lab]))
        for n, r in enumerate(rows):
            rid = attr(r, "id")
            label = unesc(texts.get(int(attr(r, "label")), "?"))
            if attr(r, "type") == "lsep":
                print("   -- %s" % label)
                continue
            deps = []
            for key in ("enable", "visible"):
                v = attr(r, key)
                if not v or v == "false":
                    if v:
                        deps.append("%s=false" % key)
                    continue
                for neg, off, val in re.findall(r'(!?)eq\((-\d+),([^)]+)\)', v):
                    j = n + int(off)
                    tgt = attr(rows[j], "id") if j >= 0 else None
                    if not tgt:
                        bad += 1
                        tgt = "!! NOT A SETTING"
                    deps.append("%s %s%s=%s" % (key, "not " if neg else "", tgt, val))
            print("   %-24s %-52s %s" % (rid, label[:52], "; ".join(deps)))
    print("\nFAIL: %d offsets point at no setting" % bad if bad else "\nPASS: every offset points at a setting")
    return bad


if __name__ == "__main__":
    if "--check" not in sys.argv:
        write()
    sys.exit(1 if check() else 0)
