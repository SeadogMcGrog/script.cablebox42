"""Music channels, Step 0 (briefs/music-channels.md): a test path, not a feature.

Plays a short queue of library songs through the TV window's own player (Kodi's
music playlist, windowed) under a placeholder screen, and logs what the N2 does:

1. Kodi's own music / visualisation screen: every change of the active window or
   dialog (polled every 50 ms).
2. Refresh-rate switches: every change of System.ScreenResolution, with what
   was happening (tune-in, song change...).
3. Audio output: each song's sample rate / codec / channels as Kodi plays it, and
   for every song change whether the player stopped in between.  Kodi's own audio
   lines (debug log: CActiveAESink / CAESinkALSA) show whether the output reopened.
4. Screensaver / dim: System.ScreenSaverActive and the idle time.
5. Gapless: for every song change the estimated silence (clock time against the
   player's own position) and whether Kodi ever reported "not playing".

Started with RunScript(script.cablebox42,watch,<video channel>,musictest): the TV
comes on on that channel and runs the script below by itself.  Every line starts
with "MUSICTEST" (Kodi log level INFO) so `grep MUSICTEST` finds them.

RunScript(script.cablebox42,musictest_kodi) plays the same queue in Kodi's own
music player (no CableBox window) with the same song changes, for comparison.

Read-only: library queries only; nothing is written but music_test.json (the
queue, in CableBox's own add-on data).  No audio setting is ever changed.
"""
import json
import os
import threading
import time

import xbmc
import xbmcgui
import xbmcvfs

from . import kodiutil as K
from .kodiutil import _

TAG = "MUSICTEST"
QUEUE_FILE = os.path.join(K.PROFILE, "music_test.json")
CH = {"id": "__musictest__", "number": 0, "name": "Music test", "type": "musictest",
      "logo": "none", "sources": []}

SEEK_AFTER = 4.0        # s after a song starts before it is skipped to its end
TAIL = 20.0             # s left of a song after that skip: the song change comes 20 s later
VIDEO_SECS = 45         # on the video channel before each tune to music
JOIN_SECS = 75          # the second, mid-song tune-in
HOLD_MIN, HOLD_MAX = 300, 900

WINDOWS = {10000: "Home", 12005: "FullscreenVideo", 12006: "Visualisation",
           10502: "Music", 10025: "Videos", 12900: "Screensaver", 10138: "BusyDialog",
           10160: "BusyDialogNoCancel", 10115: "SeekBar", 10120: "MusicOSD",
           12901: "VideoOSD", 10107: "Notification", 9999: "None", 10101: "Progress",
           10122: "VisualisationPresetList", 12009: "?"}

SETTINGS = ("audiooutput.audiodevice", "audiooutput.channels", "audiooutput.config",
            "audiooutput.samplerate", "audiooutput.stereoupmix", "audiooutput.processquality",
            "audiooutput.streamsilence", "audiooutput.streamnoise", "audiooutput.passthrough",
            "audiooutput.guisoundmode", "musicplayer.crossfade", "musicplayer.crossfadealbumtracks",
            "musicplayer.visualisation", "videoplayer.adjustrefreshrate",
            "videoplayer.pauseafterrefreshchange", "screensaver.mode", "screensaver.time",
            "screensaver.usemusicvisinstead", "screensaver.usedimonpause",
            "powermanagement.displaysoff")


def log(msg):
    xbmc.log("[%s] %s %s" % (K.ADDON_ID, TAG, msg), xbmc.LOGINFO)


def rpc_quiet(method, params=None):
    req = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        req["params"] = params
    try:
        resp = json.loads(xbmc.executeJSONRPC(json.dumps(req)))
    except Exception:
        return None
    if "error" in resp:
        return None
    return resp.get("result")


def log_settings():
    """What the box is set to (read only - never changed)."""
    vals = []
    for s in SETTINGS:
        r = rpc_quiet("Settings.GetSettingValue", {"setting": s})
        vals.append("%s=%s" % (s, r.get("value") if isinstance(r, dict) else "n/a"))
    log("settings: " + "  ".join(vals))
    log("kodi %s  platform %s  screen %s" % (xbmc.getInfoLabel("System.BuildVersion"),
                                             "CoreELEC/Linux" if xbmc.getCondVisibility("System.Platform.Linux") else
                                             "other", xbmc.getInfoLabel("System.ScreenResolution")))


