#!/usr/bin/env python3
"""Promo contact sheet (development only - .claude/ is never shipped).

Renders the promo card of every TV show in your Kodi library at 1080p and 720p
and builds one HTML page of thumbnails with the show name under each.

It runs a *copy* of Kodi in portable mode with its own profile, so your own
Kodi install, settings, library and thumbnails are never written to:

  - Kodi (the program folder) is copied to <out>/_kodi
  - your video library database (and sources.xml / advancedsettings.xml /
    passwords.xml, needed for shares and MySQL libraries) and CableBox's own
    data (channels, schedules, settings) are *copied* into its profile
  - this repository is installed into it as the add-on, plus a tiny renderer
  - the cards are drawn by the add-on's own code (promo_preview.card_for_show,
    the same code as Settings > Advanced > Preview promo), without music

Windows only (Kodi's portable mode, -p).  Kodi allows one copy at a time, so
**close Kodi first** - the script stops if it is running.

    python .claude/promo-contact-sheet.py
    python .claude/promo-contact-sheet.py --kodi G:/Kodi --out G:/CableBox42/promo-contact-sheet --limit 10

Output: <out>/index.html, <out>/1080/<tvshowid>.png, <out>/720/<tvshowid>.png.
"""
import argparse
import glob
import html
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8099

RENDERER = r'''
import json, os, sys, time, traceback
import xbmc, xbmcgui, xbmcvfs
CB = xbmcvfs.translatePath("special://home/addons/script.cablebox42")
sys.path.insert(0, CB)
from resources.lib import promo_preview, promos, kodiutil as K
OUT, TAG, LIMIT = sys.argv[1], sys.argv[2], int(sys.argv[3])
WANT = [x.strip().lower() for x in sys.argv[4].split("|") if x.strip()] if len(sys.argv) > 4 else []
STYLE = sys.argv[5] if len(sys.argv) > 5 else ""
AT = [float(x) for x in sys.argv[6].split("|")] if len(sys.argv) > 6 and sys.argv[6] else [3.5]
PRELOAD = not (len(sys.argv) > 7 and sys.argv[7] == "cold")
if STYLE in ("90s", "modern"):
    K.set_setting("promo_style", 1 if STYLE == "modern" else 0)
d = os.path.join(OUT, TAG)
shows = K.rpc("VideoLibrary.GetTVShows", {"properties": ["title"], "sort": {"method": "title", "ignorearticle": True}}).get("tvshows", [])
if WANT:
    shows = [s for s in shows if any(w == s["title"].lower() or (w.endswith("*") and s["title"].lower().startswith(w[:-1])) for w in WANT)]
if LIMIT:
    shows = shows[:LIMIT]
w = xbmcgui.WindowXML("script-cablebox42-tv.xml", CB, "Default", "1080i")
w.show()
xbmc.sleep(2000)
now = time.time()
cards = []
for s in shows:
    row = {"id": s["tvshowid"], "title": s["title"]}
    try:
        # like the TV: the logo loads during the spot before the card (up to a spot's length)
        t = promo_preview.target(s["tvshowid"], now)
        cand = promos.info(t["path"], t["title"]).get("logo") or ""
        row["logo_file"] = bool(cand)
        row["cached_before"] = bool(cand) and promos.texture_cached(cand)
        if cand and PRELOAD and not row["cached_before"]:
            w.setProperty("mode", "")
            w.setProperty("promo_preload", cand)
            t1 = time.time()
            while time.time() - t1 < 15 and not promos.texture_cached(cand):
                xbmc.sleep(250)
            row["preload_s"] = round(time.time() - t1, 2)
        props, music, _t = promo_preview.card_for_show(s["tvshowid"], now)
        w.setProperty("mode", "")
        xbmc.sleep(150)
        promos.apply_card(w, props)
        xbmc.sleep(1500)                       # textures load in the background before the card comes up
        w.setProperty("mode", "promo")
        t0 = time.time()
        for i, at in enumerate(AT):            # the last capture is the card's settled look
            xbmc.sleep(max(0, int((at - (time.time() - t0)) * 1000)))
            name = "%d.png" % s["tvshowid"] if i == len(AT) - 1 else "%d_t%03d.png" % (s["tvshowid"], int(round(at * 10)))
            xbmc.executebuiltin('TakeScreenshot("%s/%s",true)' % (d.replace("\\", "/"), name), True)
        xbmc.sleep(400)
        row.update(props=props, music=("built-in tune" if music == promos.BED else ("theme.mp3" if music else "none")))
    except Exception:
        row["error"] = traceback.format_exc()
    cards.append(row)
w.close()
json.dump(cards, open(os.path.join(d, "cards.json"), "w", encoding="utf-8"), indent=1)
open(os.path.join(d, "done"), "w").write("ok")
xbmc.executebuiltin("Quit")
'''

