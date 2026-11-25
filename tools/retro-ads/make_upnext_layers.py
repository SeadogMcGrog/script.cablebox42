#!/usr/bin/env python3
"""The "Up next" card's layers (CableBox 42), from make_bg.py's section 10.

The card can stay up for about 90 seconds between films, so its motion loops gently:
the stripes drift and a glint crosses the gold UP NEXT tab.  Kodi only moves whole
pictures, so the card is drawn in layers (bottom to top):

    un_base.jpg     the purple-blue background and its grain
    un_stripes.png  the three diagonal speed stripes (the skin drifts them to and fro)
    un_top.png      the UP NEXT tab, the picture's TV bezel and dark slot, the gold rule,
                    and the three boxes along the bottom (time, channel, countdown)
    un_glint.png    a soft streak the skin slides across the tab
    un_mask.png     the picture slot's rounded corners (the skin's diffuse mask)

At rest the layers look like bg_10_up_next.jpg (the grain is only on the base).

    python3 tools/retro-ads/make_upnext_layers.py [OUT_DIR]

OUT_DIR defaults to resources/skins/Default/media/upnext.  Needs rsvg-convert and
Pillow.  Keep the shapes in step with up_next() in make_bg.py.
"""
import os
import subprocess
import sys
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "resources", "skins", "Default", "media", "upnext")
TMP = tempfile.mkdtemp()

_argv = sys.argv
sys.argv = [_argv[0], TMP]
_src = open(os.path.join(HERE, "make_bg.py"), encoding="utf-8").read().split("# ---------- 1.")[0]
_ns = {}
exec(compile(_src, "make_bg.py", "exec"), _ns)
sys.argv = _argv
svg, NOISE, SHADOW = _ns["svg"], _ns["NOISE"], _ns["SHADOW"]
W, H = _ns["W"], _ns["H"]
ART = (120, 250, 960, 540)


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
        Image.open(png).save(path, optimize=True)


def base():
    defs = ('<linearGradient id="ubg" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#0d1a5c"/><stop offset="0.6" stop-color="#2a1466"/>'
            '<stop offset="1" stop-color="#4a1260"/></linearGradient>' + NOISE)
    b = f'<rect width="{W}" height="{H}" fill="url(#ubg)"/><rect width="{W}" height="{H}" filter="url(#noise)"/>'
    render(b, defs, os.path.join(OUT, "un_base.jpg"), jpg=True)


def stripes():
    b = ""
    for i, c in enumerate(["#ff3fa4", "#ffd23a", "#3ee6d0"]):
        x = 1350 + i * 46
        b += f'<polygon points="{x},0 {x+28},0 {x+28-520},{H} {x-520},{H}" fill="{c}" opacity="0.10"/>'
    render(b, "", os.path.join(OUT, "un_stripes.png"))


def top():
    defs = ('<linearGradient id="gold" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#ffd23a"/><stop offset="1" stop-color="#f29a12"/></linearGradient>'
            '<linearGradient id="bezel" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#e8eef6"/><stop offset="0.5" stop-color="#7d8798"/>'
            '<stop offset="1" stop-color="#d5dce6"/></linearGradient>' + SHADOW)
    b = '<polygon points="120,90 700,90 660,200 120,200" fill="url(#gold)" filter="url(#shadow)"/>'
    b += '<polygon points="700,90 740,90 700,200 660,200" fill="#ff3fa4"/>'
    x, y, w, h = ART
    b += f'<rect x="{x-22}" y="{y-22}" width="{w+44}" height="{h+44}" rx="34" fill="url(#bezel)" filter="url(#shadow)"/>'
    b += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="#0a0a14"/>'
    b += '<rect x="1150" y="485" width="650" height="5" fill="#ffd23a" opacity="0.9"/>'
    b += '<rect x="120" y="870" width="420" height="150" rx="22" fill="#c4171f" stroke="#ffffff" stroke-width="6" filter="url(#shadow)"/>'
    b += '<rect x="570" y="885" width="760" height="120" rx="16" fill="#07102e" opacity="0.75"/>'
    b += '<rect x="1360" y="885" width="440" height="120" rx="16" fill="#07102e" stroke="#3ee6d0" stroke-width="4" opacity="0.9"/>'
    render(b, defs, os.path.join(OUT, "un_top.png"))


def glint():
    w, h = 200, 110
    defs = ('<linearGradient id="gl" x1="0" y1="0" x2="1" y2="0">'
            '<stop offset="0" stop-color="#ffffff" stop-opacity="0"/>'
            '<stop offset="0.5" stop-color="#ffffff" stop-opacity="0.6"/>'
            '<stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>')
    b = f'<polygon points="70,0 130,0 100,{h} 40,{h}" fill="url(#gl)"/>'
    b += f'<polygon points="145,0 163,0 133,{h} 115,{h}" fill="url(#gl)" opacity="0.6"/>'
    render(b, defs, os.path.join(OUT, "un_glint.png"), w, h)


def mask():
    _x, _y, w, h = ART
    render(f'<rect width="{w}" height="{h}" rx="18" fill="#ffffff"/>', "", os.path.join(OUT, "un_mask.png"), w, h)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    base()
    stripes()
    top()
    glint()
    mask()
    for f in ("un_base.jpg", "un_stripes.png", "un_top.png", "un_glint.png", "un_mask.png"):
        print("%-15s %4d KB" % (f, os.path.getsize(os.path.join(OUT, f)) // 1024))