def _ext(path):
    return os.path.splitext(path.split("?")[0])[1].lower().lstrip(".")


def _rate(s):
    try:
        return int(s.get("samplerate") or 0)
    except (TypeError, ValueError):
        return 0


def describe(s):
    artist = ", ".join(s.get("artist") or []) if isinstance(s.get("artist"), list) else (s.get("artist") or "")
    r = _rate(s)
    return "%s - %s [%s %s, %ss]" % (artist or "?", s.get("title") or os.path.basename(s["file"]),
                                     _ext(s["file"]).upper(), ("%.1f kHz" % (r / 1000.0)) if r else "rate ?",
                                     int(s.get("duration") or 0))


# ------------------------------------------------------------------ the queue
def build_queue():
    """[songs], n_scripted: the songs whose ends are reached by skipping (the
    song-change part), then fillers that play in full (screensaver part)."""
    props = ["file", "duration", "artist", "title", "album", "albumid", "track", "genre",
             "samplerate", "bitrate", "channels"]
    params = {"properties": props, "limits": {"start": 0, "end": 3000}, "sort": {"method": "random"}}
    res = rpc_quiet("AudioLibrary.GetSongs", params)
    if res is None:
        log("this Kodi has no samplerate/bitrate/channels song fields - picking without rates")
        params["properties"] = props[:8]
        res = rpc_quiet("AudioLibrary.GetSongs", params)
    songs = [s for s in (res or {}).get("songs", []) if s.get("file") and int(s.get("duration") or 0) >= 60]
    log("library: %d songs of 60 s or more looked at" % len(songs))
    if not songs:
        return [], 0
    used = set()

    def take(pred, why):
        for s in songs:
            if s["file"] not in used and pred(s) and xbmcvfs.exists(s["file"]):
                used.add(s["file"])
                s["why"] = why
                return s
        log("none found for: %s" % why)
        return None

    r441 = lambda s: _rate(s) == 44100
    r48 = lambda s: _rate(s) == 48000
    plan = [
        take(lambda s: r441(s) and _ext(s["file"]) == "mp3", "44.1 MP3"),
        take(lambda s: r441(s) and _ext(s["file"]) == "mp3", "44.1 MP3 again (same rate, same codec)"),
        take(lambda s: r441(s) and _ext(s["file"]) == "flac", "44.1 FLAC (same rate, codec change)"),
        take(r48, "48 kHz (rate change 44.1 -> 48)"),
        take(r48, "48 kHz again (same rate)"),
        take(lambda s: _rate(s) >= 88200 and _ext(s["file"]) == "flac", "88.2/96+ kHz FLAC (rate change up)"),
        take(r441, "44.1 kHz (rate change back down)"),
    ]
    queue = [s for s in plan if s]
    # an album's consecutive tracks for the gapless check, FLAC preferred
    albums = {}
    for s in songs:
        if s.get("albumid"):
            albums.setdefault(s["albumid"], []).append(s)
    order = sorted(albums, key=lambda a: (_ext(albums[a][0]["file"]) != "flac", -len(albums[a])))
    for aid in order[:40]:
        res = rpc_quiet("AudioLibrary.GetSongs", {"properties": params["properties"],
                                                  "filter": {"albumid": aid}, "sort": {"method": "track"}})
        tracks = [t for t in (res or {}).get("songs", []) if t.get("file") and t["file"] not in used]
        if len(tracks) >= 3 and all(xbmcvfs.exists(t["file"]) for t in tracks[:3]):
            for i, t in enumerate(tracks[:3]):
                t["why"] = "album run %d/3: %s (gapless?)" % (i + 1, t.get("album") or "")
                used.add(t["file"])
                queue.append(t)
            break
    else:
        log("no album with 3 tracks found for the gapless check")
    scripted = len(queue)
    # fillers that play in full: the screensaver part and the mid-song tune-in
    total = 0
    for s in songs:
        if total > HOLD_MAX + 900 or len(queue) > scripted + 40:
            break
        if s["file"] in used:
            continue
        used.add(s["file"])
        s["why"] = "filler (plays in full)"
        queue.append(s)
        total += int(s.get("duration") or 0)
    return queue, scripted


