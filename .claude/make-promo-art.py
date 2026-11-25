#!/usr/bin/env python3
"""Builds the 90s promo artwork (development only - .claude/ is never shipped).

Writes resources/skins/Default/media/promo90s/:
  glyphs/*.png + glyphs.json   title lettering, pre-rendered from Bebas Neue
                               (SIL OFL 1.1).  Kodi 21 can't load fonts from a
                               script add-on, so the titles are laid out letter by
                               letter (promos.glyph_text), like the CH digits.
  band.png, band_shadow.png    the chunky slanted band and its offset shadow
  tab.png                      the time tab (stretchable: border="24,0,56,0")
  squiggle.png, triangles.png, starburst.png, confetti.png   corner shapes
  LICENSE.txt

Every shape is drawn here from scratch for CableBox 42 (CC0); colours come
from the add-on's own icon.  Needs Pillow.

    python .claude/make-promo-art.py --font path/to/BebasNeue-Regular.ttf
"""
import argparse
import json
import math
import os
import random

from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "resources", "skins", "Default", "media", "promo90s")
SS = 3                                  # supersampling for smooth edges

TEAL = (0, 200, 200)
MAGENTA = (200, 0, 200)
PURPLE = (36, 20, 95)
YELLOW = (255, 210, 60)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

CHARS = ("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
         "&'’:;!?.,-#/()\"“”+%$@*"
         "ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏ"
         "ÑÒÓÔÕÖØÙÚÛÜÝ")
GLYPH_H = 132                           # image height of one letter
SHEAR = 0.20                            # italic slant
STROKE = 6                              # black outline


def canvas(w, h):
    return Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))


def done(im, w, h, path):
    im = im.resize((w, h), Image.LANCZOS)
    im.save(path, optimize=True)


