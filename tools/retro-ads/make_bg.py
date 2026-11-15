#!/usr/bin/env python3
"""Draw CableBox 42 retro-ad sample backgrounds as SVG, render to 1920x1080 PNG.
Writes blank backgrounds (bg_*.png) and previews with sample text (preview_*.png).
All shapes are drawn from scratch here; no outside art."""
import math, os, subprocess, sys

W, H = 1920, 1080
OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
os.makedirs(OUT, exist_ok=True)
FONT = "DejaVu Sans Condensed"


def svg(body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}"><defs>{defs}</defs>{body}</svg>')


def rays(cx, cy, n, r, c1, c2, rot=0):
    out = []
    for i in range(n):
        a0 = math.radians(rot + i * 360 / n)
        a1 = math.radians(rot + (i + 0.5) * 360 / n)
        p = f"{cx},{cy} {cx + r*math.cos(a0):.1f},{cy + r*math.sin(a0):.1f} {cx + r*math.cos(a1):.1f},{cy + r*math.sin(a1):.1f}"
        out.append(f'<polygon points="{p}" fill="{c1 if i % 2 == 0 else c2}"/>')
    return "".join(out)


def star(cx, cy, n, r1, r2, rot=-90):
    pts = []
    for i in range(n * 2):
        r = r1 if i % 2 == 0 else r2
        a = math.radians(rot + i * 180 / n)
        pts.append(f"{cx + r*math.cos(a):.1f},{cy + r*math.sin(a):.1f}")
    return " ".join(pts)


def text(x, y, s, size, fill, weight="bold", anchor="start", stroke=None, sw=0,
         style="normal", family=FONT, extra=""):
    st = f' stroke="{stroke}" stroke-width="{sw}" paint-order="stroke" stroke-linejoin="round"' if stroke else ""
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
            f'font-weight="{weight}" font-style="{style}" fill="{fill}" '
            f'text-anchor="{anchor}"{st} {extra}>{s}</text>')


NOISE = ('<filter id="noise" x="0" y="0" width="100%" height="100%">'
         '<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7"/>'
         '<feColorMatrix type="saturate" values="0"/>'
         '<feComponentTransfer><feFuncA type="linear" slope="0.10"/></feComponentTransfer></filter>')
SHADOW = ('<filter id="shadow" x="-10%" y="-10%" width="130%" height="130%">'
          '<feDropShadow dx="8" dy="10" stdDeviation="6" flood-color="#000" flood-opacity="0.45"/></filter>')
GLOW_M = ('<filter id="glow" x="-20%" y="-20%" width="140%" height="140%">'
          '<feGaussianBlur stdDeviation="8" result="b"/><feMerge><feMergeNode in="b"/>'
          '<feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')


# ---------- 1. Pitch card (early-90s product pitch) ----------
def pitch(preview):
    defs = ('<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#2a0f6b"/><stop offset="0.55" stop-color="#7a1a8c"/>'
            '<stop offset="1" stop-color="#d0306e"/></linearGradient>'
            '<radialGradient id="fade" cx="0.82" cy="0.42" r="0.75">'
            '<stop offset="0" stop-color="#fff" stop-opacity="0.0"/>'
            '<stop offset="1" stop-color="#1a0840" stop-opacity="0.65"/></radialGradient>'
            + SHADOW + NOISE)
    b = f'<rect width="{W}" height="{H}" fill="url(#g)"/>'
    b += f'<g opacity="0.22">{rays(1560, 450, 36, 1800, "#ffd23a", "none", 3)}</g>'
    b += f'<rect width="{W}" height="{H}" fill="url(#fade)"/>'
    # squiggles and confetti, very early-90s
    b += ('<path d="M120 120 q40 -40 80 0 t80 0 t80 0" stroke="#3ee6d0" stroke-width="12" fill="none" stroke-linecap="round"/>'
          '<path d="M1700 960 q30 -30 60 0 t60 0" stroke="#ffd23a" stroke-width="10" fill="none" stroke-linecap="round"/>'
          '<circle cx="1820" cy="110" r="22" fill="#3ee6d0"/><rect x="980" y="70" width="34" height="34" fill="#ffd23a" transform="rotate(20 997 87)"/>'
          '<polygon points="80,820 120,760 160,820" fill="#ff7a3a"/>')
    # thin inner frame
    b += f'<rect x="36" y="36" width="{W-72}" height="{H-72}" fill="none" stroke="#ffd23a" stroke-width="6" rx="18"/>'
    # price starburst
    b += f'<polygon points="{star(1500, 640, 20, 250, 205, -90)}" fill="#ffd23a" stroke="#c4171f" stroke-width="10" filter="url(#shadow)"/>'
    # bottom call-to-action bar
    b += f'<rect x="0" y="900" width="{W}" height="12" fill="#fff"/><rect x="0" y="912" width="{W}" height="132" fill="#c4171f"/>'
    b += f'<rect x="0" y="1044" width="{W}" height="36" fill="#7a0b10"/>'
    b += f'<rect width="{W}" height="{H}" filter="url(#noise)"/>'
    if preview:
        b += text(110, 300, "CRISP-O-MATIC", 150, "#ffd23a", stroke="#1a0840", sw=14, style="italic")
        b += text(110, 420, "Countertop Fryer", 92, "#ffffff", stroke="#1a0840", sw=10)
        b += text(110, 560, "Fries in 4 minutes.", 70, "#3ee6d0", stroke="#1a0840", sw=8, style="italic")
        b += text(110, 650, "Cleans in 4 seconds!", 70, "#3ee6d0", stroke="#1a0840", sw=8, style="italic")
        b += text(1500, 590, "ONLY", 60, "#c4171f", anchor="middle")
        b += text(1500, 700, "$19.99", 110, "#c4171f", anchor="middle")
        b += text(W/2, 1000, "ORDER NOW!  1-800-555-0134", 84, "#ffffff", anchor="middle")
    return svg(b, defs)


