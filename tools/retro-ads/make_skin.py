#!/usr/bin/env python3
"""Write the retro-ad card group into the TV window (script-cablebox42-tv.xml),
between <!-- RETRO ADS START --> and <!-- RETRO ADS END -->.

    python3 tools/retro-ads/make_skin.py

The letter slots are image controls declared here and filled from Python
(resources/lib/ads.py Slots: ids and counts must match SLOT_FILL / SLOT_LINE).
The group shows retro ads (mode retro) and the station ID card (mode station,
its layers from make_station_layers.py in media/station).
"""
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
XML = os.path.join(REPO, "resources", "skins", "Default", "1080i", "script-cablebox42-tv.xml")
sys.path.insert(0, os.path.join(REPO, "resources", "lib"))
SLOT_FILL = (3000, 400)
SLOT_LINE = (3400, 140)
SLOT_CLOCK = (3600, 16)

NINETIES = 'String.IsEqual(Window.Property(ad_style),90s)'
MODERN = '!String.IsEqual(Window.Property(ad_style),90s)'
RETRO = 'String.IsEqual(Window.Property(mode),retro)'
STATION = 'String.IsEqual(Window.Property(mode),station)'
UPNEXT = 'String.IsEqual(Window.Property(mode),upnext)'
SQUEEZE = '[String.IsEqual(Window.Property(mode),video) + String.IsEqual(Window.Property(squeeze),1)]'
FIT = 'Window.Property(sid_label_fit)'


def fit_labels(left, top, width, height, color, outline):
    """The station name in the skin's font (a script the letters can't spell),
    one label per font of promos.LADDER_60, then two lines (promos.fit_font)."""
    out = ""
    for f in ("font60", "font45", "font37", "font32", "font27"):
        cond = "String.IsEqual(%s,%s)" % (FIT, f)
        out += ('                    <control type="label"><left>%d</left><top>%d</top><width>%d</width><height>%d</height>'
                '<align>center</align><aligny>center</aligny><font>%s</font><textcolor>%s</textcolor>%s'
                '<label>$INFO[Window.Property(sid_label)]</label><visible>%s</visible></control>\n'
                % (left, top, width, height, f, color, outline, cond))
    out += ('                    <control type="label"><left>%d</left><top>%d</top><width>%d</width><height>%d</height>'
            '<align>center</align><aligny>center</aligny><font>font27_narrow</font><textcolor>%s</textcolor>%s'
            '<wrapmultiline>true</wrapmultiline><label>$INFO[Window.Property(sid_label2)]</label>'
            '<visible>String.EndsWith(%s,2)</visible></control>\n' % (left, top, width, height, color, outline, FIT))
    return out


def station():
    """The station ID card (LAYOUTS.md section 9): bg_9 in layers so it can loop
    gently while it fills the end of a break - the rays turn (15 degrees, the
    pattern's repeat, then again) and a glint crosses the gold band, in both styles."""
    return '''            <control type="group">
                <visible>%(st)s</visible>
                <control type="image">
                    <left>0</left><top>0</top><width>1920</width><height>1080</height>
                    <texture>station/sid_base.jpg</texture>
                </control>
                <control type="image">
                    <left>-200</left><top>-720</top><width>2320</width><height>2320</height>
                    <texture>station/sid_rays.png</texture>
                    <animation effect="rotate" start="0" end="-15" center="960,440" time="40000" loop="true" condition="%(st)s">Conditional</animation>
                </control>
                <control type="image">
                    <left>0</left><top>0</top><width>1920</width><height>1080</height>
                    <texture>station/sid_top.png</texture>
                </control>
                <control type="image">
                    <left>240</left><top>712</top><width>260</width><height>186</height>
                    <texture>station/sid_glint.png</texture>
                    <animation effect="slide" start="0,0" end="1180,0" time="8000" loop="true" condition="%(st)s">Conditional</animation>
                    <animation effect="fade" start="0" end="100" time="4000" tween="sine" easing="inout" pulse="true" condition="%(st)s">Conditional</animation>
                </control>
                <!-- the channel's logo, fitted inside the box and centred -->
                <control type="image">
                    <left>510</left><top>250</top><width>900</width><height>380</height>
                    <aspectratio align="center" aligny="center">keep</aspectratio>
                    <texture>$INFO[Window.Property(ad_logo)]</texture>
                    <visible>!String.IsEmpty(Window.Property(ad_logo))</visible>
                    <animation effect="zoom" start="140" end="100" center="960,440" time="450" delay="150" tween="back" easing="out" condition="%(n)s">Visible</animation>
                    <animation effect="fade" start="0" end="100" time="200" delay="150" condition="%(n)s">Visible</animation>
                    <animation effect="fade" start="0" end="100" time="700" delay="100" condition="%(m)s">Visible</animation>
                </control>
                <!-- a name the letters can't spell: the skin's font, never cut off -->
                <control type="group">
                    <visible>!String.IsEmpty(Window.Property(sid_label)) + String.IsEmpty(Window.Property(sid_label_box))</visible>
%(band)s                </control>
                <control type="group">
                    <visible>!String.IsEmpty(Window.Property(sid_label)) + !String.IsEmpty(Window.Property(sid_label_box))</visible>
%(box)s                </control>
            </control>
''' % {"st": STATION, "n": NINETIES, "m": MODERN,
       "band": fit_labels(260, 712, 1400, 186, "FF14257A", ""),
       "box": fit_labels(510, 250, 900, 380, "FFFFFFFF", "<shadowcolor>FF070D33</shadowcolor>")}