RENDERER_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="script.cbcontactsheet" name="CableBox promo contact sheet" version="0.0.1" provider-name="dev">
  <requires><import addon="xbmc.python" version="3.0.0"/></requires>
  <extension point="xbmc.python.script" library="default.py"/>
  <extension point="xbmc.addon.metadata"><summary lang="en_GB">dev</summary><platform>all</platform></extension>
</addon>
'''


def kodi_running():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq kodi.exe"], capture_output=True, text=True).stdout
    return "kodi.exe" in out.lower()


def screen_size():
    try:
        import ctypes
        u = ctypes.windll.user32
        return u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    except Exception:
        return 0, 0


def rpc(method, params=None, timeout=5):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode()
    req = urllib.request.Request("http://127.0.0.1:%d/jsonrpc" % PORT, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def copytree(src, dst, skip_dots=False):
    def ignore(_d, names):
        return [n for n in names if n == "__pycache__" or n.endswith(".pyc") or (skip_dots and n.startswith("."))]
    shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)


def prepare(args, work):
    exe = os.path.join(work, "kodi.exe")
    if not os.path.exists(exe):
        print("Copying Kodi from %s ..." % args.kodi)
        copytree(args.kodi, work)
    pd = os.path.join(work, "portable_data")
    ud = os.path.join(pd, "userdata")
    os.makedirs(os.path.join(ud, "Database"), exist_ok=True)
    os.makedirs(os.path.join(pd, "addons"), exist_ok=True)
    dbs = sorted(glob.glob(os.path.join(args.userdata, "Database", "MyVideos*.db")),
                 key=lambda p: int("".join(c for c in os.path.basename(p) if c.isdigit()) or 0))
    if not dbs:
        sys.exit("No MyVideos*.db in %s" % args.userdata)
    shutil.copy2(dbs[-1], os.path.join(ud, "Database"))         # a copy: yours is only read
    for f in ("sources.xml", "advancedsettings.xml", "passwords.xml", "mediasources.xml"):
        if os.path.exists(os.path.join(args.userdata, f)):
            shutil.copy2(os.path.join(args.userdata, f), ud)
    adv = os.path.join(ud, "advancedsettings.xml")
    if not os.path.exists(adv):
        # Kodi only redraws what changes; a card that has stopped moving would be captured stale
        with open(adv, "w", encoding="utf-8") as f:
            f.write("<advancedsettings><gui><algorithmdirtyregions>0</algorithmdirtyregions></gui></advancedsettings>\n")
    cb = os.path.join(args.userdata, "addon_data", "script.cablebox42")
    if os.path.isdir(cb) and not args.no_lineup:
        copytree(cb, os.path.join(ud, "addon_data", "script.cablebox42"))
    addon = os.path.join(pd, "addons", "script.cablebox42")
    shutil.rmtree(addon, ignore_errors=True)
    copytree(args.addon, addon, skip_dots=True)
    r = os.path.join(pd, "addons", "script.cbcontactsheet")
    os.makedirs(r, exist_ok=True)
    open(os.path.join(r, "addon.xml"), "w", encoding="utf-8").write(RENDERER_XML)
    open(os.path.join(r, "default.py"), "w", encoding="utf-8").write(RENDERER)
    print("Using %s (copied)" % os.path.basename(dbs[-1]))
    return ud


def run_kodi(work, ud, out, tag, w, h, limit, shows="", style="", at="", cold=False):
    sw, sh = screen_size()
    mode = "DESKTOP" if (w, h) == (sw, sh) else "WINDOW"
    with open(os.path.join(ud, "guisettings.xml"), "w", encoding="utf-8") as f:
        f.write('<settings version="2">\n' + "".join('    <setting id="%s">%s</setting>\n' % kv for kv in (
            ("services.webserver", "true"), ("services.webserverport", PORT),
            ("services.webserverauthentication", "false"), ("videoscreen.screenmode", mode),
            ("window.width", w), ("window.height", h), ("input.enablemouse", "false"),
            ("general.addonupdates", "2"))) + "</settings>\n")
    d = os.path.join(out, tag)
    os.makedirs(d, exist_ok=True)
    for p in glob.glob(os.path.join(d, "*")):
        os.remove(p)
    print("Starting Kodi at %dx%d (%s) ..." % (w, h, "full screen" if mode == "DESKTOP" else "window"))
    proc = subprocess.Popen([os.path.join(work, "kodi.exe"), "-p"], cwd=work)
    try:
        for _i in range(90):
            try:
                if rpc("JSONRPC.Ping").get("result") == "pong":
                    break
            except Exception:
                time.sleep(1)
        else:
            sys.exit("Kodi's web server never answered")
        time.sleep(3)
        for a in ("script.cablebox42", "script.cbcontactsheet"):
            rpc("Addons.SetAddonEnabled", {"addonid": a, "enabled": True})
        n = len(rpc("VideoLibrary.GetTVShows").get("result", {}).get("tvshows", []))
        n = min(n, limit) if limit else n
        n = min(n, len(shows.split("|"))) if shows else n
        print("Rendering %d shows ..." % n)
        rpc("Addons.ExecuteAddon", {"addonid": "script.cbcontactsheet",
                                    # RunScript splits its parameters at commas: none may contain one
                                    "params": [out, tag, str(limit), shows, style or "-", at.replace(",", "|") or "3.5",
                                               "cold" if cold else "warm"]})
        deadline = time.time() + 90 + n * (8 if cold else 24)
        while time.time() < deadline and not os.path.exists(os.path.join(d, "done")):
            time.sleep(2)
        if not os.path.exists(os.path.join(d, "done")):
            print("Timed out; see %s" % os.path.join(work, "portable_data", "temp", "kodi.log"))
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
    finally:
        if proc.poll() is None:
            proc.kill()
    return json.load(open(os.path.join(d, "cards.json"), encoding="utf-8")) if os.path.exists(os.path.join(d, "cards.json")) else []


def thumbs(out, tags):
    try:
        from PIL import Image
    except ImportError:
        return False
    for tag in tags:
        for p in glob.glob(os.path.join(out, tag, "*.png")):
            t = p[:-4] + ".thumb.jpg"
            im = Image.open(p).convert("RGB")
            im.thumbnail((480, 270))
            im.save(t, quality=85)
    return True


def page(out, results, have_thumbs):
    tags = list(results)
    by_id = {}
    for tag, cards in results.items():
        for c in cards:
            by_id.setdefault(c["id"], {"title": c["title"]})[tag] = c
    rows = []
    for sid, r in sorted(by_id.items(), key=lambda kv: kv[1]["title"].lower()):
        c = next((r[t] for t in tags if t in r), {})
        p = c.get("props") or {}
        badges = []
        if c.get("error"):
            badges.append('<b class="err">error</b>')
        else:
            badges.append("logo" if p.get("promo_logo") else '<b class="warn">title text</b>')
            if c.get("logo_file") and not c.get("cached_before"):
                badges.append("first-ever: %s" % ("preloaded in %.1f s" % c["preload_s"] if "preload_s" in c
                                                  else "no preload"))
            badges.append("poster" if p.get("promo_letterbox") else ("art" if p.get("promo_bg") else '<b class="warn">no art</b>'))
            badges.append("plot" if p.get("promo_plot") else '<b class="warn">no plot</b>')
            badges.append(html.escape(c.get("music") or ""))
        shots = []
        for t in tags:
            png = "%s/%d.png" % (t, sid)
            src = "%s/%d.thumb.jpg" % (t, sid) if have_thumbs else png
            if os.path.exists(os.path.join(out, t, "%d.png" % sid)):
                shots.append('<a href="%s"><img src="%s" loading="lazy" alt=""><span>%sp</span></a>' % (png, src, t))
            else:
                shots.append('<div class="miss">%sp: no screenshot</div>' % t)
        err = '<pre>%s</pre>' % html.escape(c["error"]) if c.get("error") else ""
        rows.append('<figure><div class="shots">%s</div><figcaption><strong>%s</strong><small>%s</small>%s</figcaption></figure>'
                    % ("".join(shots), html.escape(r["title"]), " &middot; ".join(badges), err))
    doc = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Promo contact sheet</title>
<style>
:root{--bg:#101218;--card:#1a1d26;--fg:#e8ebf3;--dim:#9aa3b5;--warn:#ffd24a;--err:#ff6b6b}
body{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif}
h1{font-size:20px;margin:0 0 4px}p{color:var(--dim);margin:0 0 20px}
main{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%%,500px),1fr));gap:16px}
figure{margin:0;background:var(--card);border-radius:8px;padding:10px}
.shots{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.shots a{position:relative;display:block}.shots img{width:100%%;display:block;border-radius:4px}
.shots span{position:absolute;right:4px;bottom:4px;background:#000a;color:#fff;font-size:11px;padding:1px 5px;border-radius:3px}
.miss{aspect-ratio:16/9;display:grid;place-items:center;color:var(--err);border:1px dashed #444;border-radius:4px}
figcaption{margin-top:8px}figcaption strong{display:block;font-size:15px}figcaption small{color:var(--dim)}
b.warn{color:var(--warn);font-weight:500}b.err{color:var(--err)}pre{white-space:pre-wrap;color:var(--err);font-size:11px}
</style></head><body><h1>Promo contact sheet</h1>
<p>%d shows &middot; %s &middot; rendered %s by Kodi with the add-on's own promo code. Click a picture for the full screenshot.</p>
<main>%s</main></body></html>""" % (len(by_id), " and ".join("%sp" % t for t in tags), time.strftime("%Y-%m-%d %H:%M"), "\n".join(rows))
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(doc)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kodi", default=r"C:\Program Files\Kodi", help="Kodi's program folder (copied, not changed)")
    ap.add_argument("--userdata", default=os.path.join(os.environ.get("APPDATA", ""), "Kodi", "userdata"),
                    help="your Kodi userdata (only read)")
    ap.add_argument("--addon", default=REPO, help="the add-on folder to install (default: this repository)")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(REPO), "promo-contact-sheet"))
    ap.add_argument("--res", default="1080,720", help="vertical resolutions, e.g. 1080,720")
    ap.add_argument("--limit", type=int, default=0, help="only the first N shows (by title)")
    ap.add_argument("--no-lineup", action="store_true", help="don't copy CableBox's channels and schedules")
    ap.add_argument("--shows", default="", help='only these titles, "|"-separated ("Star Trek*" = starts with)')
    ap.add_argument("--style", choices=("90s", "modern"), default="", help="promo style (default: the setting)")
    ap.add_argument("--at", default="", help="seconds after the card appears to capture, e.g. 0.5,1.2,3.5 "
                                             "(the last one is the thumbnail; default 3.5)")
    ap.add_argument("--cold", action="store_true", help="don't preload logos before each card (a promo with "
                                                         "no spot before it: uncached logos give the title)")
    ap.add_argument("--keep-kodi", action="store_true", help="keep the Kodi copy for the next run")
    args = ap.parse_args()
    if not os.path.exists(os.path.join(args.kodi, "kodi.exe")):
        sys.exit("No kodi.exe in %s (use --kodi)" % args.kodi)
    if kodi_running():
        sys.exit("Kodi is running. Close Kodi first (only one copy can run at a time), then run this again.")
    out = os.path.abspath(args.out)
    work = os.path.join(out, "_kodi")
    os.makedirs(out, exist_ok=True)
    ud = prepare(args, work)
    results = {}
    for r in [int(x) for x in args.res.split(",") if x.strip()]:
        results[str(r)] = run_kodi(work, ud, out, str(r), r * 16 // 9, r, args.limit, args.shows, args.style, args.at,
                                    args.cold)
    have_thumbs = thumbs(out, list(results))
    page(out, results, have_thumbs)
    if not args.keep_kodi:
        shutil.rmtree(work, ignore_errors=True)
    errors = sum(1 for cards in results.values() for c in cards if c.get("error"))
    print("Done: %s  (%s; %d errors)" % (os.path.join(out, "index.html"),
                                         ", ".join("%sp %d cards" % (t, len(c)) for t, c in results.items()), errors))


if __name__ == "__main__":
    main()
