#!/usr/bin/env python3
"""Synthesize original retro ad jingle beds for CableBox 42. No samples: pure tones and noise.

Usage:  python3 make_jingle.py OUTDIR [preset ...]
Presets: local (Big Earl's, the approved one), pitch, kids, psa, video. Default: all.
Writes OUTDIR/jingle_<preset>.ogg at about -16 LUFS (needs ffmpeg with libvorbis).
"""
import os, subprocess, sys, wave, re
import numpy as np

SR = 44100
TARGET_LUFS = -16.0
RNG = np.random.default_rng(3)


def N(m):  # midi note -> Hz
    return 440 * 2 ** ((m - 69) / 12)


class Mix:
    def __init__(self, seconds):
        self.L = np.zeros(int(SR * seconds)); self.R = np.zeros_like(self.L)

    def add(self, sig, start, pan=0.0, gain=1.0):
        i = int(start * SR)
        j = min(len(self.L), i + len(sig))
        if j <= i:
            return
        sig = sig[: j - i] * gain
        self.L[i:j] += sig * np.sqrt(0.5 * (1 - pan)); self.R[i:j] += sig * np.sqrt(0.5 * (1 + pan))

    def stereo(self):
        return np.stack([self.L, self.R], 1)


def tt(dur):
    n = int(dur * SR)
    return n, np.arange(n) / SR


def env(n, a=0.005, d=0.1, s=0.6, r=0.08, hold=None):
    t = np.arange(n) / SR
    hold = hold if hold is not None else n / SR - r
    e = np.where(t < a, t / a, np.where(t < a + d, 1 - (1 - s) * (t - a) / d, s))
    rel = np.clip((t - hold) / r, 0, 1)
    return e * (1 - rel)


# ---------------- instruments ----------------
def organ(f, dur):
    n, t = tt(dur)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 6.2 * t)
    s = sum(a * np.sin(2 * np.pi * f * h * vib * t) for h, a in ((0.5, .5), (1, 1), (2, .6), (3, .35), (4, .25), (6, .12)))
    return s * env(n, .01, .05, .8, .04) * 0.11


def bass(f, dur):
    n, t = tt(dur)
    s = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.12 * np.sign(np.sin(2 * np.pi * f * t))
    return s * env(n, .004, .12, .55, .05) * 0.33


def bell(f, dur):
    n, t = tt(dur)
    s = np.sin(2 * np.pi * f * t + 1.8 * np.sin(2 * np.pi * f * 3.5 * t) * np.exp(-t * 6))
    s += 0.3 * np.sign(np.sin(2 * np.pi * f * t)) * np.exp(-t * 14)
    return s * np.exp(-t * 3.2) * env(n, .002, .01, 1, .05) * 0.22


def kick():
    n, t = tt(.3)
    f = 50 + 110 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11) * 0.55


def snare():
    n, t = tt(.22)
    nz = RNG.standard_normal(n); nz = nz - np.convolve(nz, np.ones(6) / 6, "same")
    return (nz * 0.55 * np.exp(-t * 18) + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25) * 0.4) * 0.45


def hat(open_=False):
    n, t = tt(.25 if open_ else .05)
    nz = RNG.standard_normal(n); nz = nz - np.convolve(nz, np.ones(3) / 3, "same")
    return nz * np.exp(-t * (9 if open_ else 70)) * 0.16


def cymbal(length=2.6):
    n, t = tt(length)
    nz = RNG.standard_normal(n); nz = nz - np.convolve(nz, np.ones(4) / 4, "same")
    return nz * np.exp(-t * 1.6) * 0.18


def clap():
    n, t = tt(.25)
    nz = RNG.standard_normal(n); nz = nz - np.convolve(nz, np.ones(8) / 8, "same")
    e = np.zeros(n)
    for k, d in enumerate((0, .011, .023)):
        e += np.where(t >= d, np.exp(-(t - d) * (60 if k < 2 else 16)), 0)
    return nz * e * 0.32


def brass(f, dur, bright=1.0):
    """Synth brass: saw-like stack whose upper harmonics open and close."""
    n, t = tt(dur)
    b = np.minimum(t / 0.06, 1) * np.exp(-t * 1.2) * bright + 0.25
    vib = 1 + 0.003 * np.sin(2 * np.pi * 5.5 * t) * np.minimum(t / .3, 1)
    s = np.zeros(n)
    for h in range(1, 14):
        if f * h > 9000:
            break
        s += np.sin(2 * np.pi * f * h * vib * t) / h * np.exp(-h / (1.5 + 9 * b))
    return s * env(n, .03, .1, .8, .08) * 0.16