# ---------- 2. Local business (cheap wood-panel sign) ----------
def local(preview):
    defs = ('<pattern id="wood" width="120" height="1080" patternUnits="userSpaceOnUse">'
            '<rect width="120" height="1080" fill="#6b3f1f"/>'
            '<rect x="0" width="4" height="1080" fill="#3a200e"/>'
            '<path d="M30 0 C40 200 20 400 34 620 S28 900 36 1080" stroke="#5a3318" stroke-width="5" fill="none"/>'
            '<path d="M70 0 C62 260 82 480 70 700 S78 960 68 1080" stroke="#7d4a25" stroke-width="7" fill="none"/>'
            '<path d="M98 0 C104 300 92 520 100 780 S96 1000 102 1080" stroke="#5a3318" stroke-width="3" fill="none"/>'
            '</pattern>'
            '<linearGradient id="panel" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#fbf1d6"/><stop offset="1" stop-color="#ecd9a8"/></linearGradient>'
            '<radialGradient id="vig" cx="0.5" cy="0.5" r="0.75"><stop offset="0.6" stop-color="#000" stop-opacity="0"/>'
            '<stop offset="1" stop-color="#000" stop-opacity="0.55"/></radialGradient>'
            + SHADOW + NOISE)
    b = f'<rect width="{W}" height="{H}" fill="url(#wood)"/>'
    b += f'<rect width="{W}" height="{H}" fill="url(#vig)"/>'
    # the sign
    b += '<rect x="200" y="110" width="1520" height="700" rx="40" fill="#1f5a3a" filter="url(#shadow)"/>'
    b += '<rect x="226" y="136" width="1468" height="648" rx="28" fill="url(#panel)"/>'
    b += '<rect x="250" y="160" width="1420" height="600" rx="20" fill="none" stroke="#c99a2e" stroke-width="6" stroke-dasharray="2 14" stroke-linecap="round"/>'
    # corner stars
    for x, y in ((290, 200), (1630, 200), (290, 720), (1630, 720)):
        b += f'<polygon points="{star(x, y, 5, 26, 11)}" fill="#c4171f"/>'
    # banner ribbon across the top of the sign
    b += ('<polygon points="560,92 1360,92 1400,140 1360,188 560,188 520,140" fill="#c4171f" filter="url(#shadow)"/>'
          '<polygon points="520,140 470,110 490,140 470,170" fill="#8e1016"/>'
          '<polygon points="1400,140 1450,110 1430,140 1450,170" fill="#8e1016"/>')
    # chyron
    b += '<rect x="0" y="880" width="1920" height="140" fill="#1f5a3a"/><rect x="0" y="872" width="1920" height="8" fill="#c99a2e"/><rect x="0" y="1020" width="1920" height="8" fill="#c99a2e"/>'
    b += f'<rect width="{W}" height="{H}" filter="url(#noise)"/>'
    if preview:
        b += text(W/2, 162, "NO MONEY DOWN!", 56, "#fff", anchor="middle")
        b += text(W/2, 380, "BIG EARL'S", 170, "#1f5a3a", anchor="middle", family="DejaVu Serif", stroke="#c99a2e", sw=6)
        b += text(W/2, 500, "FURNITURE BARN", 110, "#c4171f", anchor="middle", family="DejaVu Serif")
        b += text(W/2, 640, "“If you can sit on it, Earl’s got it!”", 64, "#3a200e", anchor="middle", style="italic", weight="normal", family="DejaVu Serif")
        b += text(W/2, 975, "Route 9 by the water tower  •  555-0117", 64, "#fbf1d6", anchor="middle")
    return svg(b, defs)


