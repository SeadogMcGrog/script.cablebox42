"""Kodi's memory on the N2 over hours (briefs/parked/memory-caches.md).  Run on the PC; needs n2.conf.

    python memwatch.py run HOURS [--drive] [--tag NAME]
    python memwatch.py chart DIR

run: every 60 s, over ssh: kodi.bin's pid, VmRSS and VmHWM, MemAvailable, and the kodi.log lines
since the last sample, counted as events: tune-ins (channel flips and programme starts),
"Refresh schedules", library scans (VideoInfoScanner Starting/Finished), Kodi restarts (a new
pid or "Starting Kodi").  Nothing is changed on the N2.
--drive: also works the TV like a viewer: TV on (channel 3), CH+ every 5 min, the guide (channel
2) for 2 min every 30 min, and at half time Tools > Refresh schedules with the TV off, then the
TV on again.  Each is marked in the log.  Never touches audio, volume or settings.
Files: G:\\CableBox42\\n2\\logs\\memory\\<date-time>[-TAG]\\samples.csv, events.csv, then chart.png and
summary.txt (written by `chart`, which `run` calls at the end).
"""
import csv
import datetime
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import n2  # noqa: E402

OUT = os.path.join(n2.ROOT, "logs", "memory")
PROBE = r"""p=$(pidof kodi.bin | cut -d' ' -f1)
echo "pid $p"
grep -E 'VmRSS|VmHWM' /proc/$p/status
grep MemAvailable /proc/meminfo
echo "logsize $(wc -c < /storage/.kodi/temp/kodi.log)"
"""
EVENTS = [("tune", re.compile(r"\[script\.cablebox42\] tune-in")),
          ("refresh", re.compile(r"\[script\.cablebox42\] Refresh schedules")),
          ("scan start", re.compile(r"VideoInfoScanner: Starting scan")),
          ("scan end", re.compile(r"VideoInfoScanner: Finished scan")),
          ("restart", re.compile(r"Starting Kodi \(")),
          ("traceback", re.compile(r"Traceback"))]


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def probe():
    out = n2.ssh(PROBE, check=False, timeout=30).decode("utf-8", "replace")
    v = {}
    for line in out.splitlines():
        parts = line.replace(":", " ").split()
        if len(parts) >= 2:
            v[parts[0]] = parts[1]
    return v


def new_log(start):
    """kodi.log bytes from START (a restart starts a new file: from 0 when it shrank)."""
    raw = n2.ssh("tail -c +%d /storage/.kodi/temp/kodi.log" % (start + 1), check=False, timeout=60)
    return raw.decode("utf-8", "replace")


