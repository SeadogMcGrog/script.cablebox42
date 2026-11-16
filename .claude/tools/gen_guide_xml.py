"""Writes the guide's list 50 into the TV skin (between the scrolling grid marker
and the end of group 120)."""
import sys

COLOURS = len(sys.argv) > 2 and sys.argv[2] == "colours"
CELLS = ((420, 460, "FFFFFFFF"), (900, 460, "FFDDE4FF"), (1380, 440, "FFC4CCEE"))
CALL_FONTS = ("font37", "font27", "font12", "font10")
CELL_FONTS = ("font27", "font12", "font10")
# stage 2: a cell's own colour by category (Movie / Sports / Kids); default = the row's
CATS = (("movie", "FF6A2A2A"), ("sports", "FF1F5A34"), ("kids", "FF6B4A10"))
I = "                    "


def label(left, top, width, height, font, colour, text, vis, extra=""):
    return (I + '<control type="label">\n'
            + I + '    <left>%d</left><top>%d</top><width>%d</width><height>%d</height>\n' % (left, top, width, height)
            + I + '    <font>%s</font><textcolor>%s</textcolor>%s\n' % (font, colour, extra)
            + I + '    <label>%s</label>\n' % text
            + (I + '    <visible>%s</visible>\n' % vis if vis else "")
            + I + '</control>\n')


def image(left, top, width, height, tex, vis, diffuse=""):
    d = ' colordiffuse="%s"' % diffuse if diffuse else ""
    return (I + '<control type="image">\n'
            + I + '    <left>%d</left><top>%d</top><width>%d</width><height>%d</height>\n' % (left, top, width, height)
            + I + '    <texture%s>%s</texture>\n' % (d, tex)
            + (I + '    <visible>%s</visible>\n' % vis if vis else "")
            + I + '</control>\n')


def layout():
    ch = "String.IsEqual(ListItem.Property(rt),ch)"
    out = image(0, 2, 1840, 84, "$INFO[ListItem.Property(rowbg)]", ch)
    if COLOURS:
        for n, (x, w, _c) in enumerate(CELLS):
            for cat, col in CATS:
                out += image(x - 8, 6, w + 12, 76, "white.png",
                             "String.IsEqual(ListItem.Property(c%dk),%s)" % (n + 1, cat), col)
    out += image(0, 2, 1840, 84, "white.png", "String.IsEqual(ListItem.Property(rt),hdr)", "FF101A52")
    out += image(0, 2, 1840, 84, "white.png", "String.IsEqual(ListItem.Property(rt),ad)", "FF46226E")
    out += label(20, 4, 110, 80, "font37", "FFFFD24A", "$INFO[ListItem.Label]", ch, "<align>center</align>")
    for f in CALL_FONTS:
        vis = "String.IsEqual(ListItem.Property(nfit),%s)" % f
        if f == "font37":
            vis = "%s + [%s | String.IsEmpty(ListItem.Property(nfit))]" % (ch, vis)
        out += label(135, 4, 270, 80, f, "FFFFFFFF", "$INFO[ListItem.Label2]", vis, "<aligny>center</aligny>")
    out += label(135, 4, 270, 80, "font23_narrow", "FFFFFFFF", "$INFO[ListItem.Property(name2)]",
                 "String.IsEqual(ListItem.Property(nfit),two)", "<aligny>center</aligny><wrapmultiline>true</wrapmultiline>")
    for n, (x, w, col) in enumerate(CELLS):
        p = "c%d" % (n + 1)
        for f in CELL_FONTS:
            vis = "String.IsEqual(ListItem.Property(%sf),%s)" % (p, f)
            out += label(x, 4, w, 80, f, col, "$INFO[ListItem.Property(%s)]" % p, vis, "<aligny>center</aligny>")
        out += label(x, 4, w, 80, "font23_narrow", col, "$INFO[ListItem.Property(%s2)]" % p,
                     "String.IsEqual(ListItem.Property(%sf),two)" % p,
                     "<aligny>center</aligny><wrapmultiline>true</wrapmultiline>")
    out += label(40, 4, 1760, 80, "font37", "FFFFD24A", "$INFO[ListItem.Property(ad)]",
                 "String.IsEqual(ListItem.Property(rt),hdr)", "<align>center</align><aligny>center</aligny>")
    out += label(40, 4, 1760, 80, "font32", "FFFFFFFF", "$INFO[ListItem.Property(ad)]",
                 "String.IsEqual(ListItem.Property(rt),ad)", "<align>center</align><aligny>center</aligny>")
    return out


def control():
    lay = layout()
    return ('            <!-- the crawl: a wraplist moved one row a step by tv.crawl_loop; its linear\n'
            '                 scroll lasts longer than the slowest step, so the steps blend into one\n'
            '                 constant motion. 8 rows tall (to the screen\'s bottom edge). -->\n'
            '            <control type="wraplist" id="50">\n'
            '                <left>40</left><top>440</top><width>1840</width><height>704</height>\n'
            '                <orientation>vertical</orientation>\n'
            '                <focusposition>0</focusposition>\n'
            '                <scrolltime tween="linear">3200</scrolltime>\n'
            '                <itemlayout height="88">\n' + lay + '                </itemlayout>\n'
            '                <focusedlayout height="88">\n' + lay + '                </focusedlayout>\n'
            '            </control>\n')


p = sys.argv[1]
s = open(p, encoding="utf-8").read()
a = s.index("            <!-- scrolling grid -->\n")
b = s.index("        <!-- ============ Weather channel ============ -->")
end = s.rindex("        </control>\n", a, b)
s = s[:a] + "            <!-- scrolling grid -->\n" + control() + s[end:]
open(p, "w", encoding="utf-8", newline="\n").write(s)