# ---------- 3. PSA (calm, official-ish) ----------
def psa(preview):
    defs = ('<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#0f3d7a"/><stop offset="1" stop-color="#4f9bd9"/></linearGradient>'
            '<radialGradient id="sun" cx="0.5" cy="1.1" r="0.9"><stop offset="0" stop-color="#fff6c8" stop-opacity="0.75"/>'
            '<stop offset="1" stop-color="#fff6c8" stop-opacity="0"/></radialGradient>' + SHADOW + NOISE)
    b = f'<rect width="{W}" height="{H}" fill="url(#sky)"/>'
    b += f'<g opacity="0.10">{rays(960, 1250, 28, 1700, "#ffffff", "none")}</g>'
    b += f'<rect width="{W}" height="{H}" fill="url(#sun)"/>'
    # rolling hills
    b += ('<path d="M0 900 C300 820 600 860 900 900 S1500 960 1920 880 L1920 1080 L0 1080 Z" fill="#2f7d4a"/>'
          '<path d="M0 960 C400 900 800 990 1200 960 S1700 920 1920 970 L1920 1080 L0 1080 Z" fill="#256a3d"/>')
    # seal on the left
    b += '<g filter="url(#shadow)">'
    b += f'<polygon points="{star(330, 470, 32, 190, 172)}" fill="#e8c34a"/>'
    b += '<circle cx="330" cy="470" r="150" fill="#fdf6e0" stroke="#0f3d7a" stroke-width="10"/>'
    b += '<circle cx="330" cy="470" r="120" fill="none" stroke="#0f3d7a" stroke-width="3" stroke-dasharray="6 8"/>'
    b += f'<polygon points="{star(330, 385, 5, 26, 11)}" fill="#c4171f"/>'
    b += f'<polygon points="{star(330, 575, 5, 22, 9)}" fill="#c4171f"/></g>'
    # text panel
    b += '<rect x="580" y="250" width="1200" height="440" rx="24" fill="#fdf6e0" opacity="0.95" filter="url(#shadow)"/>'
    b += '<rect x="580" y="250" width="1200" height="18" rx="9" fill="#c4171f"/>'
    b += f'<rect width="{W}" height="{H}" filter="url(#noise)"/>'
    if preview:
        b += text(330, 450, "COUNCIL", 34, "#0f3d7a", anchor="middle")
        b += text(330, 488, "FOR", 26, "#0f3d7a", anchor="middle", weight="normal")
        b += text(330, 528, "POSTURE", 34, "#0f3d7a", anchor="middle")
        b += text(640, 380, "Sit up straight.", 110, "#0f3d7a")
        b += text(640, 490, "Your spine has feelings too.", 64, "#2f4f6f", style="italic", weight="normal")
        b += text(640, 620, "A message from the Council for Sitting Up Straight", 38, "#2f4f6f", weight="normal")
        b += text(W/2, 790, "and this station.", 52, "#ffffff", anchor="middle", style="italic", stroke="#0f3d7a", sw=6)
    return svg(b, defs)


# ---------- 4. Classifieds / Shopper page ----------
def classifieds(preview):
    defs = ('<pattern id="dots" width="14" height="14" patternUnits="userSpaceOnUse">'
            '<circle cx="7" cy="7" r="3" fill="#2a2620" opacity="0.35"/></pattern>' + NOISE)
    b = f'<rect width="{W}" height="{H}" fill="#e9e1cc"/>'
    # masthead
    b += '<rect x="80" y="60" width="1760" height="6" fill="#2a2620"/><rect x="80" y="74" width="1760" height="2" fill="#2a2620"/>'
    b += '<rect x="80" y="210" width="1760" height="2" fill="#2a2620"/><rect x="80" y="218" width="1760" height="6" fill="#2a2620"/>'
    # three columns of ad boxes
    cols = [(80, [(240, 330), (590, 420)]), (680, [(240, 520), (780, 230)]), (1280, [(240, 250), (510, 260), (790, 220)])]
    for x, boxes in cols:
        for y, h in boxes:
            b += f'<rect x="{x}" y="{y}" width="560" height="{h}" fill="none" stroke="#2a2620" stroke-width="4"/>'
    # halftone corner in one box
    b += '<rect x="700" y="600" width="520" height="140" fill="url(#dots)"/>'
    # column rules
    b += '<rect x="659" y="240" width="2" height="770" fill="#2a2620"/><rect x="1259" y="240" width="2" height="770" fill="#2a2620"/>'
    b += f'<rect width="{W}" height="{H}" filter="url(#noise)"/>'
    if preview:
        S = "DejaVu Serif"
        b += text(W/2, 175, "THE VALLEY SHOPPER", 110, "#2a2620", anchor="middle", family=S)
        b += text(80, 52, "FREE • TAKE ONE", 28, "#2a2620", family=S, weight="normal")
        b += text(1840, 52, "Classifieds", 28, "#2a2620", anchor="end", family=S, style="italic", weight="normal")
        ads = [
            (100, 300, "LOST CAT", ["Orange, answers to", "“Mr. Biscuits.” Likes", "lasagna. 555-0162"]),
            (100, 650, "PIANO, USED", ["Plays most notes.", "You haul. $50 or", "best offer.", "555-0108"]),
            (700, 300, "GARAGE SALE", ["Saturday 8 am sharp!", "Elm St. Records,", "lamps, one canoe.", "No early birds", "(we mean you, Gary)."]),
            (700, 840, "BOWLING LEAGUE", ["Lucky Lanes needs", "a 4th. 555-0151"]),
            (1300, 300, "FREE KITTENS", ["To good homes.", "Mr. Biscuits says", "“not mine.”"]),
            (1300, 570, "TYPING SERVICE", ["Term papers, resumes.", "Fast! 555-0123"]),
            (1300, 850, "WANTED", ["Canoe. 555-0179"]),
        ]
        for x, y, head, lines in ads:
            b += text(x, y, head, 46, "#2a2620", family=S)
            for i, l in enumerate(lines):
                b += text(x, y + 56 + i * 48, l, 38, "#2a2620", family=S, weight="normal")
    return svg(b, defs)