class Run(object):
    def __init__(self, hours, drive, tag):
        self.hours, self.drive = hours, drive
        self.dir = os.path.join(OUT, datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S") + ("-" + tag if tag else ""))
        os.makedirs(self.dir)
        self.samples = open(os.path.join(self.dir, "samples.csv"), "w", newline="")
        self.sw = csv.writer(self.samples)
        self.sw.writerow(["time", "minute", "pid", "kodi_rss_mb", "kodi_hwm_mb", "mem_available_mb"])
        self.events = open(os.path.join(self.dir, "events.csv"), "w", newline="")
        self.ew = csv.writer(self.events)
        self.ew.writerow(["time", "minute", "event", "detail"])
        self.t0 = time.time()
        self.pid, self.logpos = None, None

    def minute(self):
        return round((time.time() - self.t0) / 60.0, 2)

    def mark(self, event, detail=""):
        self.ew.writerow([now(), self.minute(), event, detail])
        self.events.flush()
        print("%s  %-12s %s" % (now(), event, detail))

    def sample(self):
        try:
            v = probe()
        except Exception as exc:
            self.mark("no answer", str(exc)[:80])
            return
        pid, size = v.get("pid"), int(v.get("logsize", "0") or 0)
        if self.pid and pid != self.pid:
            self.mark("restart", "kodi pid %s -> %s" % (self.pid, pid))
        if self.logpos is not None:
            start = self.logpos if size >= self.logpos else 0
            try:
                for line in new_log(start).splitlines():
                    for name, rx in EVENTS:
                        if rx.search(line):
                            self.mark(name, line[:23] + " " + line.split("> ", 1)[-1][:90])
            except Exception as exc:
                self.mark("log read failed", str(exc)[:80])
        self.pid, self.logpos = pid, size
        kb = lambda k: int(v.get(k, "0") or 0) / 1024.0    # noqa: E731
        self.sw.writerow([now(), self.minute(), pid, "%.1f" % kb("VmRSS"), "%.1f" % kb("VmHWM"),
                          "%.1f" % kb("MemAvailable")])
        self.samples.flush()

    def act(self, what, fn):
        try:
            fn()
            self.mark("drive", what)
        except Exception as exc:
            self.mark("drive failed", "%s: %s" % (what, exc))

    def go(self):
        total = self.hours * 3600
        half_done = False
        last_flip = last_guide = time.time()
        if self.drive:
            self.act("TV on, channel 3", lambda: n2.rpc("Addons.ExecuteAddon",
                                                        {"addonid": n2.ADDON_ID, "params": ["watch", "3"]}))
        next_sample = time.time()
        while time.time() - self.t0 < total:
            if time.time() >= next_sample:
                self.sample()
                next_sample += 60
            if self.drive:
                t = time.time()
                if not half_done and t - self.t0 >= total / 2:
                    half_done = True
                    self.act("TV off (Stop)", lambda: n2.send_key("stop"))
                    time.sleep(15)
                    self.act("Tools > Refresh schedules", lambda: n2.rpc(
                        "Addons.ExecuteAddon", {"addonid": n2.ADDON_ID, "params": ["tool", "refresh"]}))
                    n2.wait_idle(600)
                    self.mark("drive", "refresh tool finished")
                    self.act("TV on, channel 3", lambda: n2.rpc(
                        "Addons.ExecuteAddon", {"addonid": n2.ADDON_ID, "params": ["watch", "3"]}))
                    last_flip = last_guide = time.time()
                elif t - last_guide >= 1800:
                    last_guide = last_flip = t
                    self.act("guide (channel 2)", lambda: n2.keys(["number2"]))
                    time.sleep(120)
                    self.act("back to channel 3", lambda: n2.keys(["number3"]))
                elif t - last_flip >= 300:
                    last_flip = t
                    self.act("CH+", lambda: n2.send_key("chup"))
            time.sleep(1)
        self.sample()
        if self.drive:
            self.act("TV off (Stop)", lambda: n2.send_key("stop"))
        self.samples.close()
        self.events.close()
        chart(self.dir)


def slope(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    d = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / d if d else 0.0


def chart(d):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = list(csv.DictReader(open(os.path.join(d, "samples.csv"))))
    ev = list(csv.DictReader(open(os.path.join(d, "events.csv"))))
    m = [float(r["minute"]) for r in rows]
    rss = [float(r["kodi_rss_mb"]) for r in rows]
    av = [float(r["mem_available_mb"]) for r in rows]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(m, rss, label="Kodi VmRSS (MB)", color="#1f6feb")
    ax.plot(m, av, label="MemAvailable (MB)", color="#2da44e")
    colours = {"refresh": "#cf222e", "scan start": "#9a6700", "restart": "#000000", "drive": "#8250df"}
    seen = set()
    for e in ev:
        c = colours.get(e["event"])
        if not c or (e["event"] == "drive" and "Refresh" not in e["detail"] and "guide" not in e["detail"]):
            continue
        lab = e["event"] if e["event"] != "drive" else e["detail"].split(" (")[0]
        ax.axvline(float(e["minute"]), color=c, alpha=0.5, lw=1, label=None if lab in seen else lab)
        seen.add(lab)
    ax.set_xlabel("minutes")
    ax.set_ylabel("MB")
    ax.set_title("N2 memory, %s" % os.path.basename(d))
    ax.legend(loc="center right", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(d, "chart.png"), dpi=110)
    lines = ["samples: %d over %.0f min" % (len(rows), m[-1] if m else 0)]
    if rows:
        lines.append("Kodi VmRSS: start %.0f MB, end %.0f MB, max %.0f MB; MemAvailable min %.0f MB"
                     % (rss[0], rss[-1], max(rss), min(av)))
        h = [x / 60.0 for x in m]
        lines.append("trend, whole run: %+.1f MB/hour" % slope(h, rss))
        last = [(x, y) for x, y in zip(h, rss) if x >= h[-1] - 1]
        lines.append("trend, last hour: %+.1f MB/hour" % slope([x for x, _ in last], [y for _, y in last]))
        for e in ev:
            if e["event"] == "refresh":
                t = float(e["minute"])
                before = [y for x, y in zip(m, rss) if t - 3 <= x < t - 0.5]
                after = [y for x, y in zip(m, rss) if t + 0.5 < x <= t + 3]
                if before and after:
                    lines.append("refresh at %.0f min: %+.0f MB (%.0f -> %.0f)"
                                 % (t, after[-1] - before[0], before[0], after[-1]))
        n = sum(1 for e in ev if e["event"] == "tune")
        lines.append("tune-ins: %d; scans: %d; restarts: %d" % (
            n, sum(1 for e in ev if e["event"] == "scan start"), sum(1 for e in ev if e["event"] == "restart")))
    open(os.path.join(d, "summary.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(os.path.join(d, "chart.png"))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "run":
        tag = a[a.index("--tag") + 1] if "--tag" in a else ""
        Run(float(a[1]), "--drive" in a, tag).go()
    elif a and a[0] == "chart":
        chart(a[1])
    else:
        sys.exit(__doc__)
