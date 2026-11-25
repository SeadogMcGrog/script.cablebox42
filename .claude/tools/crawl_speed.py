"""crawl_speed.py REC.mp4 : vertical shift of the guide grid between frames (px of a
640x360 recording; the list is y 147..360). Prints per-frame shift and a summary:
a smooth crawl has no zero-shift runs and a steady shift."""
import subprocess
import sys

import numpy as np

W, H = 640, 360
raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", sys.argv[1], "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                     stdout=subprocess.PIPE, check=True).stdout
frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)
y0, y1, x0, x1 = 160, 340, 20, 620       # inside the list, clear of the header
shifts = []
for a, b in zip(frames[:-1], frames[1:]):
    A = a[y0:y1, x0:x1]
    best, bs = None, 0
    for s in range(0, 12):                   # the crawl moves up: content at y in b was at y+s in a
        d = np.abs(b[y0:y1 - 12, x0:x1] - a[y0 + s:y1 - 12 + s, x0:x1]).mean()
        if best is None or d < best:
            best, bs = d, s
    shifts.append(bs)
print(" ".join(str(s) for s in shifts))
moving = shifts[10:]                         # skip the first second
zeros = sum(1 for s in moving if s == 0)
runs, cur = 0, 0
for s in moving:
    cur = cur + 1 if s == 0 else 0
    runs = max(runs, cur)
print("frames %d, mean shift %.2f px/frame, zero-shift frames %d, longest still run %d frames"
      % (len(moving), float(np.mean(moving)) if moving else 0, zeros, runs))
# over 10 frames (1 s): the speed with less rounding
long = []
for i in range(10, len(frames) - 10, 5):
    a, b = frames[i], frames[i + 10]
    best, bs = None, 0
    for s in range(0, 40):
        d = np.abs(b[y0:y1 - 40, x0:x1] - a[y0 + s:y1 - 40 + s, x0:x1]).mean()
        if best is None or d < best:
            best, bs = d, s
    long.append(bs)
print("px per second:", " ".join(str(s) for s in long))
