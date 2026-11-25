"""Promo audio gate, Step 1 (briefs/promo-audio-n2-test.md): plain Kodi, no CableBox.

    python .claude/tools/n2/promo_step1.py [CASE...]      (cases: ac3 truehd dtshd ad; default all)

Each case: Kodi's video playlist in memory = episode A, a middle item (theme.mp3, or a stereo
commercial), episode B.  Opens A at 0 (also DTS: never at an offset), seeks to 20 s before its end,
lets it run into the middle item and on into B, 15 s of B, then stops.  Polls every 0.5 s (player,
file, time, window) and writes the transitions plus kodi.log's audio lines for that window to
n2/logs/promo-audio/step1-CASE.txt.  Changes no setting; nothing is written on the N2."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import n2  # noqa: E402

TV = "/var/media/Elements/Kodi/TV Shows/"
HP, FP = TV + "Human Planet (2011)/", TV + "Frozen Planet (2011)/"
LAB = "/var/media/Elements/Kodi/Movies/Labyrinth (1986)/Labyrinth (1986).SDR.mkv"
AD = "/var/media/Elements/Kodi/Commercials/9 Lives Crunchy Cat Food 1990 Commercial [AxQe_sE83_4].mp4"
CASES = {
    "ac3": [HP + "Human Planet (2011) S01E01.mkv", HP + "theme.mp3", HP + "Human Planet (2011) S01E02.mkv"],
    "truehd": [LAB, HP + "theme.mp3", LAB],
    "dtshd": [FP + "Frozen Planet (2011) S01E01.mkv", FP + "theme.mp3", FP + "Frozen Planet (2011) S01E02.mkv"],
    "ad": [HP + "Human Planet (2011) S01E01.mkv", AD, HP + "Human Planet (2011) S01E02.mkv"],
}
OUT = os.path.join(n2.ROOT, "logs", "promo-audio")


def secs(t):
    return t["hours"] * 3600 + t["minutes"] * 60 + t["seconds"] + t.get("milliseconds", 0) / 1000.0


def hms(s):
    s = max(0, int(s))
    return {"hours": s // 3600, "minutes": s // 60 % 60, "seconds": s % 60, "milliseconds": 0}


def run(case):
    items = CASES[case]
    lines = []

    def say(s):
        print(s, flush=True)
        lines.append(s)
    say("== %s  %s" % (case, time.strftime("%H:%M:%S")))
    for i, f in enumerate(items):
        say("   item %d: %s" % (i, os.path.basename(f)))
    since = time.strftime("%H:%M:%S")
    n2.rpc("Playlist.Clear", {"playlistid": 1})
    n2.rpc("Playlist.Add", {"playlistid": 1, "item": [{"file": f} for f in items]})
    t0 = time.time()
    n2.rpc("Player.Open", {"item": {"playlistid": 1, "position": 0}})
    # wait for A to play, then jump to 20 s before its end
    total = 0
    for _ in range(60):
        time.sleep(0.5)
        try:
            p = n2.rpc("Player.GetProperties", {"playerid": 1, "properties": ["time", "totaltime", "position"]})
            total = secs(p["totaltime"])
            if total > 0 and secs(p["time"]) > 1:
                break
        except Exception:
            pass
    say("%6.1f  A playing, length %.0f s; seek to %.0f s" % (time.time() - t0, total, total - 20))
    n2.rpc("Player.Seek", {"playerid": 1, "value": {"time": hms(total - 20)}})
    last, b_at, seen_mid = None, None, False
    while time.time() - t0 < 240:
        time.sleep(0.5)
        try:
            pl = n2.rpc("Player.GetActivePlayers")
            lab = n2.labels("Player.Filenameandpath", "Player.Time", "System.CurrentWindow", "VideoPlayer.AudioCodec",
                            "MusicPlayer.Codec", "System.FPS")
        except Exception as exc:
            say("%6.1f  Kodi not answering (%s)" % (time.time() - t0, exc))
            continue
        cur = (os.path.basename(lab["Player.Filenameandpath"]), lab["System.CurrentWindow"],
               ",".join(p["type"] for p in pl) or "none")
        if cur != last:
            say("%6.1f  %-45s window=%-22s player=%-6s audio=%s/%s time=%s fps=%s" % (
                time.time() - t0, cur[0][:45], cur[1], cur[2], lab["VideoPlayer.AudioCodec"], lab["MusicPlayer.Codec"],
                lab["Player.Time"], lab["System.FPS"]))
            last = cur
        if cur[0] == os.path.basename(items[1]):
            seen_mid = True
        if seen_mid and cur[0] == os.path.basename(items[2]) and b_at is None:
            b_at = time.time()              # B (the same file as A for TrueHD): after the middle item
        if b_at and time.time() - b_at > 15:
            break
    n2.rpc("Player.Stop", {"playerid": 1})
    say("%6.1f  stopped" % (time.time() - t0))
    time.sleep(2)
    log = n2.read_log(None)
    keep = [l for l in log.splitlines() if l[11:19] >= since and any(
        k in l for k in ("CAESinkALSA", "ActiveAE", "Unable to open", "SyncDTS", "SyncAC3", "SyncTrueHD",
                         "Visualisation", "visualisation", "OnPlayBack", "Display resolution", "CVideoPlayer::OpenFile"))]
    say("-- kodi.log audio / player lines since %s: %d" % (since, len(keep)))
    for l in keep:
        say("   " + l[:220])
    say("-- 'Unable to open the requested channel layout': %d" % sum("requested channel layout" in l for l in keep))
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "step1-%s.txt" % case), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    for c in sys.argv[1:] or ["ac3", "truehd", "dtshd", "ad"]:
        run(c)
        time.sleep(5)