# ---------- 5. Late-night infomercial (neon grid) ----------
def latenight(preview):
    defs = ('<linearGradient id="night" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#05010f"/><stop offset="0.55" stop-color="#2a0845"/>'
            '<stop offset="0.56" stop-color="#ff3fa4"/><stop offset="0.565" stop-color="#14031f"/>'
            '<stop offset="1" stop-color="#0a0214"/></linearGradient>' + GLOW_M + SHADOW + NOISE)
    b = f'<rect width="{W}" height="{H}" fill="url(#night)"/>'
    hz = 605
    g = '<g stroke="#3ee6f0" stroke-width="3" opacity="0.8" filter="url(#glow)">'
    for i in range(-14, 15):  # perspective lines
        g += f'<line x1="{960 + i*40}" y1="{hz}" x2="{960 + i*260}" y2="{H}"/>'
    y, step = hz + 10, 12
    while y < H:  # horizontal lines getting further apart
        g += f'<line x1="0" y1="{y:.0f}" x2="{W}" y2="{y:.0f}"/>'
        step *= 1.32
        y += step
    b += g + '</g>'
    # stars
    import random
    random.seed(42)
    for _ in range(90):
        b += f'<circle cx="{random.randint(0, W)}" cy="{random.randint(0, 560)}" r="{random.choice([1.5, 2, 2.5, 3])}" fill="#fff" opacity="{random.uniform(0.3, 0.9):.2f}"/>'
    # "as seen on TV" style seal outline (left blank for text)
    b += f'<polygon points="{star(1620, 250, 16, 150, 128)}" fill="#ffd23a" filter="url(#shadow)"/>'
    b += '<circle cx="1620" cy="250" r="112" fill="none" stroke="#c4171f" stroke-width="6"/>'
    # phone bar
    b += '<rect x="160" y="900" width="1600" height="120" rx="60" fill="#05010f" stroke="#ff3fa4" stroke-width="6" filter="url(#glow)"/>'
    b += f'<rect width="{W}" height="{H}" filter="url(#noise)"/>'
    if preview:
        b += text(1620, 235, "AS SEEN", 40, "#c4171f", anchor="middle")
        b += text(1620, 285, "ON TV!", 48, "#c4171f", anchor="middle")
        b += text(140, 250, "BUT WAIT —", 120, "#ff3fa4", style="italic", extra='filter="url(#glow)"')
        b += text(140, 390, "THERE'S MORE!", 150, "#ffffff", style="italic", stroke="#ff3fa4", sw=4)
        b += text(140, 500, "Call in the next 10 minutes for a second", 52, "#3ee6f0", weight="normal")
        b += text(140, 560, "Never-Dull Knife Set — absolutely FREE!", 52, "#3ee6f0", weight="normal")
        b += text(W/2, 982, "OPERATORS ARE STANDING BY  •  1-800-555-0190", 60, "#ffffff", anchor="middle")
    return svg(b, defs)



