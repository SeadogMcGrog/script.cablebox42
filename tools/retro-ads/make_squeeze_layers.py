#!/usr/bin/env python3
"""The squeezed-credits screen's layers (CableBox 42), from make_bg.py's section 11.

The episode keeps playing (its own picture and sound) in Kodi's video window, which
the skin shrinks into the frame; around it:

    sq_base.jpg    background, stripes, the white frame and black slot, the bottom
                   strip (drawn BEHIND the video window)
    sq_panel.png   the right panel: UP NEXT tab, info box, countdown box (slides in)

At rest the two look like bg_11_squeeze.jpg.

    python3 tools/retro-ads/make_squeeze_layers.py [OUT_DIR]

OUT_DIR defaults to resources/skins/Default/media/squeeze.  Needs rsvg-convert and
Pillow.  Keep the shapes in step with squeeze() in make_bg.py.
"""
import os
import subprocess
import sys
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "resources", "skins", "Default", "media", "squeeze")
TMP = tempfile.mkdtemp()
_argv = sys.argv
sys.argv = [_argv[0], TMP]
_src = open(os.path.join(HERE, "make_bg.py"), encoding="utf-8").read().split("# ---------- 1.")[0]
_ns = {}
exec(compile(_src, "make_bg.py", "exec"), _ns)
sys.argv = _argv
svg, NOISE, SHADOW = _ns["svg"], _ns["NOISE"], _ns["SHADOW"]
W, H = _ns["W"], _ns["H"]
VIDWIN = (70, 150, 1120, 630)


def render(body, defs, path, jpg=False):
    sp = os.path.join(TMP, "layer.svg")
    with open(sp, "w", encoding="utf-8") as f:
        f.write(svg(body, defs))
    png = path if not jpg else os.path.join(TMP, "layer.png")
    subprocess.run(["rsvg-convert", "-w", str(W), "-h", str(H), "-o", png, sp], check=True)
    if jpg:
        Image.open(png).convert("RGB").save(path, quality=82, optimize=True, progressive=True)
    else:
        Image.open(png).save(path, optimize=True)


def base():
    defs = ('<linearGradient id="sqbg" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#0d1a5c"/><stop offset="0.6" stop-color="#2a1466"/>'
            '<stop offset="1" stop-color="#4a1260"/></linearGradient>' + SHADOW + NOISE)
    b = f'<rect width="{W}" height="{H}" fill="url(#sqbg)"/>'
    for i, c in enumerate(["#ff3fa4", "#ffd23a", "#3ee6d0"]):
        x = 1500 + i * 46
        b += f'<polygon points="{x},0 {x+28},0 {x+28-520},{H} {x-520},{H}" fill="{c}" opacity="0.10"/>'
    x, y, w, h = VIDWIN
    b += f'<rect x="{x-10}" y="{y-10}" width="{w+20}" height="{h+20}" rx="14" fill="#ffffff" opacity="0.9" filter="url(#shadow)"/>'
    b += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#000000"/>'
    b += f'<rect x="0" y="850" width="{W}" height="130" fill="#07102e" opacity="0.8"/>'
    b += '<rect x="0" y="850" width="1920" height="5" fill="#ffd23a"/>'
    b += f'<rect width="{W}" height="{H}" filter="url(#noise)"/>'
    render(b, defs, os.path.join(OUT, "sq_base.jpg"), jpg=True)


def panel():
    defs = ('<linearGradient id="gold2" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#ffd23a"/><stop offset="1" stop-color="#f29a12"/></linearGradient>' + SHADOW)
    b = '<polygon points="1240,150 1850,150 1820,240 1240,240" fill="url(#gold2)" filter="url(#shadow)"/>'
    b += '<rect x="1240" y="270" width="610" height="340" rx="16" fill="#07102e" opacity="0.8"/>'
    b += '<rect x="1240" y="640" width="610" height="140" rx="16" fill="#c4171f" stroke="#ffffff" stroke-width="5" filter="url(#shadow)"/>'
    render(b, defs, os.path.join(OUT, "sq_panel.png"))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    base()
    panel()
    for f in ("sq_base.jpg", "sq_panel.png"):
        print("%-13s %4d KB" % (f, os.path.getsize(os.path.join(OUT, f)) // 1024))