def pad(f, dur):
    n, t = tt(dur)
    s = np.zeros(n)
    for det in (-0.006, 0, 0.007):
        for h in range(1, 7):
            s += np.sin(2 * np.pi * f * (1 + det) * h * t + h) / h ** 1.6
    return s * env(n, .45, .3, .85, .6) * 0.07


def lead(f, dur):
    """Bright square-ish lead with delayed vibrato."""
    n, t = tt(dur)
    vib = 1 + 0.006 * np.sin(2 * np.pi * 6 * t) * np.clip((t - .12) / .1, 0, 1)
    s = sum(np.sin(2 * np.pi * f * h * vib * t) / h for h in (1, 3, 5, 7, 9))
    return s * env(n, .004, .08, .7, .05) * 0.12


def xylo(f, dur=.5):
    n, t = tt(dur)
    s = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 3.93 * t) * np.exp(-t * 30) + 0.12 * np.sin(2 * np.pi * f * 9.2 * t) * np.exp(-t * 60)
    return s * np.exp(-t * 9) * env(n, .001, .01, 1, .03) * 0.3


def pluck_bass(f, dur):
    n, t = tt(dur)
    s = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t) * np.exp(-t * 12)
    return s * np.exp(-t * 6) * env(n, .003, .02, 1, .04) * 0.4


def boing(f0=220, dur=.45):
    n, t = tt(dur)
    f = f0 * (1 + 0.6 * np.exp(-t * 6) * np.sin(2 * np.pi * 9 * t))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4) * env(n, .003, .01, 1, .05) * 0.3


def slide_whistle(f0, f1, dur):
    n, t = tt(dur)
    f = f0 * (f1 / f0) ** (t / dur) * (1 + 0.012 * np.sin(2 * np.pi * 7 * t))
    nz = RNG.standard_normal(n) * 0.04
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) + nz) * env(n, .03, .05, .9, .05) * 0.2


def triangle_hit(dur=2.0):
    n, t = tt(dur)
    s = np.sin(2 * np.pi * 2600 * t) + 0.6 * np.sin(2 * np.pi * 5450 * t) + 0.3 * np.sin(2 * np.pi * 7900 * t)
    return s * np.exp(-t * 2.5) * env(n, .001, .01, 1, .1) * 0.05


def timpani(f, dur=2.5, vel=1.0):
    n, t = tt(dur)
    fr = f * (1 + 0.06 * np.exp(-t * 8))
    s = np.sin(2 * np.pi * np.cumsum(fr) / SR) + 0.4 * np.sin(2 * np.pi * np.cumsum(fr * 1.5) / SR) * np.exp(-t * 3)
    nz = RNG.standard_normal(n); nz = np.convolve(nz, np.ones(30) / 30, "same")
    return (s * np.exp(-t * 2.2) + nz * np.exp(-t * 30) * 0.8) * 0.4 * vel


def zip_up(dur):
    n, t = tt(dur)
    f = 300 * (8 ** (t / dur))
    s = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.5 + np.sin(2 * np.pi * np.cumsum(f) / SR)
    return s * (t / dur) ** 1.5 * 0.08


# ---------------- presets ----------------
def preset_local():
    """Big Earl's: bouncy organ, bass, bell hook, ta-da. (Approved 2026-11-13.)"""
    B = 60 / 132
    m = Mix(16 * B + 3.2)
    prog = [(48, [60, 64, 67]), (53, [60, 65, 69]), (55, [59, 62, 67])]
    for bar, (root, ch) in enumerate(prog):
        t0 = bar * 4 * B
        for beat in range(4):
            tb = t0 + beat * B
            m.add(bass(N(root if beat % 2 == 0 else root + 7), B * 0.8), tb, -0.1)
            for n_ in ch:
                m.add(organ(N(n_), B * 0.38), tb + B / 2, 0.25)
            m.add(kick() if beat % 2 == 0 else snare(), tb, 0.0)
            m.add(hat(), tb + B / 2, 0.35); m.add(hat(), tb, 0.35, 0.6)
    mel = [(72, 0, .5), (76, .5, .5), (79, 1, 1), (76, 2, .5), (79, 2.5, 1.5),
           (77, 4, .5), (81, 4.5, .5), (84, 5, 1), (81, 6, .5), (77, 6.5, 1.5),
           (79, 8, .5), (77, 8.5, .5), (76, 9, .5), (74, 9.5, .5), (71, 10, .5), (74, 10.5, .5), (79, 11, 1)]
    for n_, s, d in mel:
        m.add(bell(N(n_), d * B + 0.6), s * B, -0.3)
    t4 = 12 * B
    for k, n_ in enumerate((67, 71, 74)):
        m.add(bell(N(n_ + 12), .3), t4 + k * B / 3, -0.3, 0.9)
        m.add(snare(), t4 + k * B / 3, 0.0, 0.7)
    hit = t4 + B
    m.add(kick(), hit); m.add(cymbal(), hit, 0.3)
    for n_ in (48, 60, 64, 67, 72, 76):
        m.add(organ(N(n_), 2.4) * np.linspace(1.2, 0.0, int(2.4 * SR)) ** 0.5, hit, 0.2, 1.3)
    m.add(bass(N(36), 2.0), hit, 0, 1.2)
    m.add(bell(N(84), 2.2), hit, -0.3, 1.1); m.add(bell(N(88), 2.2), hit + .02, -0.3, 0.8)
    return m.stereo(), hit + 2.6