# ------------------------------------------------------------------ watching Kodi
class Watcher(xbmc.Player):
    """Kodi's player callbacks plus a 50 ms poll of windows, screen mode,
    screensaver and playback: one log line per change."""

    def __init__(self, label):
        xbmc.Player.__init__(self)
        self.label = label
        self.t0 = time.time()
        self.stop_ev = threading.Event()
        self.note = ""                 # what the test is doing now (in every line)
        self.stats = {"vis": 0, "fullscreen": 0, "res": [], "saver": 0, "changes": [], "stopped_gaps": 0}
        self.last = None               # (wall, file, pos, total) of the last good sample
        self.cur_file = None
        self.not_playing_since = None
        self.thread = threading.Thread(target=self.run, name="cablebox42-musictest-watch")

    def ts(self):
        return "%8.2f" % (time.time() - self.t0)

    def say(self, msg):
        log("%s t=%s [%s] %s" % (self.label, self.ts(), self.note or "-", msg))

    # callbacks (Kodi's thread)
    def onPlayBackStarted(self):
        self.say("cb onPlayBackStarted")

    def onAVStarted(self):
        self.say("cb onAVStarted %s" % self._file())

    def onAVChange(self):
        self.say("cb onAVChange")

    def onQueueNextItem(self):
        self.say("cb onQueueNextItem")

    def onPlayBackEnded(self):
        self.say("cb onPlayBackEnded")

    def onPlayBackStopped(self):
        self.say("cb onPlayBackStopped")

    def onPlayBackError(self):
        self.say("cb onPlayBackError")

    def onPlayBackSeek(self, time_ms, offset_ms):
        self.say("cb onPlayBackSeek to %.1f s" % (time_ms / 1000.0))

    def _file(self):
        try:
            return self.getPlayingFile() if self.isPlaying() else ""
        except Exception:
            return ""

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_ev.set()

    def run(self):
        mon = xbmc.Monitor()
        win = dlg = res = saver = None
        while not self.stop_ev.is_set() and not mon.abortRequested():
            now = time.time()
            try:
                w = xbmcgui.getCurrentWindowId()
                d = xbmcgui.getCurrentWindowDialogId()
                if w != win:
                    self.say("window %s -> %s (%s)" % (win, w, WINDOWS.get(w, "?")))
                    if w == 12006:
                        self.stats["vis"] += 1
                    if w == 12005 and not self.isPlayingVideo():
                        self.stats["fullscreen"] += 1
                    win = w
                if d != dlg:
                    self.say("dialog %s -> %s (%s)" % (dlg, d, WINDOWS.get(d, "?")))
                    dlg = d
                r = xbmc.getInfoLabel("System.ScreenResolution")
                if r != res:
                    if res is not None:
                        self.say("SCREEN MODE CHANGE %s -> %s" % (res, r))
                        self.stats["res"].append((self.note, res, r))
                    res = r
                sv = xbmc.getCondVisibility("System.ScreenSaverActive")
                if sv != saver:
                    self.say("screensaver %s (idle %s s)" % ("ON" if sv else "off",
                                                              xbmc.getInfoLabel("System.IdleTime")))
                    if sv:
                        self.stats["saver"] += 1
                    saver = sv
                self.playback(now)
            except Exception as exc:
                self.say("watch error: %s" % exc)
            self.stop_ev.wait(0.05)

    def playback(self, now):
        try:
            if self.isPlayingVideo():           # the video channel: song changes start afresh after it
                self.cur_file, self.last, self.not_playing_since = None, None, None
                return
        except Exception:
            pass
        try:
            playing = self.isPlayingAudio() and not self.isPlayingVideo()
            f = self.getPlayingFile() if playing else ""
            pos = self.getTime() if playing else 0.0
            total = self.getTotalTime() if playing else 0.0
        except Exception:
            playing, f, pos, total = False, "", 0.0, 0.0
        if not playing:
            if self.cur_file and self.not_playing_since is None:
                self.not_playing_since = now
            return
        if self.not_playing_since is not None:
            self.say("player was not playing for %.2f s" % (now - self.not_playing_since))
            self.stats["stopped_gaps"] += 1
            self.not_playing_since = None
        if f != self.cur_file:
            if pos <= 0.0:
                return                  # wait for the new song's first position
            gap = None
            if self.last and self.last[1] == self.cur_file and self.last[3] > 0:
                ended = self.last[0] + (self.last[3] - self.last[2])   # when the old song ran out
                began = now - pos                                       # when the new one started
                gap = began - ended
            prev = self.cur_file
            self.cur_file = f
            threading.Thread(target=self.song_info, args=(prev, f, gap), name="cablebox42-musictest-info").start()
        self.last = (now, f, pos, total)

    def song_info(self, prev, f, gap):
        """What Kodi decoded, read 1.5 s into the song (the labels fill a moment late)."""
        xbmc.sleep(1500)
        info = {k: xbmc.getInfoLabel(v) for k, v in (
            ("rate", "MusicPlayer.SampleRate"), ("codec", "MusicPlayer.Codec"),
            ("ch", "MusicPlayer.Channels"), ("bits", "MusicPlayer.BitsPerSample"),
            ("prate", "Player.Process(audiosamplerate)"), ("pch", "Player.Process(audiochannels)"),
            ("pdec", "Player.Process(audiodecoder)"))}
        self.stats["changes"].append((prev, f, gap, info))
        self.say("SONG %s  rate=%s kHz codec=%s ch=%s bits=%s | process: rate=%s ch=%s dec=%s | %s" % (
            os.path.basename(f), info["rate"], info["codec"], info["ch"], info["bits"],
            info["prate"], info["pch"], info["pdec"],
            ("est. silence %.2f s after %s" % (gap, os.path.basename(prev))) if gap is not None and prev
            else "first song"))

    def summary(self):
        s = self.stats
        log("%s ===== SUMMARY =====" % self.label)
        log("%s visualisation window seen %d times; Kodi full-screen (no video) %d times; screensaver on %d times; "
            "player stopped between songs %d times" % (self.label, s["vis"], s["fullscreen"], s["saver"],
                                                      s["stopped_gaps"]))
        for note, a, b in s["res"]:
            log("%s screen mode change during [%s]: %s -> %s" % (self.label, note, a, b))
        rows = s["changes"]
        for i in range(1, len(rows)):
            prev, f, gap, info = rows[i]
            pinfo = rows[i - 1][3]
            if not prev:
                log("%s tune-in: %s at %s kHz %s" % (self.label, os.path.basename(f), info["rate"], info["codec"]))
                continue
            log("%s change %d: %s kHz %s -> %s kHz %s  est. silence %s  (%s -> %s)" % (
                self.label, i, pinfo["rate"], pinfo["codec"], info["rate"], info["codec"],
                ("%.2f s" % gap) if gap is not None else "n/a", os.path.basename(prev), os.path.basename(f)))
        log("%s ===== END =====" % self.label)