def glyphs(font_path):
    d = os.path.join(OUT, "glyphs")
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        os.remove(os.path.join(d, f))
    size = 150
    font = ImageFont.truetype(font_path, size * SS)
    asc, desc = font.getmetrics()
    meta = {"height": GLYPH_H, "space": 0, "glyphs": {}}
    pad = STROKE + 4
    shear_px = int(math.ceil(SHEAR * GLYPH_H)) + 2
    top = int((asc - font.getbbox("H")[1]) * 0.0)          # keep the font's own baseline
    for c in CHARS:
        adv = font.getlength(c) / SS
        w = int(math.ceil(adv)) + 2 * pad + shear_px
        im = Image.new("RGBA", (w * SS, GLYPH_H * SS), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        y = (GLYPH_H * SS - (asc + desc)) // 2 + top + 6 * SS
        dr.text((pad * SS, y), c, font=font, fill=WHITE, stroke_width=STROKE * SS, stroke_fill=BLACK)
        # italic: shift each row right in proportion to its height above the bottom
        im = im.transform(im.size, Image.AFFINE, (1, SHEAR, -SHEAR * im.size[1], 0, 1, 0), Image.BICUBIC)
        im = im.resize((w, GLYPH_H), Image.LANCZOS)
        name = "u%04x.png" % ord(c)
        im.save(os.path.join(d, name), optimize=True)
        meta["glyphs"][c] = [name, w, round(adv, 1)]
    meta["pad"] = pad
    meta["space"] = round(font.getlength(" ") / SS, 1)
    with open(os.path.join(OUT, "glyphs.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=True, separators=(",", ":"))


def band():
    w, h, slant = 1360, 200, 60
    for name, colour in (("band.png", MAGENTA), ("band_shadow.png", TEAL)):
        im = canvas(w, h)
        dr = ImageDraw.Draw(im)
        dr.polygon([(slant * SS, 0), (w * SS, 0), ((w - slant) * SS, h * SS), (0, h * SS)], fill=colour + (255,))
        if name == "band.png":         # a yellow speed line along the top edge
            dr.polygon([((slant + 30) * SS, 14 * SS), ((w - 40) * SS, 14 * SS), ((w - 42) * SS, 22 * SS),
                        ((slant + 28) * SS, 22 * SS)], fill=YELLOW + (255,))
        done(im, w, h, os.path.join(OUT, name))


def tab():
    w, h = 300, 96
    im = canvas(w, h)
    dr = ImageDraw.Draw(im)
    b = 5 * SS
    dr.polygon([(0, 0), (w * SS, 0), ((w - 40) * SS, h * SS), (0, h * SS)], fill=BLACK + (255,))
    dr.polygon([(b, b), (w * SS - b * 2.2, b), ((w - 40) * SS - b * 1.2, h * SS - b), (b, h * SS - b)],
               fill=YELLOW + (255,))
    done(im, w, h, os.path.join(OUT, "tab.png"))


def squiggle():
    w, h = 320, 110
    im = canvas(w, h)
    dr = ImageDraw.Draw(im)
    pts = [((10 + x) * SS, (h / 2 + 30 * math.sin(x / 26.0)) * SS) for x in range(0, w - 20, 2)]
    dr.line(pts, fill=BLACK + (255,), width=22 * SS, joint="curve")
    dr.line(pts, fill=TEAL + (255,), width=13 * SS, joint="curve")
    done(im, w, h, os.path.join(OUT, "squiggle.png"))


def triangles():
    w, h = 240, 200
    im = canvas(w, h)
    dr = ImageDraw.Draw(im)
    for (cx, cy, r, rot, col) in ((80, 110, 70, 10, YELLOW), (175, 70, 48, -25, MAGENTA), (180, 160, 34, 40, TEAL)):
        pts = [((cx + r * math.cos(math.radians(rot + a))) * SS, (cy + r * math.sin(math.radians(rot + a))) * SS)
               for a in (-90, 30, 150)]
        dr.polygon(pts, fill=BLACK + (255,))
        inner = [((cx + (r - 9) * math.cos(math.radians(rot + a))) * SS,
                  (cy + (r - 9) * math.sin(math.radians(rot + a))) * SS) for a in (-90, 30, 150)]
        dr.polygon(inner, fill=col + (255,))
    done(im, w, h, os.path.join(OUT, "triangles.png"))


def starburst():
    w = h = 230
    im = canvas(w, h)
    dr = ImageDraw.Draw(im)
    cx = cy = w / 2
    for r_out, r_in, col in ((112, 72, BLACK), (100, 64, YELLOW)):
        pts = []
        for i in range(28):
            r = r_out if i % 2 == 0 else r_in
            a = math.pi * 2 * i / 28
            pts.append(((cx + r * math.cos(a)) * SS, (cy + r * math.sin(a)) * SS))
        dr.polygon(pts, fill=col + (255,))
    done(im, w, h, os.path.join(OUT, "starburst.png"))


def confetti():
    w, h = 280, 200
    im = canvas(w, h)
    dr = ImageDraw.Draw(im)
    rnd = random.Random(42)
    for i in range(16):
        x, y = rnd.randint(20, w - 30), rnd.randint(20, h - 30)
        col = (TEAL, MAGENTA, YELLOW, WHITE)[i % 4]
        if i % 3 == 0:
            r = rnd.randint(8, 13)
            dr.ellipse([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], fill=col + (255,),
                       outline=BLACK + (255,), width=3 * SS)
        else:
            a = rnd.uniform(0, math.pi)
            l = rnd.randint(16, 26)
            p0 = ((x - l * math.cos(a)) * SS, (y - l * math.sin(a)) * SS)
            p1 = ((x + l * math.cos(a)) * SS, (y + l * math.sin(a)) * SS)
            dr.line([p0, p1], fill=BLACK + (255,), width=12 * SS)
            dr.line([p0, p1], fill=col + (255,), width=6 * SS)
    done(im, w, h, os.path.join(OUT, "confetti.png"))


LICENSE = """90s promo artwork (this folder)

glyphs/*.png - the promo title lettering - are images of letters rendered from
Bebas Neue, Copyright (c) 2010 by Dharma Type, licensed under the SIL Open Font
License, Version 1.1 (https://openfontlicense.org).  Kodi 21 cannot load fonts
from a script add-on, so CableBox 42 ships the letters as pictures instead of
the font file.

Everything else here (band, tab, squiggle, triangles, starburst, confetti) was
drawn for CableBox 42 by .claude/make-promo-art.py in the source repository and
is dedicated to the public domain under CC0 1.0 Universal:
https://creativecommons.org/publicdomain/zero/1.0/
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", default=os.path.join(os.environ.get("APPDATA", ""), "Kodi", "addons",
                                                    "skin.marquee", "fonts", "BebasNeue-Regular.ttf"))
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    glyphs(a.font)
    band()
    tab()
    squiggle()
    triangles()
    starburst()
    confetti()
    with open(os.path.join(OUT, "LICENSE.txt"), "w", encoding="utf-8") as f:
        f.write(LICENSE)
    total = sum(os.path.getsize(os.path.join(dp, f)) for dp, _d, fs in os.walk(OUT) for f in fs)
    print("wrote %s (%d KB)" % (OUT, total // 1024))


if __name__ == "__main__":
    main()