# ---------- 6. Now on videocassette (poster slot on the left) ----------
POSTER = (170, 150, 520, 780)  # x, y, w, h  (2:3)
def video(preview):
    defs = ('<linearGradient id="vbg" x1="0" y1="0" x2="1" y2="0">'
            '<stop offset="0" stop-color="#0b0b12"/><stop offset="1" stop-color="#1b1430"/></linearGradient>'
            '<linearGradient id="chrome" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#ffffff"/><stop offset="0.45" stop-color="#c9d3e0"/>'
            '<stop offset="0.5" stop-color="#6d7a8c"/><stop offset="1" stop-color="#e8eef6"/></linearGradient>'
            + SHADOW + NOISE)
    b = f'<rect width="{W}" height="{H}" fill="url(#vbg)"/>'
    # diagonal tape-box stripes behind the text area
    cols = ["#ff3b3b", "#ff9a1f", "#ffd23a", "#3ecf6e", "#2f8cff"]
    for i, c in enumerate(cols):
        x = 1480 + i * 60
        b += f'<polygon points="{x},{H} {x+60},{H} {x+60+520},0 {x+520},0" fill="{c}" opacity="0.9"/>'
    b += f'<rect x="760" y="0" width="{W-760}" height="{H}" fill="#0b0b12" opacity="0.35"/>'
    # poster frame (Kodi puts the library poster in the slot)
    x, y, w, h = POSTER
    b += f'<rect x="{x-18}" y="{y-18}" width="{w+36}" height="{h+36}" rx="10" fill="#1d1d28" stroke="url(#chrome)" stroke-width="8" filter="url(#shadow)"/>'
    b += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#2a2a38"/>'
    # cassette window motif under the headline
    b += '<rect x="820" y="760" width="980" height="150" rx="20" fill="#14141c" stroke="#3a3a4a" stroke-width="4"/>'
    for cx in (1010, 1610):
        b += f'<circle cx="{cx}" cy="835" r="52" fill="#0b0b12" stroke="#55556a" stroke-width="6"/>'
        for k in range(6):
            a = math.radians(k * 60)
            b += f'<rect x="{cx-5}" y="{835-48}" width="10" height="22" fill="#55556a" transform="rotate({k*60} {cx} 835)"/>'
    b += '<rect x="1080" y="805" width="460" height="60" rx="8" fill="#22222e"/>'
    b += f'<rect width="{W}" height="{H}" filter="url(#noise)"/>'
    if preview:
        b += text(x + w/2, y + h/2 - 20, "MOVIE POSTER", 40, "#6a6a80", anchor="middle")
        b += text(x + w/2, y + h/2 + 30, "from your library", 30, "#6a6a80", anchor="middle", weight="normal")
        b += text(820, 255, "NOW ON", 84, "url(#chrome)", style="italic", stroke="#0b0b12", sw=10)
        b += text(820, 370, "VIDEOCASSETTE!", 104, "url(#chrome)", style="italic", stroke="#0b0b12", sw=10)
        b += text(820, 520, "The Long Weekend (1988)", 72, "#ffffff")
        b += text(820, 600, "Own it today! Ask for it by name.", 50, "#ffd23a", style="italic", weight="normal")
        b += text(820, 680, "Rated PG", 40, "#c9d3e0", weight="normal")
        b += text(1310, 1000, "Available wherever videos are sold", 44, "#ffffff", anchor="middle")
    return svg(b, defs)


# ---------- 7. Kids pitch card (toys, cereal) ----------
def kids(preview):
    defs = ('<pattern id="pd" width="90" height="90" patternUnits="userSpaceOnUse">'
            '<circle cx="22" cy="22" r="10" fill="#ffffff" opacity="0.25"/>'
            '<circle cx="67" cy="67" r="10" fill="#ffffff" opacity="0.25"/></pattern>' + SHADOW + NOISE)
    b = f'<rect width="{W}" height="{H}" fill="#19b5e8"/><rect width="{W}" height="{H}" fill="url(#pd)"/>'
    # wavy green band and zigzags
    b += '<path d="M0 760 Q240 680 480 760 T960 760 T1440 760 T1920 760 L1920 1080 L0 1080 Z" fill="#46d16a"/>'
    b += '<path d="M0 800 Q240 720 480 800 T960 800 T1440 800 T1920 800" stroke="#ffffff" stroke-width="10" fill="none" opacity="0.6"/>'
    zz = "M60 90 " + " ".join(f"L{60+i*40} {90 + (30 if i % 2 else 0)}" for i in range(1, 16))
    b += f'<path d="{zz}" stroke="#ffd23a" stroke-width="14" fill="none" stroke-linejoin="round"/>'
    zz2 = "M1250 1010 " + " ".join(f"L{1250+i*40} {1010 + (30 if i % 2 else 0)}" for i in range(1, 16))
    b += f'<path d="{zz2}" stroke="#ff4fa3" stroke-width="14" fill="none" stroke-linejoin="round"/>'
    # shapes
    b += f'<polygon points="{star(1780, 140, 5, 70, 30)}" fill="#ffd23a" transform="rotate(12 1780 140)"/>'
    b += '<circle cx="140" cy="640" r="46" fill="#ff4fa3"/><rect x="1650" y="620" width="80" height="80" rx="14" fill="#ffd23a" transform="rotate(-15 1690 660)"/>'
    # price splat
    splat = []
    for i in range(28):
        r = 230 if i % 2 == 0 else 175 + (i * 37 % 40)
        a = math.radians(i * 360 / 28)
        splat.append(f"{1460 + r*math.cos(a):.0f},{470 + r*math.sin(a):.0f}")
    b += f'<polygon points="{" ".join(splat)}" fill="#ff4fa3" stroke="#ffffff" stroke-width="10" stroke-linejoin="round" filter="url(#shadow)"/>'
    # bottom small-print strip
    b += f'<rect x="0" y="960" width="{W}" height="120" fill="#7a2fd0"/>'
    b += f'<rect width="{W}" height="{H}" filter="url(#noise)"/>'
    if preview:
        b += text(120, 310, "ROBO-REX!", 190, "#ffd23a", stroke="#7a2fd0", sw=18, style="italic")
        b += text(120, 430, "He roars! He stomps!", 76, "#ffffff", stroke="#0d5f80", sw=10)
        b += text(120, 520, "He's afraid of the vacuum.", 76, "#ffffff", stroke="#0d5f80", sw=10)
        b += text(1460, 445, "ONLY", 56, "#ffffff", anchor="middle")
        b += text(1460, 545, "$39.99", 110, "#ffffff", anchor="middle", stroke="#7a2fd0", sw=8)
        b += text(W/2, 1035, "Batteries not included  •  Each sold separately", 48, "#ffffff", anchor="middle", weight="normal")
    return svg(b, defs)