# ------------------------------------------------------------------ in the TV window
class MusicTest(object):
    def __init__(self, tv):
        self.tv = tv
        self.queue = []
        self.scripted = 0
        self.video_ch = None
        self.plan = None           # ("pos", index, offset) for the next tune to the music channel
        self.epoch = time.time()   # after the script: tune-ins join on this clock
        self.pos = -1
        self.pos_at = 0
        self.seeked = set()
        self.pending = None        # (index, offset) to seek to once the song plays
        self.skip_ends = False
        self.status = ""
        self.watch = Watcher("TV")
        self.done = False

    # ---- the script (own thread)
    def start(self):
        t = threading.Thread(target=self.run, name="cablebox42-musictest")
        t.start()
        return t

    def wait(self, secs):
        end = time.time() + secs
        while time.time() < end:
            if self.tv.closing or self.tv.monitor.waitForAbort(0.25):
                return False
        return True

    def step(self, note):
        self.watch.note = note
        self.status = note
        log("STEP %s" % note)

    def run(self):
        log("===== Step 0 music test start =====")
        log_settings()
        self.watch.start()
        try:
            self.queue, self.scripted = build_queue()
            for i, s in enumerate(self.queue):
                log("queue %2d: %s  <- %s" % (i + 1, describe(s), s.get("why", "")))
            K.save_json(QUEUE_FILE, {"queue": self.queue, "scripted": self.scripted})
            if len(self.queue) < 3:
                log("not enough songs in the music library - test stopped")
                self.status = _("Music test: not enough songs in the music library")
                return
            # wait for the TV to be on a video
            for _i in range(240):
                if self.tv.closing:
                    return
                if self.tv.ch and not self.tv.power_on and self.tv.prop_mode == "video" and \
                        self.tv.player.isPlayingVideo():
                    break
                xbmc.sleep(250)
            self.video_ch = self.tv.ch
            fps = xbmc.getInfoLabel("Player.Process(videofps)")
            self.step(_("Music test: on video channel %s (%s fps)") % (self.video_ch.get("number"), fps))
            if not self.wait(VIDEO_SECS):
                return
            # 1: tune to music; the song changes, each song skipped to its last 20 s
            self.skip_ends = True
            self.plan = ("pos", 0, 0.0)
            self.step(_("Music test: tuning from video to music"))
            self.tv.tune(CH)
            self.step(_("Music test: song changes (each song skipped to its last 20 seconds)"))
            limit = time.time() + self.scripted * (SEEK_AFTER + TAIL + 20) + 120
            while self.pos < self.scripted and time.time() < limit:
                if not self.wait(0.5):
                    return
            self.skip_ends = False
            hold = self.hold_secs()
            self.step(_("Music test: full songs for %d minutes - press nothing") % max(1, hold // 60))
            if not self.wait(hold):
                return
            # 2: back to video
            self.step(_("Music test: tuning from music to video channel %s") % self.video_ch.get("number"))
            self.tv.tune(self.video_ch)
            if not self.wait(VIDEO_SECS):
                return
            # 3: music again, joining mid-song
            j = min(len(self.queue) - 1, self.scripted + 2)
            dur = float(self.queue[j].get("duration") or 120)
            self.plan = ("pos", j, round(dur * 0.4, 1))
            self.step(_("Music test: tuning from video to music, joining mid-song"))
            self.tv.tune(CH)
            if not self.wait(JOIN_SECS):
                return
            self.step(_("Music test: tuning from music to video channel %s") % self.video_ch.get("number"))
            self.tv.tune(self.video_ch)
            if not self.wait(30):
                return
            self.step(_("Music test done. Previous channel flips between music and video."))
            self.watch.summary()
            self.done = True
            self.epoch = time.time()
            # keep watching for the hand flips until the TV goes off
            while self.wait(5):
                pass
        finally:
            if not self.done:
                self.watch.summary()
            self.watch.stop()
            log("===== Step 0 music test end =====")

    def hold_secs(self):
        r = rpc_quiet("Settings.GetSettingValue", {"setting": "screensaver.time"})
        mins = int(r.get("value") or 0) if isinstance(r, dict) else 0
        return max(HOLD_MIN, min(HOLD_MAX, mins * 60 + 90))

    # ---- in the TV's loop (TV lock held)
    def tick(self, now):
        tv = self.tv
        if tv.cur_key != "musictest":
            tv.cur_key = "musictest"
            tv.cur_entry = {"k": "music", "s": now}
            tv.unqueue()
            tv.show_bug(False)
            tv.set_mode("musictest")
            self.play(now)
        self.follow(now)
        self.labels(now)

    def play(self, now):
        if not self.queue:
            return
        if self.plan:
            _k, idx, off = self.plan
            self.plan = None
        else:
            # after the script: the queue loops on the real clock from the end of the script
            total = sum(float(s.get("duration") or 0) for s in self.queue) or 1.0
            t = (now - self.epoch) % total
            idx = 0
            while t > float(self.queue[idx].get("duration") or 0):
                t -= float(self.queue[idx].get("duration") or 0)
                idx += 1
            off = round(t, 1)
        pl = xbmc.PlayList(getattr(xbmc, "PLAYLIST_MUSIC", 0))
        pl.clear()
        for s in self.queue:
            li = xbmcgui.ListItem(s.get("title") or "", path=s["file"])
            pl.add(s["file"], li)
            self.tv.our_files.add(s["file"])
        self.pos = -1
        self.seeked = set()
        self.pending = (idx, off) if off > 1 else None
        self.tv.play_token += 1
        self.tv.play_started_at = time.time()
        log("play music playlist from song %d at %.1f s (windowed)" % (idx + 1, off))
        self.tv.player.play(pl, windowed=True, startpos=idx)

    def follow(self, now):
        try:
            if not self.tv.player.isPlayingAudio():
                return
            p = xbmc.PlayList(getattr(xbmc, "PLAYLIST_MUSIC", 0)).getposition()
            t = self.tv.player.getTime()
            total = self.tv.player.getTotalTime()
        except Exception:
            return
        if p != self.pos:
            self.pos, self.pos_at = p, now
        if self.pending and self.pending[0] == p and t > 0.2:
            off = self.pending[1]
            self.pending = None
            log("seek to %.1f s (tune-in mid-song)" % off)
            self.tv.player.seekTime(off)
            self.seeked.add(p)
            return
        if self.skip_ends and p < self.scripted and p not in self.seeked and now - self.pos_at > SEEK_AFTER \
                and total > TAIL * 2 and t < total - TAIL * 2:
            self.seeked.add(p)
            log("skip song %d to its last %d s (%.1f -> %.1f); its song change follows ~%d s later" % (
                p + 1, TAIL, t, total - TAIL, TAIL))
            self.tv.player.seekTime(total - TAIL)

    def labels(self, now):
        tv = self.tv
        p = self.pos
        s = self.queue[p] if 0 <= p < len(self.queue) else None
        if s:
            artist = s.get("artist")
            tv.setProperty("mt_artist", ", ".join(artist) if isinstance(artist, list) else (artist or ""))
            tv.setProperty("mt_title", s.get("title") or os.path.basename(s["file"]))
            tv.setProperty("mt_album", s.get("album") or "")
            tv.setProperty("mt_why", "%d/%d  %s" % (p + 1, len(self.queue), s.get("why", "")))
        tv.setProperty("mt_tech", "%s kHz  %s  %s ch  %s bit" % (
            xbmc.getInfoLabel("MusicPlayer.SampleRate"), xbmc.getInfoLabel("MusicPlayer.Codec"),
            xbmc.getInfoLabel("MusicPlayer.Channels"), xbmc.getInfoLabel("MusicPlayer.BitsPerSample")))
        tv.setProperty("mt_status", self.status)


# ------------------------------------------------------------------ Kodi's own player, for comparison
def run_kodi_player():
    """The same song changes in Kodi's own music player (no CableBox window)."""
    data = K.load_json(QUEUE_FILE, {})
    queue, scripted = data.get("queue") or [], int(data.get("scripted") or 0)
    if not queue:
        xbmcgui.Dialog().notification("CableBox 42", _("Run the TV music test first"), xbmcgui.NOTIFICATION_INFO, 4000)
        return
    log("===== Kodi's own player comparison start =====")
    log_settings()
    w = Watcher("KODI")
    w.note = "Kodi's own player: song changes"
    w.start()
    pl = xbmc.PlayList(getattr(xbmc, "PLAYLIST_MUSIC", 0))
    pl.clear()
    for s in queue[:scripted + 1]:
        pl.add(s["file"])
    player = xbmc.Player()
    player.play(pl)                     # as Kodi plays music: its own full-screen screen
    mon = xbmc.Monitor()
    seeked, pos, pos_at = set(), -1, time.time()
    started = time.time()
    while not mon.waitForAbort(0.25):
        now = time.time()
        try:
            if not player.isPlayingAudio():
                if now - started > 15:
                    break
                continue
            p = pl.getposition()
            t, total = player.getTime(), player.getTotalTime()
        except Exception:
            continue
        if p != pos:
            pos, pos_at = p, now
        if p >= scripted:
            if now - pos_at > 10:
                break
            continue
        if p not in seeked and now - pos_at > SEEK_AFTER and total > TAIL * 2 and t < total - TAIL * 2:
            seeked.add(p)
            log("KODI skip song %d to its last %d s" % (p + 1, TAIL))
            player.seekTime(total - TAIL)
    try:
        player.stop()
    except Exception:
        pass
    xbmc.sleep(1000)
    w.summary()
    w.stop()
    log("===== Kodi's own player comparison end =====")

