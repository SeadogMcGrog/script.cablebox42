"""The guide's top half (stage 3) in the TV skin: frame (the video is the window's own
control 10, zoomed into it in guide mode - never a second videowindow), panel and caption
while a run plays (Window.Property(gtop) = video); the 1.2.0 header otherwise."""
import sys

p = sys.argv[1]
s = open(p, encoding="utf-8").read()
TXT = "<visible>!String.IsEqual(Window.Property(gtop),video)</visible>"


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:80]
    s = s.replace(old, new)


rep('''            <control type="label">
                <left>70</left><top>40</top><width>1200</width><height>80</height>
                <font>font45</font><textcolor>FFFFD24A</textcolor><shadowcolor>FF000000</shadowcolor>
                <label>$INFO[Window.Property(guide_title)]</label>
            </control>
            <control type="label">
                <left>1250</left><top>40</top><width>600</width><height>80</height>
                <align>right</align><font>font45</font><textcolor>FFFFFFFF</textcolor><shadowcolor>FF000000</shadowcolor>
                <label>$INFO[System.Time]</label>
            </control>
            <control type="label">
                <left>70</left><top>140</top><width>1780</width><height>200</height>
                <font>font37</font><textcolor>FFFFFFFF</textcolor><shadowcolor>FF000000</shadowcolor>
                <wrapmultiline>true</wrapmultiline>
                <label>$INFO[Window.Property(guide_promo)]</label>
            </control>''', '''            <!-- the top half: text and music (as 1.2.0), or a video run (guide stage 3, tv.top_tick) -->
            <control type="group">
                %s
                <control type="label">
                    <left>70</left><top>40</top><width>1200</width><height>80</height>
                    <font>font45</font><textcolor>FFFFD24A</textcolor><shadowcolor>FF000000</shadowcolor>
                    <label>$INFO[Window.Property(guide_title)]</label>
                </control>
                <control type="label">
                    <left>1250</left><top>40</top><width>600</width><height>80</height>
                    <align>right</align><font>font45</font><textcolor>FFFFFFFF</textcolor><shadowcolor>FF000000</shadowcolor>
                    <label>$INFO[System.Time]</label>
                </control>
                <control type="label">
                    <left>70</left><top>140</top><width>1780</width><height>200</height>
                    <font>font37</font><textcolor>FFFFFFFF</textcolor><shadowcolor>FF000000</shadowcolor>
                    <wrapmultiline>true</wrapmultiline>
                    <label>$INFO[Window.Property(guide_promo)]</label>
                </control>
            </control>
            <control type="group">
                <visible>String.IsEqual(Window.Property(gtop),video)</visible>
                <!-- 4:3 video, framed, top left -->
                <control type="image">
                    <left>56</left><top>16</top><width>464</width><height>348</height>
                    <texture colordiffuse="FFD8C890">white.png</texture>
                </control>
                <control type="image">
                    <left>60</left><top>20</top><width>456</width><height>340</height>
                    <texture colordiffuse="FF000000">white.png</texture>
                </control>
                <!-- the picture: the TV window's one video control (id 10) moved into this frame
                     (a zoom on it in guide mode).  Never a second videowindow: with two in the window Kodi
                     redraws at half the display rate (stop motion on the N2) -->
                <!-- the panel: guide title and clock, then the caption -->
                <control type="label">
                    <left>560</left><top>28</top><width>900</width><height>70</height>
                    <font>font37</font><textcolor>FFFFD24A</textcolor><shadowcolor>FF000000</shadowcolor>
                    <label>$INFO[Window.Property(guide_title)]</label>
                </control>
                <control type="label">
                    <left>1460</left><top>28</top><width>400</width><height>70</height>
                    <align>right</align><font>font37</font><textcolor>FFFFFFFF</textcolor><shadowcolor>FF000000</shadowcolor>
                    <label>$INFO[System.Time]</label>
                </control>
                <control type="image">
                    <left>560</left><top>104</top><width>1300</width><height>3</height>
                    <texture colordiffuse="FFD8C890">white.png</texture>
                </control>
                <control type="label">
                    <left>560</left><top>140</top><width>1300</width><height>64</height>
                    <font>font37</font><textcolor>FFFFD24A</textcolor><shadowcolor>FF000000</shadowcolor>
                    <label>$INFO[Window.Property(gt_cap)]</label>
                </control>
                <control type="label">
                    <left>560</left><top>210</top><width>1300</width><height>150</height>
                    <font>font45</font><textcolor>FFFFFFFF</textcolor><shadowcolor>FF000000</shadowcolor>
                    <wrapmultiline>true</wrapmultiline>
                    <label>$INFO[Window.Property(gt_title)]</label>
                </control>
            </control>''' % TXT)
open(p, "w", encoding="utf-8", newline="").write(s)