def slots(first, count):
    return "".join('                <control type="image" id="%d"><left>0</left><top>0</top><width>1</width>'
                   '<height>1</height><texture></texture></control>\n' % (first + i) for i in range(count))


def letters_anim():
    # early-90s: the words slam in from the left; Modern: a soft fade
    return ('                <animation effect="slide" start="-120,0" end="0,0" time="320" delay="120" tween="back" '
            'easing="out" condition="%s">Visible</animation>\n'
            '                <animation effect="fade" start="0" end="100" time="160" delay="120" '
            'condition="%s">Visible</animation>\n'
            '                <animation effect="fade" start="0" end="100" time="600" delay="150" '
            'condition="%s">Visible</animation>\n' % (NINETIES, NINETIES, MODERN))


def fit_variants(prop, left, top, width, height, color, extra="", align="left"):
    """A name in the skin's font that is never cut off (promos.fit_font): one label
    per font, the property PROP_fit says which; two lines from PROP2 (split by
    promos.two_lines) when even the smallest is too wide."""
    fit = "Window.Property(%s_fit)" % prop
    out = ""
    for f in ("font60", "font45", "font37", "font32", "font27"):
        out += ('                <control type="label"><left>%d</left><top>%d</top><width>%d</width><height>%d</height>'
                '<align>%s</align><aligny>center</aligny><font>%s</font><textcolor>%s</textcolor>%s'
                '<label>$INFO[Window.Property(%s)]</label><visible>String.IsEqual(%s,%s)</visible></control>\n'
                % (left, top, width, height, align, f, color, extra, prop, fit, f))
    out += ('                <control type="label"><left>%d</left><top>%d</top><width>%d</width><height>%d</height>'
            '<align>%s</align><aligny>center</aligny><font>font27_narrow</font><textcolor>%s</textcolor>%s'
            '<wrapmultiline>true</wrapmultiline><label>$INFO[Window.Property(%s2)]</label>'
            '<visible>String.EndsWith(%s,2)</visible></control>\n' % (left, top, width, height, align, color, extra, prop, fit))
    return out


