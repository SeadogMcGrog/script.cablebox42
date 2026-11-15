#!/usr/bin/env python3
"""Turn make_jingle.py's stereo OGG jingles into the WAVs the add-on ships:
mono, 22.05 kHz, 16-bit (the Kodi repository checker refuses .ogg), at the same
loudness as the stereo original (EBU R128 integrated, measured after the downmix:
a plain L+R downmix comes out about 3 dB quieter).  Two passes: the gain the
downmix lost, then a trim to the target measured on the WAV itself.  A jingle
whose peaks would go above -1 dBTP gets a peak limiter (ceiling -1.5 dB) instead
of clipping; the others are left untouched apart from the gain.

    python3 tools/retro-ads/to_wav.py OGG_DIR [OUT_DIR]

OUT_DIR defaults to resources/media/jingles.  Needs ffmpeg.
"""
import glob
import os
import re
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOWNMIX = "pan=mono|c0=0.5*c0+0.5*c1"
PEAK_MAX = -1.0
LIMIT = -1.5           # limiter ceiling (sample peak), only where the gain would clip


def measure(path, pre=""):
    """(integrated LUFS, true peak dBTP) of path after the filter `pre`."""
    chain = (pre + "," if pre else "") + "ebur128=peak=true"
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", chain, "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    summary = out[out.rindex("Summary:"):]
    lufs = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summary).group(1))
    peak = float(re.search(r"True peak:\s+Peak:\s+(-?[\d.]+|-inf) dBFS", summary).group(1))
    return lufs, peak


def main():
    src = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(REPO, "resources", "media", "jingles")
    os.makedirs(out_dir, exist_ok=True)
    bad = 0
    for ogg in sorted(glob.glob(os.path.join(src, "jingle_*.ogg"))):
        target, _peak = measure(ogg)
        mono, mpeak = measure(ogg, DOWNMIX)
        gain = target - mono
        limit = mpeak + gain > PEAK_MAX
        wav = os.path.join(out_dir, os.path.basename(ogg)[:-4] + ".wav")
        for _pass in range(3):
            chain = "%s,volume=%.2fdB" % (DOWNMIX, gain)
            if limit:
                chain += ",alimiter=limit=%.4f:attack=1:release=50:level=disabled" % (10 ** (LIMIT / 20.0))
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", ogg, "-af", chain,
                            "-ar", "22050", "-ac", "1", "-c:a", "pcm_s16le", "-map_metadata", "-1",
                            "-fflags", "+bitexact", wav], check=True)
            got, gpeak = measure(wav)
            if abs(target - got) < 0.15:
                break
            gain += target - got
        if gpeak > PEAK_MAX or abs(target - got) > 0.3:
            print("FAIL %s: %.1f LUFS (wanted %.1f), peak %.1f dBTP" % (os.path.basename(wav), got, target, gpeak))
            bad += 1
            continue
        print("%-18s stereo %.1f LUFS -> mono %.1f LUFS (+%.1f dB%s), peak %.1f dBTP, %d KB"
              % (os.path.basename(wav), target, got, gain, ", limited" if limit else "", gpeak,
                 os.path.getsize(wav) // 1024))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
