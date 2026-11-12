"""Background helper (called from service.py): optional start-on-boot, and
keeps schedules topped up so tuning and the guide are instant."""
import os
import time

import xbmc
import xbmcgui

from . import kodiutil as K


TOOL_BUSY = "script.cablebox42.tool"     # manager.TOOL_BUSY (the menus aren't imported up front)


LIBRARY_SETTLE = 30         # s after the last library scan/clean before a refresh


class Monitor(xbmc.Monitor):
    """Notes when Kodi's video library was scanned or cleaned (start-up scans and
    add-ons scanning on CoreELEC come in bursts: one refresh after the last)."""
    library_at = 0

    def onScanFinished(self, library):
        if library == "video":
            self.library_at = time.time()

    def onCleanFinished(self, library):
        if library == "video":
            self.library_at = time.time()


def run():
    monitor = Monitor()
    home = xbmcgui.Window(10000)

    def tv_running():
        return home.getProperty("cablebox42.running") == "1"

    def topup():
        if not os.path.exists(K.CHANNELS_FILE):
            return
        from . import scheduler, library
        lineup = scheduler.Lineup(K.schedule_cfg())
        lineup.ensure_all(abort=lambda: monitor.abortRequested() or tv_running())
        library.durations().save()

    def extras():
        # movie Extras folders: listed and measured only here, while the TV is off
        from . import library
        library.extras_refresh(abort=lambda: monitor.abortRequested() or tv_running())

    def music_videos():
        # Boombox: length, frame rate, audio and tags of music videos not read yet
        from . import library
        library.musicvideos_refresh(abort=lambda: monitor.abortRequested() or tv_running(), recheck=True)

    K.ensure_dirs()
    try:
        from . import progress
        progress.repair_pending()            # resume points a crash/power cut left changed
    except Exception as exc:
        K.log_err("progress repair failed: %s" % exc)
    try:
        from . import captions
        captions.restore_leftovers()         # a Kodi setting the subtitle search left changed
    except Exception as exc:
        K.log_err("captions repair failed: %s" % exc)
    for key in ("weather_source", "weather_units"):  # 1.1 stored text, 1.3 uses numbers
        if not K.ADDON.getSetting(key).isdigit():
            K.set_setting(key, "0")
    if os.path.exists(K.CHANNELS_FILE) and not home.getProperty(TOOL_BUSY):
        # a new build of the add-on: breaks planned by the old one take the new
        # layout from each channel's next programme (keep my place; what's on air stays)
        try:
            from . import manager
            manager.refresh_if_changed(clips=False, quiet=True)
        except Exception as exc:
            K.log_err("refresh after an update failed: %s" % exc)
    if K.setting_bool("autostart", False) and os.path.exists(K.CHANNELS_FILE):
        # wait for the home screen, then switch the TV on
        # Only right after Kodi starts, and never once the viewer has started
        # watching something else (otherwise stopping that video would land
        # them in CableBox).
        for _tick in range(60):
            if monitor.waitForAbort(1):
                return
            if xbmc.getCondVisibility("Player.HasMedia"):
                break
            if xbmc.getCondVisibility("Window.IsActive(home)") and \
                    not xbmc.getCondVisibility("System.HasModalDialog"):
                xbmc.executebuiltin("RunScript(script.cablebox42,watch)")
                break
    if monitor.waitForAbort(90):
        return
    from . import progress
    was_on = tv_running()
    idle = 0
    tick = 0
    while not monitor.abortRequested():
        tick += 1
        on = tv_running()
        if was_on and not on:
            # TV just switched off: confirm every resume point is back (twice,
            # in case Kodi was still writing when the TV closed)
            for wait in (10, 60):
                if monitor.waitForAbort(wait):
                    return
                progress.repair_pending()
        was_on = on
        if tick % 3 == 0 and not on and not home.getProperty(TOOL_BUSY) and \
                not home.getProperty("cablebox42.main_menu"):
            # settings changed from Kodi's own add-on settings (the CableBox menu and
            # its tools refresh on their own): apply them, never while the TV is on
            try:
                from . import manager
                manager.refresh_if_changed(clips=False, quiet=True)
            except Exception as exc:
                K.log_err("refresh after a settings change failed: %s" % exc)
        if monitor.library_at and time.time() - monitor.library_at >= LIBRARY_SETTLE \
                and not home.getProperty(TOOL_BUSY):
            # the library changed: new episodes, shows, movies, files gone.  Works
            # with the TV on too: a refresh never touches what's on air
            monitor.library_at = 0
            try:
                from . import manager
                manager.refresh_if_changed(clips=False, quiet=True, lib=True)
            except Exception as exc:
                K.log_err("refresh after a library change failed: %s" % exc)
        if not on and idle <= 0:
            try:
                progress.repair_pending()
                topup()
            except Exception as exc:
                K.log_err("schedule top-up failed: %s" % exc)
            try:
                music_videos()
            except Exception as exc:
                K.log_err("music video scan failed: %s" % exc)
            try:
                extras()
            except Exception as exc:
                K.log_err("extras scan failed: %s" % exc)
            idle = 20 * 60
        if monitor.waitForAbort(5):
            break
        idle -= 5
