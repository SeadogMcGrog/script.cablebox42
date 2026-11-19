"""Settings at 1080p on the N2: every category's top and bottom, by tool (settings-rework-n2-test.md).

    python .claude/tools/n2/settings_shots.py FOLDER

Starts with the add-on settings open and focus on the category list (first category).
Moves only: Right into the list, Up (wraps to the last row), Left back, Down to the next
category.  Changes nothing; leave the dialog with Back (= Cancel) afterwards."""
import re
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
import n2  # noqa: E402

folder = sys.argv[1]
names = ["breaks", "channels", "on-screen", "guide-weather", "holidays-events", "startup-library", "tools",
         "advanced"]


def cur():
    return re.sub(r"\[/?[A-Z]+[^\]]*\]", "", n2.labels("System.CurrentControl")["System.CurrentControl"])


for i, name in enumerate(names):
    cat = cur()
    n2.send_key("right")
    time.sleep(0.8)
    top = cur()
    n2.shot("%s/%d-%s-top" % (folder, i + 1, name))
    n2.send_key("up")
    time.sleep(0.8)
    bottom = cur()
    n2.shot("%s/%d-%s-bottom" % (folder, i + 1, name))
    print("%-22s first row %-45r last row %r" % (cat, top, bottom))
    n2.send_key("left")
    time.sleep(0.5)
    if i < len(names) - 1:
        n2.send_key("down")
        time.sleep(0.8)