def upnext():
    """The Up next card (LAYOUTS.md section 10): bg_10 in layers so it can loop gently
    while it waits (up to ~90 s between films) - the stripes drift and a glint crosses
    the UP NEXT tab, in both styles.  The picture fills its rounded slot (episode still
    or fanart), or a poster sits on a dimmed copy of itself, or the channel logo on
    dark; the show's clear logo replaces its lettered title."""
    return '''            <control type="group">
                <visible>%(un)s</visible>
                <control type="image">
                    <left>0</left><top>0</top><width>1920</width><height>1080</height>
                    <texture>upnext/un_base.jpg</texture>
                </control>
                <control type="image">
                    <left>0</left><top>0</top><width>1920</width><height>1080</height>
                    <texture>upnext/un_stripes.png</texture>
                    <animation effect="slide" start="-40,0" end="40,0" time="9000" tween="sine" easing="inout" pulse="true" condition="%(un)s">Conditional</animation>
                </control>
                <control type="image">
                    <left>0</left><top>0</top><width>1920</width><height>1080</height>
                    <texture>upnext/un_top.png</texture>
                </control>
                <control type="image">
                    <left>130</left><top>90</top><width>200</width><height>110</height>
                    <texture>upnext/un_glint.png</texture>
                    <animation effect="slide" start="0,0" end="420,0" time="7000" loop="true" condition="%(un)s">Conditional</animation>
                    <animation effect="fade" start="0" end="100" time="3500" tween="sine" easing="inout" pulse="true" condition="%(un)s">Conditional</animation>
                </control>
                <!-- the picture: an episode still or fanart, filling the slot -->
                <control type="image">
                    <left>120</left><top>250</top><width>960</width><height>540</height>
                    <aspectratio>scale</aspectratio>
                    <texture diffuse="upnext/un_mask.png" background="true">$INFO[Window.Property(un_pic)]</texture>
                    <visible>!String.IsEmpty(Window.Property(un_pic))</visible>
                    <animation effect="fade" start="0" end="100" time="400">Visible</animation>
                </control>
                <!-- only a poster: on a dimmed copy of itself (Kodi can't blur) -->
                <control type="group">
                    <visible>!String.IsEmpty(Window.Property(un_poster))</visible>
                    <animation effect="fade" start="0" end="100" time="400">Visible</animation>
                    <control type="image">
                        <left>120</left><top>250</top><width>960</width><height>540</height>
                        <aspectratio>scale</aspectratio>
                        <texture diffuse="upnext/un_mask.png" colordiffuse="FF4A4A5A" background="true">$INFO[Window.Property(un_poster)]</texture>
                    </control>
                    <control type="image">
                        <left>120</left><top>270</top><width>960</width><height>500</height>
                        <aspectratio>keep</aspectratio>
                        <texture background="true">$INFO[Window.Property(un_poster)]</texture>
                    </control>
                </control>
                <!-- no picture: the channel's logo on dark -->
                <control type="image">
                    <left>220</left><top>330</top><width>760</width><height>380</height>
                    <aspectratio>keep</aspectratio>
                    <texture>$INFO[Window.Property(un_chlogo)]</texture>
                    <visible>!String.IsEmpty(Window.Property(un_chlogo))</visible>
                    <animation effect="fade" start="0" end="100" time="400">Visible</animation>
                </control>
                <!-- the show's clear logo (else its title is lettered) -->
                <control type="image">
                    <left>1150</left><top>250</top><width>650</width><height>200</height>
                    <aspectratio align="left" aligny="center">keep</aspectratio>
                    <texture>$INFO[Window.Property(un_logo)]</texture>
                    <visible>!String.IsEmpty(Window.Property(un_logo))</visible>
                    <animation effect="zoom" start="130" end="100" center="1150,350" time="400" delay="150" tween="back" easing="out" condition="%(n)s">Visible</animation>
                    <animation effect="fade" start="0" end="100" time="600" delay="100" condition="%(m)s">Visible</animation>
                </control>
                <!-- texts the letters can't spell (another script): the skin's font, names never cut off -->
                <control type="group">
                    <visible>!String.IsEmpty(Window.Property(un_title))</visible>
%(title)s                </control>
                <control type="group">
                    <visible>!String.IsEmpty(Window.Property(un_chan))</visible>
%(chan)s                </control>
                <control type="label">
                    <left>1150</left><top>585</top><width>650</width><height>60</height>
                    <aligny>center</aligny><font>font37</font><textcolor>FFFFFFFF</textcolor>
                    <label>$INFO[Window.Property(un_ep)]</label>
                    <visible>!String.IsEmpty(Window.Property(un_ep))</visible>
                </control>
                <control type="label">
                    <left>1150</left><top>665</top><width>650</width><height>150</height>
                    <font>font27</font><textcolor>FFC9D3E0</textcolor><wrapmultiline>true</wrapmultiline>
                    <label>$INFO[Window.Property(un_plot)]</label>
                    <visible>!String.IsEmpty(Window.Property(un_plot))</visible>
                </control>
            </control>
''' % {"un": UPNEXT, "n": NINETIES, "m": MODERN,
       "title": fit_variants("un_title", 1150, 260, 650, 200, "FFFFFFFF"),
       "chan": fit_variants("un_chan", 590, 890, 720, 110, "FFFFFFFF", align="center")}


def squeeze():
    """Squeezed credits (LAYOUTS.md section 11): the Up next panel that slides in from
    the right while the episode's credits play in the shrunken video window (the
    background is drawn behind the video window, outside this group)."""
    return '''            <control type="group">
                <visible>%(sq)s</visible>
                <animation effect="slide" start="700,0" end="0,0" time="500" tween="cubic" easing="out">Visible</animation>
                <control type="image">
                    <left>0</left><top>0</top><width>1920</width><height>1080</height>
                    <texture>squeeze/sq_panel.png</texture>
                </control>
                <control type="image">
                    <left>1260</left><top>290</top><width>580</width><height>70</height>
                    <aspectratio align="left" aligny="center">keep</aspectratio>
                    <texture>$INFO[Window.Property(sq_logo)]</texture>
                    <visible>!String.IsEmpty(Window.Property(sq_logo))</visible>
                </control>
                <control type="group">
                    <visible>!String.IsEmpty(Window.Property(sq_title))</visible>
%(title)s                </control>
            </control>
            <control type="group">
                <visible>%(sq)s + !String.IsEmpty(Window.Property(sq_strip))</visible>
%(strip)s            </control>
''' % {"sq": SQUEEZE, "title": fit_variants("sq_title", 1260, 280, 580, 100, "FFFFFFFF"),
       "strip": fit_variants("sq_strip", 60, 860, 1800, 110, "FFFFFFFF", align="center")}