def preset_pitch():
    """Product pitch: punchy synth brass, four-on-the-floor, square lead, zip-up and hit."""
    B = 60 / 140
    m = Mix(12 * B + 3.0)
    prog = [(41, [65, 69, 72]), (46, [65, 70, 74]), (48, [64, 67, 72])]  # F  Bb  C
    for bar, (root, ch) in enumerate(prog):
        t0 = bar * 4 * B
        for beat in range(4):
            tb = t0 + beat * B
            m.add(kick(), tb, 0, 1.1)
            if beat in (1, 3):
                m.add(clap(), tb, 0.1)
            m.add(hat(), tb + B / 2, -0.3)
            for e in range(2):  # octave-bounce bass in eighths
                m.add(bass(N(root + 12 * e), B * 0.45), tb + e * B / 2, -0.05, 0.9)
        for st in (0, 1.5):
            for n_ in ch:
                m.add(brass(N(n_ - 12), B * 0.7), t0 + st * B, 0.3)
    mel = [(72, 0, .5), (77, .5, .5), (81, 1, .75), (79, 2, .5), (77, 2.5, .5), (79, 3, 1),
           (74, 4, .5), (77, 4.5, .5), (82, 5, .75), (81, 6, .5), (79, 6.5, .5), (77, 7, 1),
           (79, 8, .5), (81, 8.5, .5), (82, 9, .5), (84, 9.5, 1.4)]
    for n_, s, d in mel:
        m.add(lead(N(n_), d * B), s * B, -0.25)
    m.add(zip_up(B * 1.0), 11 * B, 0.2)
    m.add(snare(), 11 * B, 0, 0.6); m.add(snare(), 11.5 * B, 0, 0.8)
    hit = 12 * B
    m.add(kick(), hit, 0, 1.3); m.add(cymbal(2.8), hit, 0.2, 1.1)
    for n_ in (53, 57, 60, 65, 69, 72):
        m.add(brass(N(n_), 2.4, bright=1.4), hit, 0.15, 1.1)
    m.add(bass(N(29), 2.2), hit, 0, 1.3)
    m.add(lead(N(89), 1.2) * np.exp(-np.arange(int(1.2 * SR)) / SR * 2), hit, -0.25, 0.8)
    return m.stereo(), hit + 2.6


def preset_kids():
    """Kids: xylophone hook, plucky bass, claps, a boing, slide whistle up and a 'ding'."""
    B = 60 / 150
    m = Mix(12 * B + 2.8)
    roots = [48, 48, 48, 48, 55, 55, 55, 55, 53, 53, 55, 55]  # C | G | F G
    for beat, root in enumerate(roots):
        tb = beat * B
        m.add(pluck_bass(N(root if beat % 2 == 0 else root + 7), B * 0.9), tb, -0.1)
        m.add(kick(), tb, 0, 0.6) if beat % 2 == 0 else m.add(clap(), tb, 0.15)
        m.add(hat(), tb + B / 2, 0.3, 0.8)
    mel = [(72, 0, .5), (76, .5, .5), (79, 1, .5), (76, 1.5, .5), (79, 2, .5), (84, 2.5, 1),
           (74, 4, .5), (79, 4.5, .5), (83, 5, .5), (79, 5.5, .5), (83, 6, .5), (86, 6.5, 1),
           (81, 8, .5), (77, 8.5, .5), (81, 8.5 + .5, .5), (84, 9.5, .5)]
    for n_, s, d in mel:
        m.add(xylo(N(n_), .6), s * B, -0.2)
        m.add(xylo(N(n_ + 12), .3), s * B, 0.4, 0.25)
    m.add(boing(196), 3.5 * B, 0.3)
    m.add(boing(247), 7.5 * B, -0.3)
    m.add(slide_whistle(N(67), N(91), 2 * B), 10 * B, 0.2)
    hit = 12 * B
    m.add(kick(), hit); m.add(cymbal(2.0), hit, 0.2, 0.6)
    for n_ in (72, 76, 79, 84):
        m.add(xylo(N(n_), 1.5), hit, -0.1, 1.2)
    for k, n_ in enumerate((88, 91, 96)):
        m.add(bell(N(n_), 1.5), hit + 0.12 + k * 0.08, 0.3, 0.6)
    m.add(pluck_bass(N(36), 1.5), hit, 0, 1.2)
    return m.stereo(), hit + 2.4


