#!/usr/bin/env python3
"""Letter pictures for the retro-ad cards (CableBox 42).

Kodi 21 can't load a font from a script add-on, and the skins' own fonts stop at
about 60 px, so the ad cards are lettered with pictures of letters that Kodi
places one by one (resources/lib/ads.py), like the 90s promo titles.  Text is
never baked into a background: the cards stay data-driven and translatable.

    python3 tools/retro-ads/make_glyphs.py [FONTDIR]

FONTDIR holds the DejaVu fonts (default: C:/Windows/Fonts or
/usr/share/fonts/truetype/dejavu).  Needs Pillow.  Writes
resources/skins/Default/media/retroads/<set>/<hex>.png (white letters,
<hex>o.png: the same letter with a thick outline, drawn behind it in the outline
colour) and retroads/glyphs.json.  The previews in retro-ads/samples were drawn
with the same DejaVu faces.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(REPO, "resources", "skins", "Default", "media", "retroads")

ASCII = [chr(c) for c in range(0x21, 0x7F)]
TYPO = list(u"\u2018\u2019\u201c\u201d\u2013\u2014\u2022\u2026\u00a2\u00b7\u00e9")
LATIN1 = [chr(c) for c in range(0xA1, 0x100) if c not in (0xAD,)]

# set: (font file, cell size in px, characters, outline stroke as a share of the size)
SETS = {
    "sb": ("DejaVuSansCondensed-Bold.ttf", 120, ASCII + TYPO + LATIN1, 0.075),          # bold
    "sbi": ("DejaVuSansCondensed-BoldOblique.ttf", 150, ASCII + TYPO, 0.075),           # bold italic
    "sr": ("DejaVuSansCondensed.ttf", 64, ASCII + TYPO + LATIN1, 0),                    # regular
    "si": ("DejaVuSansCondensed-Oblique.ttf", 72, ASCII + TYPO + LATIN1, 0),            # italic
    "fb": ("DejaVuSerif-Bold.ttf", 150, ASCII + TYPO, 0.045),                           # serif bold
    "fi": ("DejaVuSerif-Italic.ttf", 64, ASCII + TYPO, 0),                              # serif italic
}


def font_dir():
    if len(sys.argv) > 1:
        return sys.argv[1]
    for d in ("C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu"):
        if os.path.exists(os.path.join(d, "DejaVuSans.ttf")):
            return d
    sys.exit("DejaVu fonts not found: give the folder as the first argument")


def build(name, fname, size, chars, outline, fdir):
    font = ImageFont.truetype(os.path.join(fdir, fname), size)
    asc, desc = font.getmetrics()
    stroke = int(round(size * outline))
    pad = stroke + 2
    folder = os.path.join(OUT, name)
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        if f.endswith(".png"):
            os.remove(os.path.join(folder, f))
    glyphs = {}
    h = asc + desc + 2 * pad
    for c in chars:
        l, _t, r, _b = font.getbbox(c)
        adv = font.getlength(c)
        if r <= l:
            continue
        w = int(r - l) + 2 * pad
        base = "%04x" % ord(c)
        for suffix, sw in (("", 0), ("o", stroke)):
            if suffix and not stroke:
                continue
            im = Image.new("LA", (w, h), (255, 0))
            ImageDraw.Draw(im).text((pad - l, pad), c, font=font, fill=(255, 255),
                                    stroke_width=sw, stroke_fill=(255, 255))
            im.save(os.path.join(folder, base + suffix + ".png"), optimize=True)
        # picture width, advance, left edge of the picture from the pen (all at `size`)
        glyphs[c] = [w, round(adv, 2), l - pad]
    return {"size": size, "ascent": asc, "descent": desc, "pad": pad, "outline": bool(stroke),
            "space": round(font.getlength(" "), 2), "glyphs": glyphs}


def main():
    fdir = font_dir()
    data = {}
    for name, (fname, size, chars, outline) in SETS.items():
        data[name] = build(name, fname, size, chars, outline, fdir)
        print(name, len(data[name]["glyphs"]))
    with open(os.path.join(OUT, "glyphs.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


if __name__ == "__main__":
    main()
