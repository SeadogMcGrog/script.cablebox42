#!/usr/bin/env python3
"""The station ID card's moving layers (CableBox 42), from make_bg.py's section 9.

The station ID stretches to fill the last seconds of a break, so its motion loops
gently instead of ending: the rays turn slowly and a glint crosses the gold band.
Kodi can only move whole pictures, so the card is drawn in layers (bottom to top):

    sid_base.jpg   the blue background, the spot and the grain (bg_9 without the rays,
                   rings, stars, band, badge and strip)
    sid_rays.png   the rays alone, a square centred on their middle (960, 440): the skin
                   turns it 15 degrees and starts again (the pattern repeats every 15)
    sid_top.png    rings, stars, gold band, number badge and tagline strip
    sid_glint.png  a soft streak the skin slides across the band

At rest the layers look like bg_9_station_id.jpg (the grain is only on the base).

    python3 tools/retro-ads/make_station_layers.py [OUT_DIR]

OUT_DIR defaults to resources/skins/Default/media/station (the skin names them).
Needs rsvg-convert and Pillow.  Keep the
shapes in step with station_id() in make_bg.py (helpers are read from that file).
"""
import os
import subprocess
import sys
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "resources", "skins", "Default", "media", "station")
TMP = tempfile.mkdtemp()

# make_bg.py's helpers (svg, rays, star, NOISE, SHADOW) without running its main loop
_argv = sys.argv
sys.argv = [_argv[0], TMP]
_src = open(os.path.join(HERE, "make_bg.py"), encoding="utf-8").read().split("# ---------- 1.")[0]
_ns = {}
exec(compile(_src, "make_bg.py", "exec"), _ns)
sys.argv = _argv
svg, rays, star, NOISE, SHADOW = _ns["svg"], _ns["rays"], _ns["star"], _ns["NOISE"], _ns["SHADOW"]
W, H = _ns["W"], _ns["H"]

CX, CY = 960, 440            # the rays' middle
HALF = 1160                  # the rays square's half side: covers every corner (1154 px away) at any angle
RAYS_PX = 1160               # drawn at half size; the skin shows it at 2 * HALF


def render(body, defs, path, w=W, h=H, jpg=False):
    sp = os.path.join(TMP, "layer.svg")
    doc = svg(body, defs)
    if (w, h) != (W, H):
        doc = doc.replace(f'width="{W}" height="{H}" viewBox="0 0 {W} {H}"',
                          f'width="{w}" height="{h}" viewBox="0 0 {w} {h}"')
    with open(sp, "w", encoding="utf-8") as f:
        f.write(doc)
    png = path if not jpg else os.path.join(TMP, "layer.png")
    subprocess.run(["rsvg-convert", "-w", str(w), "-h", str(h), "-o", png, sp], check=True)
    if jpg:
        Image.open(png).convert("RGB").save(path, quality=82, optimize=True, progressive=True)
    else:
        im = Image.open(png)
        im.save(path, optimize=True)


def base():
    defs = ('<radialGradient id="sbg" cx="0.5" cy="0.42" r="0.85">'
            '<stop offset="0" stop-color="#2b4fd6"/><stop offset="0.55" stop-color="#14257a"/>'
            '<stop offset="1" stop-color="#070d33"/></radialGradient>'
            '<radialGradient id="spot" cx="0.5" cy="0.5" r="0.5">'
            '<stop offset="0" stop-color="#ffffff" stop-opacity="0.35"/>'
            '<stop offset="1" stop-color="#ffffff" stop-opacity="0"/></radialGradient>' + NOISE)
    b = f'<rect width="{W}" height="{H}" fill="url(#sbg)"/>'
    b += f'<ellipse cx="{CX}" cy="{CY}" rx="720" ry="330" fill="url(#spot)"/>'
    b += f'<rect width="{W}" height="{H}" filter="url(#noise)"/>'
    render(b, defs, os.path.join(OUT, "sid_base.jpg"), jpg=True)


def ray_layer():
    s = RAYS_PX
    k = s / (2.0 * HALF)
    b = f'<g opacity="0.16">{rays(s / 2, s / 2, 48, 1700 * k, "#9fd0ff", "none")}</g>'
    render(b, "", os.path.join(OUT, "sid_rays.png"), s, s)


def top():
    defs = ('<linearGradient id="band" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#ffd23a"/><stop offset="1" stop-color="#f29a12"/></linearGradient>'
            + SHADOW)
    b = (f'<ellipse cx="{CX}" cy="{CY}" rx="640" ry="250" fill="none" stroke="#9fd0ff" stroke-width="4" '
         f'opacity="0.5" transform="rotate(-8 {CX} {CY})"/>')
    b += (f'<ellipse cx="{CX}" cy="{CY}" rx="700" ry="285" fill="none" stroke="#ffd23a" stroke-width="3" '
          f'opacity="0.45" stroke-dasharray="4 18" stroke-linecap="round" transform="rotate(6 {CX} {CY})"/>')
    for x, y, r in ((300, 190, 16), (1640, 640, 12), (1560, 170, 9), (380, 700, 10)):
        b += f'<polygon points="{star(x, y, 4, r*2.4, r*0.6)}" fill="#ffffff" opacity="0.85"/>'
    b += '<polygon points="180,700 1740,700 1700,800 1740,900 180,900 220,800" fill="url(#band)" filter="url(#shadow)"/>'
    b += '<rect x="180" y="706" width="1560" height="6" fill="#fff3c4" opacity="0.8"/>'
    b += '<circle cx="1660" cy="190" r="118" fill="#c4171f" stroke="#ffffff" stroke-width="10" filter="url(#shadow)"/>'
    b += f'<rect x="0" y="960" width="{W}" height="120" fill="#070d33" opacity="0.75"/>'
    render(b, defs, os.path.join(OUT, "sid_top.png"))


def glint():
    # a slanted, soft-edged streak; the skin keeps it inside the band (y 712-898)
    w, h = 260, 186
    defs = ('<linearGradient id="gl" x1="0" y1="0" x2="1" y2="0">'
            '<stop offset="0" stop-color="#ffffff" stop-opacity="0"/>'
            '<stop offset="0.5" stop-color="#ffffff" stop-opacity="0.55"/>'
            '<stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>')
    b = f'<polygon points="90,0 170,0 120,{h} 40,{h}" fill="url(#gl)"/>'
    b += f'<polygon points="190,0 214,0 164,{h} 140,{h}" fill="url(#gl)" opacity="0.6"/>'
    render(b, defs, os.path.join(OUT, "sid_glint.png"), w, h)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    base()
    ray_layer()
    top()
    glint()
    for f in ("sid_base.jpg", "sid_rays.png", "sid_top.png", "sid_glint.png"):
        print("%-14s %4d KB" % (f, os.path.getsize(os.path.join(OUT, f)) // 1024))