# ---------- 8. Contest / sweepstakes ----------
def contest(preview):
    defs = ('<radialGradient id="cbg" cx="0.5" cy="0.45" r="0.8">'
            '<stop offset="0" stop-color="#1e8a5a"/><stop offset="1" stop-color="#0a3a26"/></radialGradient>'
            + SHADOW + NOISE)
    b = f'<rect width="{W}" height="{H}" fill="url(#cbg)"/>'
    b += f'<g opacity="0.18">{rays(960, 470, 40, 1600, "#ffd23a", "none")}</g>'
    # marquee bulbs border
    for i in range(48):
        x = 60 + i * (1800 / 47)
        for y in (50, 1030):
            b += f'<circle cx="{x:.0f}" cy="{y}" r="11" fill="{"#ffe680" if i % 2 else "#ffffff"}"/>'
    for i in range(1, 27):
        y = 50 + i * (980 / 27)
        for x in (60, 1860):
            b += f'<circle cx="{x}" cy="{y:.0f}" r="11" fill="{"#ffe680" if i % 2 else "#ffffff"}"/>'
    # ticket shape in the middle
    b += ('<path d="M360 220 H1560 a50 50 0 0 0 50 50 V650 a50 50 0 0 0 -50 50 H360 a50 50 0 0 0 -50 -50 V270 a50 50 0 0 0 50 -50 Z" '
          'fill="#fff4cf" stroke="#c4171f" stroke-width="10" filter="url(#shadow)"/>')
    b += '<line x1="1300" y1="240" x2="1300" y2="680" stroke="#c4171f" stroke-width="5" stroke-dasharray="16 12"/>'
    # phone / small print bar
    b += '<rect x="200" y="800" width="1520" height="150" rx="20" fill="#c4171f" filter="url(#shadow)"/>'
    b += f'<rect width="{W}" height="{H}" filter="url(#noise)"/>'
    if preview:
        b += text(820, 360, "WIN!", 150, "#c4171f", anchor="middle", stroke="#ffd23a", sw=6)
        b += text(820, 470, "A trip to beautiful", 64, "#0a3a26", anchor="middle")
        b += text(820, 560, "Lake Whatever!", 84, "#0a3a26", anchor="middle", style="italic")
        b += text(820, 630, "Two nights! One canoe!", 44, "#0a3a26", anchor="middle", weight="normal")
        b += text(1450, 440, "ADMIT", 48, "#c4171f", anchor="middle")
        b += text(1450, 510, "ONE", 64, "#c4171f", anchor="middle")
        b += text(W/2, 875, "CALL 1-900-555-0188", 72, "#ffffff", anchor="middle")
        b += text(W/2, 925, "$1.99 per minute  •  must be 18 or older", 36, "#ffe680", anchor="middle", weight="normal")
    return svg(b, defs)


# ---------- 9. Station ID ("You're watching ...") ----------
LOGO = (510, 250, 900, 380)  # x, y, w, h: channel logo, fit inside, centred
def station_id(preview):
    defs = ('<radialGradient id="sbg" cx="0.5" cy="0.42" r="0.85">'
            '<stop offset="0" stop-color="#2b4fd6"/><stop offset="0.55" stop-color="#14257a"/>'
            '<stop offset="1" stop-color="#070d33"/></radialGradient>'
            '<linearGradient id="band" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#ffd23a"/><stop offset="1" stop-color="#f29a12"/></linearGradient>'
            '<radialGradient id="spot" cx="0.5" cy="0.5" r="0.5">'
            '<stop offset="0" stop-color="#ffffff" stop-opacity="0.35"/>'
            '<stop offset="1" stop-color="#ffffff" stop-opacity="0"/></radialGradient>'
            + SHADOW + NOISE)
    b = f'<rect width="{W}" height="{H}" fill="url(#sbg)"/>'
    b += f'<g opacity="0.16">{rays(960, 440, 48, 1700, "#9fd0ff", "none")}</g>'
    b += '<ellipse cx="960" cy="440" rx="720" ry="330" fill="url(#spot)"/>'
    # orbit rings around the logo area, a bit of cable-network swagger
    b += '<ellipse cx="960" cy="440" rx="640" ry="250" fill="none" stroke="#9fd0ff" stroke-width="4" opacity="0.5" transform="rotate(-8 960 440)"/>'
    b += '<ellipse cx="960" cy="440" rx="700" ry="285" fill="none" stroke="#ffd23a" stroke-width="3" opacity="0.45" stroke-dasharray="4 18" stroke-linecap="round" transform="rotate(6 960 440)"/>'
    for x, y, r in ((300, 190, 16), (1640, 640, 12), (1560, 170, 9), (380, 700, 10)):
        b += f'<polygon points="{star(x, y, 4, r*2.4, r*0.6)}" fill="#ffffff" opacity="0.85"/>'
    # name band
    b += '<polygon points="180,700 1740,700 1700,800 1740,900 180,900 220,800" fill="url(#band)" filter="url(#shadow)"/>'
    b += '<rect x="180" y="706" width="1560" height="6" fill="#fff3c4" opacity="0.8"/>'
    # channel number badge
    b += '<circle cx="1660" cy="190" r="118" fill="#c4171f" stroke="#ffffff" stroke-width="10" filter="url(#shadow)"/>'
    # bottom strip for the tagline
    b += f'<rect x="0" y="960" width="{W}" height="120" fill="#070d33" opacity="0.75"/>'
    b += f'<rect width="{W}" height="{H}" filter="url(#noise)"/>'
    if preview:
        x, y, w, h = LOGO
        b += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="#ffffff" stroke-width="3" stroke-dasharray="14 10" opacity="0.6"/>'
        b += text(960, 450, "CHANNEL LOGO", 64, "#ffffff", anchor="middle", extra='opacity="0.75"')
        b += text(960, 510, "(fit inside, centred)", 34, "#ffffff", anchor="middle", weight="normal", extra='opacity="0.6"')
        b += text(960, 160, "YOU'RE WATCHING", 64, "#ffffff", anchor="middle", style="italic", stroke="#070d33", sw=8)
        b += text(1660, 160, "CH", 36, "#ffffff", anchor="middle")
        b += text(1660, 250, "12", 96, "#ffffff", anchor="middle")
        b += text(960, 832, "THE ANIMATION STATION", 92, "#14257a", anchor="middle")
        b += text(960, 1035, "Cartoons all day, every day", 48, "#ffffff", anchor="middle", style="italic", weight="normal")
    return svg(b, defs)


