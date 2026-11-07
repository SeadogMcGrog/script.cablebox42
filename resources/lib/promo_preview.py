"""Settings > Advanced > Preview promo: one show's promo card, straight away,
exactly as it appears in a break (same card, same theme music, same fade).

    RunScript(script.cablebox42,preview_promo)            pick a show
    RunScript(script.cablebox42,preview_promo,<tvshowid>)  that show

It uses the show's next airing in the channels' schedules when there is one
(nothing is built or changed); otherwise its home channel, its first episode
and the next half hour.
"""
import threading
import time

import xbmc
import xbmcgui

from . import kodiutil as K
from . import promos
from . import scheduler
from . import stations
from . import logos
from .kodiutil import _



def pick_show():
    """The show picker (with posters): a tvshowid, or None."""
    shows = K.rpc("VideoLibrary.GetTVShows", {"properties": ["title", "year", "art"],
                                               "sort": {"method": "title", "ignorearticle": True}}).get("tvshows", [])
    if not shows:
        xbmcgui.Dialog().ok(_("Preview promo"), _("No TV shows in the library"))
        return None
    items = []
    for s in shows:
        li = xbmcgui.ListItem(s.get("title", ""), str(s.get("year") or ""))
        art = s.get("art") or {}
        li.setArt({"thumb": art.get("poster") or art.get("thumb") or "", "icon": art.get("poster") or ""})
        items.append(li)
    i = xbmcgui.Dialog().select(_("Preview a promo for which show?"), items, useDetails=True)
    return shows[i]["tvshowid"] if i >= 0 else None


def _first_episode(tvshowid):
    from . import library
    eps = library.episodes_for(tvshowid)
    return eps[0]["file"] if eps else ""


def target(tvshowid, now=None):
    """{title, path, pt, ch, later} for this show's promo."""
    now = now or time.time()
    d = K.rpc("VideoLibrary.GetTVShowDetails", {"tvshowid": int(tvshowid), "properties": ["title"]})
    title = (d.get("tvshowdetails") or {}).get("title") or ""
    out = {"title": title, "path": "", "pt": None, "ch": None, "later": False}
    try:
        lineup = scheduler.Lineup(K.schedule_cfg())
    except Exception as exc:
        K.log("preview promo: no lineup (%s)" % exc)
        lineup = None
    best = None
    for c in (lineup.channels if lineup else []):
        try:
            sc = lineup.schedule(c, ensure=False)          # never builds anything
        except Exception:
            continue
        for b in sc.blocks_between(now, now + 24 * 3600):
            if b["s"] > now and b.get("k") == "show" and b["t"].lower() == title.lower():
                if best is None or b["s"] < best[0]["s"]:
                    best = (b, c, sc)
                break
    if best:
        b, c, sc = best
        path = ""
        for e in sc.data["entries"]:
            if b["s"] <= e["s"] < b["e"] and e.get("k") == "show" and e.get("p"):
                path = e["p"]
                break
        out.update(path=path, pt=b["s"], ch=c, later=b is not sc.next_block(now))
    else:
        home = ((lineup.assignment if lineup else None) or {}).get("home", {}).get(title.lower())
        ch = next((c for c in (lineup.channels if lineup else []) if c["id"] == home), None)
        out.update(path=_first_episode(tvshowid), pt=scheduler.ceil_slot(now + 60, 1800), ch=ch)   # "next", half past
    return out


def card_for_show(tvshowid, now=None):
    """(window properties, music path, title) of a show's promo card."""
    now = now or time.time()
    t = target(tvshowid, now)
    inf = promos.info(t["path"], t["title"])
    ch = t["ch"]
    name = stations.brand(ch, t["pt"])["name"] if ch else ""      # its branding at that hour
    props = promos.card(inf, t["title"], t["pt"], now, ch, name, t["later"])
    logo = ""
    if ch and K.setting_bool("logo_banner", True):
        logo = stations.brand(ch, now)["logo"] or logos.logo_for(ch) or ""
    crt = K.setting_int("crt_mode", 0)
    # like the TV: a logo not yet in the texture cache gives a title-only card; it
    # loads in the background meanwhile, so the next preview of this show has it
    preload = "" if props.get("promo_logo") else (inf.get("logo") or "")
    props.update(banner_logo=logo, crt=str(crt) if crt in (1, 2) else "", mode="promo", promo_preload=preload)
    return props, promos.music(inf), t["title"]


class PreviewWindow(xbmcgui.WindowXML):
    """The TV window's own layout, showing just the promo for its length."""
    props = None
    music = ""
    done = False
    theme = None

    def onInit(self):
        self.player = xbmc.Player()
        self.theme = promos.ThemeAudio(self.player)
        self.setProperty("mode", "")
        promos.apply_card(self, self.props or {})
        self.setProperty("mode", "promo")
        self.end = time.time() + promos.PROMO_LEN
        if self.music:
            self.theme.start(self.music, self.end)
        threading.Thread(target=self._run, name="cablebox42-preview").start()

    def _run(self):
        mon = xbmc.Monitor()
        while not self.done and not mon.abortRequested():
            now = time.time()
            if self.theme.tick(now) or now >= self.end:
                break
            mon.waitForAbort(0.1)
        self.finish()

    def finish(self):
        if self.done:
            return
        self.done = True
        if self.theme is not None:
            self.theme.stop()
        self.close()

    def onAction(self, action):
        aid = action.getId()
        if aid in (10, 92, 13, 7):                     # Back, Stop or OK: end the preview
            self.finish()


def run(tvshowid=None):
    if xbmcgui.Window(10000).getProperty("cablebox42.running"):
        xbmcgui.Dialog().ok(_("Preview promo"), _("Turn CableBox's TV off first"))
        return
    if tvshowid is None:
        tvshowid = pick_show()
        if tvshowid is None:
            return
    player = xbmc.Player()
    if player.isPlaying():
        if not xbmcgui.Dialog().yesno(_("Preview promo"), _("Stop what's playing to show the preview?")):
            return
        player.stop()
        xbmc.sleep(300)
    try:
        props, music, title = card_for_show(tvshowid)
    except Exception as exc:
        K.log_err("preview promo: %s" % exc)
        xbmcgui.Dialog().ok(_("Preview promo"), _("Couldn't make this show's promo (see the Kodi log)"))
        return
    K.log("Preview promo: %s (%s)" % (title, music or "silent"), xbmc.LOGINFO)
    win = PreviewWindow("script-cablebox42-tv.xml", K.ADDON_PATH, "Default", "1080i")
    win.props, win.music = props, music
    win.doModal()
    win.finish()
    del win
