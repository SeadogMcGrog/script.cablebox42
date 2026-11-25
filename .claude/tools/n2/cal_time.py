"""The month calendar on the N2: opening time and CH+ held (seasons-n2-test.md, steps 1 and 3).

    python .claude/tools/n2/cal_time.py open [TOOL]   time from starting the tool (default
                                                       'specials') to the calendar drawn
    python .claude/tools/n2/cal_time.py hold SECS     hold CH+ (a press every 0.1 s), then time
                                                       until the month stops changing; checks the
                                                       month moved once per press
Reads the window's own properties (title, cur) through InfoLabels; changes nothing."""
import re
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
import n2  # noqa: E402

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


def title():
    """The calendar's title property ('' unless the calendar is the window in front)."""
    if not active():
        return ""
    return n2.labels("Window.Property(title)")["Window.Property(title)"]


def active():
    """A Python window is in front (Kodi gives them ids from 13000; the calendar is the
    only one this tool opens).  Kodi can't address it by its XML file name."""
    w = n2.rpc("GUI.GetProperties", {"properties": ["currentwindow"]})["currentwindow"]["id"]
    return 13000 <= w < 13100


def month_index(t):
    m = re.search(r"(%s) (\d{4})" % "|".join(MONTHS), t or "")
    return int(m.group(2)) * 12 + MONTHS.index(m.group(1)) if m else None


def opening(tool):
    if active():
        sys.exit("The calendar is already open")
    t0 = time.time()
    n2.rpc("Addons.ExecuteAddon", {"addonid": n2.ADDON_ID, "params": ["tool", tool]})
    t_win = None
    while time.time() - t0 < 30:
        if t_win is None and active():
            t_win = time.time() - t0
        if t_win is not None and title():
            print("calendar window active after %.2f s, its month drawn after %.2f s (%s)"
                  % (t_win, time.time() - t0, title()))
            return
        time.sleep(0.03)
    sys.exit("No calendar after 30 s (the list view instead? state.json specials_view)")


def holding(secs):
    if not active():
        sys.exit("Open the calendar first")
    m0 = month_index(title())
    n = n2.hold("chup", secs)
    t_last = time.time()
    last, stable_since = title(), time.time()
    while time.time() - t_last < 20:
        cur = title()
        if cur != last:
            last, stable_since = cur, time.time()
        elif time.time() - stable_since > 1.0:
            break
        time.sleep(0.03)
    m1 = month_index(last)
    print("%d CH+ presses in %.1f s; the month settled %.2f s after the last press on %s; moved %s months (%s)"
          % (n, secs, stable_since - t_last, last, (m1 - m0) if m0 and m1 else "?",
             "one per press" if m0 and m1 and m1 - m0 == n else "NOT one per press"))


if __name__ == "__main__":
    if sys.argv[1] == "open":
        opening(sys.argv[2] if len(sys.argv) > 2 else "specials")
    else:
        holding(float(sys.argv[2]))