def preset_psa():
    """PSA: warm pads, gentle bells, triangle. Calm and sincere (mostly)."""
    B = 60 / 84
    m = Mix(8 * B + 3.5)
    chords = [(0, 4, 43, [55, 59, 62, 67]), (4, 2, 48, [55, 60, 64, 67]), (6, 2, 50, [54, 57, 62, 66])]
    for st, ln, root, ch in chords:
        for n_ in ch:
            m.add(pad(N(n_), ln * B + .6), st * B, 0.2)
        m.add(bass(N(root), ln * B) * 0.6, st * B, 0)
    for bar in (0, 4):
        m.add(triangle_hit(), bar * B, 0.4)
    mel = [(71, 0, 1), (74, 1, 1), (79, 2, 1.5), (78, 3.5, .5), (76, 4, 1), (74, 5, 1), (72, 6, 1), (74, 7, 1)]
    for n_, s, d in mel:
        m.add(bell(N(n_), d * B + 1.0), s * B, -0.25, 0.9)
    end = 8 * B
    for n_ in (43, 55, 59, 62, 67, 71):
        m.add(pad(N(n_), 3.2), end, 0.1, 1.1)
    m.add(bell(N(79), 3.0), end, -0.25); m.add(bell(N(86), 3.0), end + .25, 0.25, 0.6)
    m.add(triangle_hit(3.0), end, 0.4, 1.2)
    return m.stereo(), end + 3.4


def preset_video():
    """Now on videocassette: timpani roll, brass swell Cm-Ab-Bb, big C major hit, sparkle."""
    m = Mix(7.5)
    for k in range(68):  # roll on G, getting louder right up to the hit
        t = k * 0.05
        m.add(timpani(N(43), 0.4, vel=0.15 + 0.45 * (k / 72) ** 1.5), t, (-1) ** k * 0.15)
    for st, ln, ch in ((0.0, 1.6, [48, 51, 55, 60]), (1.6, 1.4, [44, 48, 51, 56]), (3.0, 0.45, [46, 50, 53, 58])):
        for n_ in ch:
            sw = np.linspace(0.4, 1.0, int((ln + .3) * SR))
            m.add(brass(N(n_), ln + .3, bright=0.8) * sw, st, 0.2, 0.6)
    m.add(snare(), 3.6, 0, 0.5); m.add(snare(), 3.75, 0, 0.7)
    hit = 3.9
    m.add(timpani(N(36), 3.0, 2.0), hit); m.add(cymbal(3.2), hit, 0.2, 1.6); m.add(kick(), hit, 0, 1.2)
    for n_ in (48, 52, 55, 60, 64, 67, 72):
        m.add(brass(N(n_), 3.0, bright=1.5), hit, 0.15, 1.6)
    m.add(bass(N(24), 2.8), hit, 0, 1.2)
    for k, n_ in enumerate((84, 88, 91, 96, 100)):
        m.add(bell(N(n_), 2.0), hit + 0.25 + k * 0.07, 0.35 - k * 0.15, 0.7)
    return m.stereo(), hit + 3.2


PRESETS = {"local": preset_local, "pitch": preset_pitch, "kids": preset_kids, "psa": preset_psa, "video": preset_video}


def finish(mix, end):
    mix = mix[: int(end * SR)]
    dl = int(0.09 * SR); room = np.zeros_like(mix); room[dl:] = mix[:-dl] * 0.18
    mix = np.tanh((mix + room) * 1.4) / np.tanh(1.4)
    fade = int(0.4 * SR); mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return mix * 10 ** (-1.5 / 20) / np.abs(mix).max()


def write_ogg(mix, path):
    wav = path[:-4] + ".tmp.wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())
    meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", wav, "-af", "loudnorm=print_format=summary", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    lufs = float(re.search(r"Input Integrated:\s+(-?[\d.]+)", meas).group(1))
    gain = min(TARGET_LUFS - lufs, 0.0)  # only turn down; never clip
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-af", f"volume={gain:.2f}dB",
                    "-c:a", "libvorbis", "-q:a", "5", path], check=True)
    os.remove(wav)
    return lufs + gain


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    names = sys.argv[2:] or list(PRESETS)
    os.makedirs(out, exist_ok=True)
    for name in names:
        RNG = np.random.default_rng(3)
        globals()["RNG"] = RNG
        mix, end = PRESETS[name]()
        mix = finish(mix, end)
        path = os.path.join(out, f"jingle_{name}.ogg")
        lufs = write_ogg(mix, path)
        print(f"{path}: {len(mix)/SR:.2f}s, about {lufs:.1f} LUFS")