# ---------- 10. Up next (end-of-show card; can run 90 s between movies) ----------
ART = (120, 250, 960, 540)     # 16:9 picture slot: episode still / fanart / poster, else channel logo
TLOGO = (1150, 250, 650, 200)  # show/movie logo slot (clearlogo), else title text
def up_next(preview):
    defs = ('<linearGradient id="ubg" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#0d1a5c"/><stop offset="0.6" stop-color="#2a1466"/>'
            '<stop offset="1" stop-color="#4a1260"/></linearGradient>'
            '<linearGradient id="gold" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#ffd23a"/><stop offset="1" stop-color="#f29a12"/></linearGradient>'
            '<linearGradient id="bezel" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#e8eef6"/><stop offset="0.5" stop-color="#7d8798"/>'
            '<stop offset="1" stop-color="#d5dce6"/></linearGradient>'
            + SHADOW + NOISE)
    b = f'<rect width="{W}" height="{H}" fill="url(#ubg)"/>'
    # diagonal speed stripes behind the right column
    for i, c in enumerate(["#ff3fa4", "#ffd23a", "#3ee6d0"]):
        x = 1350 + i * 46
        b += f'<polygon points="{x},0 {x+28},0 {x+28-520},{H} {x-520},{H}" fill="{c}" opacity="0.10"/>'
    # UP NEXT tab
    b += '<polygon points="120,90 700,90 660,200 120,200" fill="url(#gold)" filter="url(#shadow)"/>'
    b += '<polygon points="700,90 740,90 700,200 660,200" fill="#ff3fa4"/>'
    # picture slot with a TV bezel
    x, y, w, h = ART
    b += f'<rect x="{x-22}" y="{y-22}" width="{w+44}" height="{h+44}" rx="34" fill="url(#bezel)" filter="url(#shadow)"/>'
    b += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="#0a0a14"/>'
    # right column divider rules
    b += '<rect x="1150" y="485" width="650" height="5" fill="#ffd23a" opacity="0.9"/>'
    # bottom bar: start time (big), channel, countdown
    b += '<rect x="120" y="870" width="420" height="150" rx="22" fill="#c4171f" stroke="#ffffff" stroke-width="6" filter="url(#shadow)"/>'
    b += '<rect x="570" y="885" width="760" height="120" rx="16" fill="#07102e" opacity="0.75"/>'
    b += '<rect x="1360" y="885" width="440" height="120" rx="16" fill="#07102e" stroke="#3ee6d0" stroke-width="4" opacity="0.9"/>'
    b += f'<rect width="{W}" height="{H}" filter="url(#noise)"/>'
    if preview:
        b += text(140, 172, "UP NEXT", 80, "#14257a", style="italic")
        b += text(x + w/2, y + h/2 - 10, "EPISODE STILL / FANART", 44, "#5a5a75", anchor="middle")
        b += text(x + w/2, y + h/2 + 40, "else channel logo", 30, "#5a5a75", anchor="middle", weight="normal")
        lx, ly, lw, lh = TLOGO
        b += text(lx, ly + 90, "The Long", 96, "#ffffff")
        b += text(lx, ly + 190, "Weekend", 96, "#ffffff")
        b += text(lx, 560, "Season 2 · Episode 5", 46, "#ffd23a")
        b += text(lx, 620, "“The Canoe”", 46, "#ffffff", style="italic", weight="normal")
        for i, l in enumerate(["Gary arrives early to the garage", "sale and leaves with more than", "he bargained for."]):
            b += text(lx, 700 + i * 50, l, 38, "#c9d3e0", weight="normal")
        b += text(330, 910, "AT", 28, "#ffffff", anchor="middle")
        b += text(330, 1000, "4:30", 84, "#ffffff", anchor="middle")
        b += text(950, 960, "CH 12 · The Animation Station", 46, "#ffffff", anchor="middle")
        b += text(1580, 935, "STARTS IN", 32, "#3ee6d0", anchor="middle")
        b += text(1580, 990, "2:14", 60, "#ffffff", anchor="middle")
    return svg(b, defs)


