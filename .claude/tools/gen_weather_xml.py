"""Inserts the weather channel's Latest Observations and Regional Map pages into the
TV skin, before the almanac page's group."""
import sys

V = "String.IsEqual(Window.Property(mode),weather) + String.IsEqual(Window.Property(wx_page),%s)"


def label(l, t, w, h, font, col, text, extra="", vis=""):
    return ('''                <control type="label">
                    <left>%d</left><top>%d</top><width>%d</width><height>%d</height>
                    <font>%s</font><textcolor>%s</textcolor><shadowcolor>FF000000</shadowcolor>%s
                    <label>%s</label>%s
                </control>
''' % (l, t, w, h, font, col, extra, text, ("\n                    <visible>%s</visible>" % vis) if vis else ""))


def image(l, t, w, h, tex, extra="", vis="", cid=None):
    return ('''                <control type="image"%s>
                    <left>%d</left><top>%d</top><width>%d</width><height>%d</height>%s
                    <texture%s</texture>%s
                </control>
''' % ((' id="%d"' % cid) if cid else "", l, t, w, h, extra, tex, ("\n                    <visible>%s</visible>" % vis) if vis else ""))


obs = '''        <!-- Latest Observations: nearby cities (weather.nearby), one request for all (from_open_meteo_many) -->
        <control type="group">
            <visible>%s</visible>
            <animation effect="fade" start="0" end="100" time="400">Visible</animation>
''' % (V % "observations")
obs += label(150, 190, 900, 60, "font30_title", "FFFFD24A", "$ADDON[script.cablebox42 34057]", "<align>left</align>").replace("                ", "            ", 1)
for i in range(8):
    y = 280 + i * 76
    vis = "!String.IsEmpty(Window.Property(wx_o%d_name))" % i
    obs += "            <control type=\"group\">\n                <top>%d</top>\n                <visible>%s</visible>\n" % (y, vis)
    obs += label(150, 0, 720, 70, "font37", "FFFFFFFF", "$INFO[Window.Property(wx_o%d_name)]" % i, "<aligny>center</aligny>")
    obs += image(890, 3, 64, 64, ">$INFO[Window.Property(wx_o%d_icon)]" % i, "\n                    <aspectratio>keep</aspectratio>")
    obs += label(980, 0, 170, 70, "font37", "FFFFD24A", "$INFO[Window.Property(wx_o%d_temp)]" % i, "<align>right</align><aligny>center</aligny>")
    obs += label(1200, 0, 620, 70, "font37", "FFE0E8FF", "$INFO[Window.Property(wx_o%d_cond)]" % i, "<aligny>center</aligny>")
    obs += "            </control>\n"
obs += "        </control>\n"

VX, VY, VW, VH = 116, 256, 1688, 672
mp = '''        <!-- Regional Map: Natural Earth tiles drawn by G:\\CableBox42\\rig\\wx_prerender.py (media/wxmap),
             placed by weather.map_layout into slots 4101-4112 inside a grouplist, which clips them
             to the map's area; cities 4120-4128 (0 = your own) are moved to their places -->
        <control type="group">
            <visible>%s</visible>
            <animation effect="fade" start="0" end="100" time="400">Visible</animation>
''' % (V % "map")
mp += label(150, 190, 900, 60, "font30_title", "FFFFD24A", "$ADDON[script.cablebox42 34058]", "<align>left</align>").replace("                ", "            ", 1)
mp += image(VX - 4, VY - 4, VW + 8, VH + 8, ' colordiffuse="FFD6C496">white.png')
mp += image(VX, VY, VW, VH, ' colordiffuse="FF183480">white.png')
mp += '''            <control type="grouplist">
                <left>%d</left><top>%d</top><width>%d</width><height>%d</height>
                <orientation>vertical</orientation><itemgap>0</itemgap>
                <control type="group">
                    <width>%d</width><height>%d</height>
''' % (VX, VY, VW, VH, VW, VH)
for i in range(12):
    mp += image(0, 0, 10, 10, ">", "", "", 4101 + i).replace("\n                ", "\n                    ").replace("                <control", "                    <control", 1)
mp += "                </control>\n            </control>\n"
for i in range(9):
    cid = 4120 + i
    p = "wx_m%d" % i
    mp += '''            <control type="group" id="%d">
                <left>0</left><top>0</top>
                <visible>String.IsEqual(Window.Property(%s),1)</visible>
''' % (cid, p)
    mp += image(-11, -11, 22, 22, ' colordiffuse="FFFFFFFF">white.png', "", "!String.IsEqual(Window.Property(%s_home),1)" % p)
    mp += image(-9, -9, 18, 18, ' colordiffuse="FFD02020">white.png', "", "!String.IsEqual(Window.Property(%s_home),1)" % p)
    mp += image(-15, -15, 30, 30, ' colordiffuse="FFFFD24A">white.png', "", "String.IsEqual(Window.Property(%s_home),1)" % p)
    mp += image(-80, -86, 72, 72, ">$INFO[Window.Property(%s_icon)]" % p, "\n                    <aspectratio>keep</aspectratio>")
    mp += label(0, -86, 140, 72, "font45", "FFFFD24A", "$INFO[Window.Property(%s_temp)]" % p, "<aligny>center</aligny>")
    mp += label(-160, 14, 320, 44, "font27", "FFFFFFFF", "$INFO[Window.Property(%s_name)]" % p, "<align>center</align>")
    mp += "            </control>\n"
mp += "        </control>\n"

p = sys.argv[1]
s = open(p, encoding="utf-8").read()
mark = "        <control type=\"group\">\n            <visible>String.IsEqual(Window.Property(mode),weather) + String.IsEqual(Window.Property(wx_page),almanac)</visible>"
assert s.count(mark) == 1
s = s.replace(mark, obs + mp + mark)
open(p, "w", encoding="utf-8", newline="").write(s)
