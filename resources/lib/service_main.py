"""Background helper (called from service.py): optional start-on-boot, and
keeps schedules topped up so tuning and the guide are instant."""
import os

import xbmc
import xbmcgui

from . import kodiutil as K


def run():
    monitor = xbmc.Monitor()
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

    K.ensure_dirs()
    for key in ("weather_source", "weather_units"):  # 1.1 stored text, 1.3 uses numbers
        if not K.ADDON.getSetting(key).isdigit():
            K.set_setting(key, "0")
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
    while not monitor.abortRequested():
        if not tv_running():
            try:
                topup()
            except Exception as exc:
                K.log_err("schedule top-up failed: %s" % exc)
        if monitor.waitForAbort(20 * 60):
            break