# ---------- 11. Squeezed credits (show keeps playing, smaller, with "Up next") ----------
VIDWIN = (70, 150, 1120, 630)   # 16:9 video window; Kodi letterboxes/pillarboxes inside it
def squeeze(preview):
    defs = ('<linearGradient id="sqbg" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#0d1a5c"/><stop offset="0.6" stop-color="#2a1466"/>'
            '<stop offset="1" stop-color="#4a1260"/></linearGradient>'
            '<linearGradient id="gold2" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#ffd23a"/><stop offset="1" stop-color="#f29a12"/></linearGradient>'
            + SHADOW + NOISE)
    b = f'<rect width="{W}" height="{H}" fill="url(#sqbg)"/>'
    for i, c in enumerate(["#ff3fa4", "#ffd23a", "#3ee6d0"]):
        x = 1500 + i * 46
        b += f'<polygon points="{x},0 {x+28},0 {x+28-520},{H} {x-520},{H}" fill="{c}" opacity="0.10"/>'
    x, y, w, h = VIDWIN
    b += f'<rect x="{x-10}" y="{y-10}" width="{w+20}" height="{h+20}" rx="14" fill="#ffffff" opacity="0.9" filter="url(#shadow)"/>'
    b += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#000000"/>'
    # right panel
    b += '<polygon points="1240,150 1850,150 1820,240 1240,240" fill="url(#gold2)" filter="url(#shadow)"/>'
    b += '<rect x="1240" y="270" width="610" height="340" rx="16" fill="#07102e" opacity="0.8"/>'
    b += '<rect x="1240" y="640" width="610" height="140" rx="16" fill="#c4171f" stroke="#ffffff" stroke-width="5" filter="url(#shadow)"/>'
    # bottom strip
    b += f'<rect x="0" y="850" width="{W}" height="130" fill="#07102e" opacity="0.8"/>'
    b += '<rect x="0" y="850" width="1920" height="5" fill="#ffd23a"/>'
    b += f'<rect width="{W}" height="{H}" filter="url(#noise)"/>'
    if preview:
        b += text(x + w/2, y + h/2 - 10, "THE SHOW KEEPS PLAYING HERE", 44, "#5a5a75", anchor="middle")
        b += text(x + w/2, y + h/2 + 40, "(end credits, with its own sound)", 30, "#5a5a75", anchor="middle", weight="normal")
        b += text(1260, 215, "UP NEXT", 64, "#14257a", style="italic")
        b += text(1270, 340, "Star Trek", 64, "#ffffff")
        b += text(1270, 400, "“The Man Trap”", 40, "#ffd23a", style="italic", weight="normal")
        for i, l in enumerate(["The Enterprise visits an old", "flame of Dr. McCoy's. Things", "get strange."]):
            b += text(1270, 470 + i * 44, l, 34, "#c9d3e0", weight="normal")
        b += text(1545, 688, "STARTS IN", 30, "#ffffff", anchor="middle")
        b += text(1545, 762, "0:45", 64, "#ffffff", anchor="middle")
        b += text(960, 935, "CH 3 · Keystone  •  Next at 5:00", 50, "#ffffff", anchor="middle")
    return svg(b, defs)

SETS = {"1_pitch_card": pitch, "2_local_business": local, "3_psa": psa,
        "4_classifieds": classifieds, "5_late_night": latenight,
        "6_video": video, "7_kids_pitch": kids, "8_contest": contest, "9_station_id": station_id, "10_up_next": up_next, "11_squeeze": squeeze}

for name, fn in SETS.items():
    for kind, prev in (("bg", False), ("preview", True)):
        sp = os.path.join(OUT, f"{kind}_{name}.svg")
        with open(sp, "w", encoding="utf-8") as f:
            f.write(fn(prev))
        subprocess.run(["rsvg-convert", "-w", str(W), "-h", str(H), "-o", sp[:-4] + ".png", sp], check=True)
        os.remove(sp)
        if kind == "bg":  # ship version: JPG, small enough for the Kodi repository
            from PIL import Image
            Image.open(sp[:-4] + ".png").convert("RGB").save(sp[:-4] + ".jpg", quality=82, optimize=True, progressive=True)
print("done")
