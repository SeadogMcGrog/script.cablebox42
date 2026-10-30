"""Leave the viewer's watch progress exactly as it was.

Kodi saves a resume point (and may bump the play count / last-played date)
whenever a video stops - including every show CableBox airs and every
channel you surf past.  We snapshot a file's state before CableBox first plays
it and put it back after CableBox moves on.  Pending restores are written to
disk, so a crash or power cut is repaired at the next start.
"""
import os
import threading

from . import kodiutil as K

PENDING_FILE = os.path.join(K.PROFILE, "progress_restore.json")
_lock = threading.Lock()


def enabled():
    return K.setting_bool("keep_progress", True)


def snapshot(path):
    """Current resume/playcount/lastplayed of a file (library item or plain file)."""
    res = K.rpc("Files.GetFileDetails", {"file": path, "media": "video",
                                         "properties": ["resume", "playcount", "lastplayed"]})
    d = res.get("filedetails") or {}
    if not d:
        return None
    r = d.get("resume") or {}
    return {"path": path, "type": d.get("type") or "", "id": d.get("id"),
            "position": float(r.get("position") or 0), "total": float(r.get("total") or 0),
            "playcount": int(d.get("playcount") or 0), "lastplayed": d.get("lastplayed") or ""}


def restore(snap):
    resume = {"position": snap["position"], "total": snap["total"]}
    common = {"playcount": snap["playcount"], "lastplayed": snap["lastplayed"], "resume": resume}
    kind, item = snap.get("type"), snap.get("id")
    if kind == "episode" and item is not None:
        params = dict(common, episodeid=item)
        K.rpc("VideoLibrary.SetEpisodeDetails", params)
    elif kind == "movie" and item is not None:
        params = dict(common, movieid=item)
        K.rpc("VideoLibrary.SetMovieDetails", params)
    elif kind == "musicvideo" and item is not None:
        params = dict(common, musicvideoid=item)
        K.rpc("VideoLibrary.SetMusicVideoDetails", params)
    else:
        params = dict(common, file=snap["path"], media="video")
        K.rpc("Files.SetFileDetails", params)


class Guard(object):
    """Used by the TV: remember() before playing, release() once playback moved on."""

    def __init__(self):
        self.snaps = {}            # path -> original state (first time seen this session)
        self.pending = {}          # path -> snap still to restore
        self._load_pending()

    def _load_pending(self):
        for snap in K.load_json(PENDING_FILE, []):
            self.snaps.setdefault(snap["path"], snap)
            self.pending[snap["path"]] = snap

    def _save_pending(self):
        try:
            K.save_json(PENDING_FILE, list(self.pending.values()))
        except Exception as exc:
            K.log_err("progress save: %s" % exc)

    def remember(self, path):
        if not enabled() or not path:
            return
        with _lock:
            if path not in self.snaps:
                snap = snapshot(path)
                if snap is None:
                    return
                self.snaps[path] = snap
            self.pending[path] = self.snaps[path]
            self._save_pending()

    def release(self, keep=None, delay=2.5):
        """Restore everything pending except `keep` (the file playing now), after
        Kodi has had time to write its own resume point."""
        with _lock:
            todo = [s for p, s in self.pending.items() if p != keep]
        if not todo:
            return
        t = threading.Timer(delay, self._restore, [todo])
        t.daemon = True
        t.start()

    def release_now(self):
        with _lock:
            todo = list(self.pending.values())
        self._restore(todo)

    def _restore(self, todo):
        for snap in todo:
            try:
                restore(snap)
            except Exception as exc:
                K.log_err("progress restore %s: %s" % (snap.get("path"), exc))
        with _lock:
            for snap in todo:
                self.pending.pop(snap["path"], None)
            self._save_pending()


def repair_pending():
    """At start-up: restore anything a crash left behind."""
    todo = K.load_json(PENDING_FILE, [])
    if not todo:
        return
    for snap in todo:
        try:
            restore(snap)
        except Exception as exc:
            K.log_err("progress repair %s: %s" % (snap.get("path"), exc))
    K.save_json(PENDING_FILE, [])


# ------------------------------------------------------------------ clean-up tool
def in_progress_items():
    """[(label, kind, id)] for every movie/episode Kodi lists as in progress."""
    flt = {"field": "inprogress", "operator": "true", "value": ""}
    out = []
    res = K.rpc("VideoLibrary.GetMovies", {"filter": flt, "properties": ["title", "year", "resume"]})
    for m in res.get("movies", []):
        out.append(("%s (%s)" % (m.get("title", ""), m.get("year", "")), "movie", m["movieid"], m.get("resume") or {}))
    res = K.rpc("VideoLibrary.GetEpisodes", {"filter": flt,
                                            "properties": ["showtitle", "season", "episode", "title", "resume"]})
    for e in res.get("episodes", []):
        out.append(("%s S%02dE%02d %s" % (e.get("showtitle", ""), e.get("season", 0), e.get("episode", 0),
                                          e.get("title", "")), "episode", e["episodeid"], e.get("resume") or {}))
    return out


def clear_resume(kind, item):
    resume = {"position": 0, "total": 0}
    if kind == "movie":
        K.rpc("VideoLibrary.SetMovieDetails", {"movieid": item, "resume": resume})
    else:
        K.rpc("VideoLibrary.SetEpisodeDetails", {"episodeid": item, "resume": resume})