def group():
    return '''        <!-- RETRO ADS START (tools/retro-ads/make_skin.py writes this block) -->
        <!-- ============ Retro ads: made-up commercials (resources/lib/ads.py, tv.start_retro) ============
             A blank background, lettered with pictures of letters placed by ads.Slots (Kodi 21 can't load
             an add-on's fonts).  Outlines first, letters over them. -->
        <control type="group" id="150">
            <visible>%(r)s | %(st)s | %(un)s | %(sq)s</visible>
            <control type="image">
                <left>0</left><top>0</top><width>1920</width><height>1080</height>
                <texture>$INFO[Window.Property(ad_bg)]</texture>
                <visible>%(r)s + %(n)s</visible>
            </control>
            <!-- Modern: the background drifts in slowly (a short Hidden animation: a long Visible one keeps drawing) -->
            <control type="image">
                <left>0</left><top>0</top><width>1920</width><height>1080</height>
                <texture>$INFO[Window.Property(ad_bg)]</texture>
                <visible>%(r)s + %(m)s</visible>
                <animation effect="zoom" start="104" end="100" center="960,540" time="9000" tween="sine" easing="out">Visible</animation>
                <animation effect="fade" start="100" end="0" time="60">Hidden</animation>
            </control>
            <!-- Now on videocassette: the movie's poster from the library -->
            <control type="image">
                <left>170</left><top>150</top><width>520</width><height>780</height>
                <aspectratio>scale</aspectratio>
                <texture background="true">$INFO[Window.Property(ad_poster)]</texture>
                <visible>%(r)s + String.IsEqual(Window.Property(ad_fmt),video) + !String.IsEmpty(Window.Property(ad_poster))</visible>
                <animation effect="fade" start="0" end="100" time="300">Visible</animation>
            </control>
            <!-- a title the letters can't spell (another script): the skin's font -->
            <control type="label">
                <left>820</left><top>455</top><width>1000</width><height>90</height>
                <aligny>center</aligny><font>font52_title</font><textcolor>FFFFFFFF</textcolor>
                <shadowcolor>FF000000</shadowcolor>
                <label>$INFO[Window.Property(ad_title)]</label>
                <visible>%(r)s + !String.IsEmpty(Window.Property(ad_title))</visible>
            </control>
            <!-- the station ID card -->
%(station)s            <!-- the Up next card -->
%(upnext)s            <!-- squeezed credits: the Up next panel -->
%(squeeze)s            <control type="group">
%(anim)s%(line)s            </control>
            <control type="group">
%(anim)s%(fill)s            </control>
            <!-- the Up next card's (and the squeeze's) countdown, relettered every second (ads.SLOT_CLOCK) -->
            <control type="group">
                <visible>%(un)s | %(sq)s</visible>
%(clock)s            </control>
        </control>
        <!-- RETRO ADS END -->
''' % {"n": NINETIES, "m": MODERN, "r": RETRO, "st": STATION, "station": station(), "un": UPNEXT, "upnext": upnext(), "sq": SQUEEZE, "squeeze": squeeze(), "anim": letters_anim(), "line": slots(*SLOT_LINE), "fill": slots(*SLOT_FILL),
   "clock": slots(*SLOT_CLOCK)}


def main():
    with open(XML, encoding="utf-8") as f:
        xml = f.read()
    block = group()
    if "<!-- RETRO ADS START" in xml:
        xml = re.sub(r"        <!-- RETRO ADS START.*?<!-- RETRO ADS END -->\n", lambda _m: block, xml, flags=re.S)
    else:
        anchor = "        <!-- ============ Promo: channel, show, episode"
        if anchor not in xml:
            sys.exit("anchor not found in " + XML)
        xml = xml.replace(anchor, block + "\n" + anchor, 1)
    with open(XML, "w", encoding="utf-8", newline="\n") as f:
        f.write(xml)
    print("retro group written:", XML)


if __name__ == "__main__":
    main()
