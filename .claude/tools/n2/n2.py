#!/usr/bin/env python
"""Drive the ODROID N2 (CoreELEC, Kodi 21) from the Windows PC.  briefs/n2-remote-testing.md.

    bash .claude/tools/n2/n2 COMMAND ...      (or: python .claude/tools/n2/n2.py COMMAND ...)

Only ssh and Kodi's JSON-RPC over HTTP; nothing is installed on the N2 beyond the SSH key.
Text work (settings.xml, logs) happens on the PC: CoreELEC's busybox tools are limited.
Files go under G:\\CableBox42\\n2\\ (backups\\, shots\\, logs\\, snaps\\).  Address and HTTP login
come from G:\\CableBox42\\n2\\n2.conf (outside the repository):

    [n2]
    host = <the N2's fixed IP address>
    http_port = 8080
    http_user = <Kodi's web server user>
    http_pass = <its password>
    ssh_key = ~/.ssh/n2_cablebox

Commands
  preflight                   before every session: TV/display on (HDMI), Kodi on a real display
                              mode, the media drive answers (waits out a spin-up, up to 90 s), a
                              screenshot has a picture; PASS or FAIL with what to do
  status                      Kodi and add-on version, window, player, display
  restart                     stop and start Kodi (e.g. after the TV was off at Kodi's start)
  install ZIP                 back up, stop Kodi, replace the add-on with ZIP, start, check version
  backup [LABEL]              addon_data (and the add-on's code) -> n2\\backups\\<date-time>[-LABEL]
  backups                     list them
  restore NAME|latest [--addon]   put addon_data back (--addon: the add-on's code too)
  key K [K...]                remote keys: up down left right ok back menu info home chup chdn
                              pgup pgdn play stop osd ... (any Kodi action name); K*5 repeats;
                              wait:1.5 pauses; --gap S between keys (default 0.4)
  goto TEXT [--key down] [--max 40]   press KEY until the focused item contains TEXT
  hold K SECS                 repeat K every 0.1 s for SECS (a held button)
  text STRING                 type into the open keyboard
  shot NAME                   screenshot -> n2\\shots\\NAME.png
  log [NAME]                  kodi.log -> n2\\logs\\NAME.log
  grep REGEX [LOGFILE]        lines of the N2's kodi.log (or a saved one) matching REGEX
  audio [LOGFILE] [--since HH:MM:SS]   CActiveAE / CAESinkALSA / "Unable to open" lines, counted
  get ID                      the add-on's setting
  set ID VALUE [ID VALUE...]  stop Kodi, edit the add-on's settings.xml, start Kodi ("" clears)
  time                        the last "Refresh schedules ... s" in kodi.log
  time run [--tool rebuild]   start the add-on's Rebuild schedules tool and time it on the PC
                              (answers 1.1.1's Yes/No itself), then compare with the log
  snap NAME                   guisettings.xml, sources.xml and a file list of userdata (outside
                              the add-on's folders) -> n2\\snaps\\NAME\\
  compare A B                 what differs between two snaps
  rpc METHOD [JSON]           any JSON-RPC call
  info LABEL [LABEL...]       Kodi info labels (System.CurrentWindow, Control.GetLabel(...)...)
  wait-idle [SECS]            until the add-on's tools are idle

Never touches the library, sources, Kodi's own settings or audio settings.

Learned on the N2 (2026-11-16); `preflight` checks the first two before a session:
- No picture with the TV off: HDMI hotplug 0 (`status` shows it) means Kodi draws nothing and every
  screenshot is one flat colour. Kodi started while the TV was off stays at "1280x720 @ 0.00 Hz"
  after the TV comes back: `restart` with the TV on.
- A USB media drive spins down (about 60 s to wake). Once its NTFS driver hung for 15+ min
  (nothing played, rebuilds took 70 s instead of 47-51 s) until a reboot; `preflight` lists a
  library folder (up to 90 s) and says so.
- Kodi's time/number dialog ignores Input.SendText: press `number0`..`number9`, then Done.
- 1.1.1's Rebuild question is Cancel / Rebuild (the yes button is control 11); ~hol7 asks nothing
  and logs "Refresh schedules: N channels ..., X s". `time run` handles both.
- The add-on's script windows show as odd names in System.CurrentWindow ("Immediate HDD spindown").
"""
import base64
import configparser
import datetime
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import zipfile

ROOT = r"G:\CableBox42\n2"
CONF = os.path.join(ROOT, "n2.conf")
ADDON_ID = "script.cablebox42"
R_ADDON = "/storage/.kodi/addons/" + ADDON_ID
R_DATA = "/storage/.kodi/userdata/addon_data/" + ADDON_ID
R_LOG = "/storage/.kodi/temp/kodi.log"
R_USERDATA = "/storage/.kodi/userdata"
BUSY_PROP = "Window(Home).Property(script.cablebox42.tool)"
REFRESH_RE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+).*\[script\.cablebox42\] Refresh schedules: "
                        r"(\d+) channels.*?([\d.]+) s\s*$")
AUDIO_RE = re.compile(r"CActiveAE|CAESinkALSA|Unable to open|AESink|PassthroughFormat|audio device", re.I)

KEYS = {   # name -> (method, params)
    "up": ("Input.Up", None), "down": ("Input.Down", None), "left": ("Input.Left", None),
    "right": ("Input.Right", None), "ok": ("Input.Select", None), "select": ("Input.Select", None),
    "back": ("Input.Back", None), "home": ("Input.Home", None), "menu": ("Input.ContextMenu", None),
    "context": ("Input.ContextMenu", None), "info": ("Input.Info", None), "osd": ("Input.ShowOSD", None),
}
ACTIONS = {"chup": "channelup", "chdn": "channeldown", "chdown": "channeldown", "pgup": "pageup",
           "pgdn": "pagedown", "pgdown": "pagedown", "play": "playpause", "guide": "showvideomenu"}
FORBIDDEN_ACTIONS = ("audio", "volume", "mute", "passthrough", "settings")   # never via 'key'


# ------------------------------------------------------------------ config, ssh, rpc
def conf():
    c = configparser.ConfigParser()
    if not c.read(CONF):
        sys.exit("No %s - see the top of n2.py" % CONF)
    n = c["n2"]
    return {"host": n.get("host"), "port": n.get("http_port", "8080"), "user": n.get("http_user", "kodi"),
            "pass": n.get("http_pass", ""), "key": os.path.expanduser(n.get("ssh_key", "~/.ssh/n2_cablebox"))}


CFG = None


def cfg():
    global CFG
    if CFG is None:
        CFG = conf()
    return CFG


def ssh(cmd, data=None, check=True, timeout=120):
    """Run cmd on the N2; data (bytes) goes to its stdin. Returns stdout bytes."""
    c = cfg()
    args = ["ssh", "-i", c["key"].replace("\\", "/"), "-o", "BatchMode=yes", "-o", "ConnectTimeout=6",
            "-o", "StrictHostKeyChecking=accept-new", "root@" + c["host"], cmd]
    p = subprocess.run(args, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if check and p.returncode != 0:
        sys.exit("ssh failed (%d): %s\n%s" % (p.returncode, cmd, p.stderr.decode("utf-8", "replace").strip()))
    return p.stdout


def fetch(remote, local):
    os.makedirs(os.path.dirname(local), exist_ok=True)
    with open(local, "wb") as f:
        f.write(ssh("cat '%s'" % remote))
    return local


def put(local, remote):
    with open(local, "rb") as f:
        ssh("cat > '%s.n2tmp' && mv '%s.n2tmp' '%s'" % (remote, remote, remote), data=f.read())


def rpc(method, params=None, timeout=10):
    c = cfg()
    body = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    req = urllib.request.Request("http://%s:%s/jsonrpc" % (c["host"], c["port"]),
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    req.add_header("Authorization", "Basic " + base64.b64encode(("%s:%s" % (c["user"], c["pass"])).encode()).decode())
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read().decode("utf-8"))
    if "error" in out:
        raise RuntimeError("%s: %s" % (method, out["error"]))
    return out.get("result")


def labels(*names):
    return rpc("XBMC.GetInfoLabels", {"labels": list(names)}) or {}


def booleans(*names):
    return rpc("XBMC.GetInfoBooleans", {"booleans": list(names)}) or {}


def stamp():
    return datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")


# ------------------------------------------------------------------ before a session
def preflight():
    """The checks before a session (briefs/n2-remote-testing.md); True if all pass."""
    ok = True
    hpd = ssh("cat /sys/class/amhdmitx/amhdmitx0/hpd_state 2>/dev/null", check=False).decode().strip()
    res = labels("System.ScreenResolution").get("System.ScreenResolution", "")
    if hpd != "1":
        print("FAIL  TV/display: HDMI shows nothing connected - switch the TV (and receiver) on to the N2")
        ok = False
    else:
        print("ok    TV/display: connected")
    if "@ 0.00 Hz" in res:
        print("FAIL  Kodi is on its placeholder mode (%s): it started with the TV off - TV on, then `n2 restart`"
              % res)
        ok = False
    else:
        print("ok    display mode: %s" % res)
    # a folder of the video library: the drive it's on must answer (a sleeping drive takes ~60 s)
    path = ""
    try:
        got = rpc("VideoLibrary.GetEpisodes", {"limits": {"end": 1}, "properties": ["file"]}).get("episodes") or \
            rpc("VideoLibrary.GetMovies", {"limits": {"end": 1}, "properties": ["file"]}).get("movies") or []
        path = os.path.dirname(got[0]["file"]) if got else ""
    except Exception as exc:
        print("FAIL  library: %s" % exc)
        ok = False
    if path.startswith("/"):
        t0 = time.time()
        quoted = "'" + path.replace("'", "'\"'\"'") + "'"
        try:                 # CoreELEC's busybox has no `timeout`: the PC side times it
            out = ssh("ls -d %s >/dev/null 2>&1 && echo yes || echo no" % quoted,
                      check=False, timeout=90).decode().strip()
        except subprocess.TimeoutExpired:
            out = "timeout"
        took = time.time() - t0
        if out != "yes":
            print("FAIL  media drive: %s didn't answer in 90 s (a hung drive or NTFS driver: "
                  "power-cycle the drive or reboot the N2)" % path)
            ok = False
        else:
            print("ok    media drive answered in %.1f s%s" % (took, " (it was asleep)" if took > 5 else ""))
    elif path:
        print("--    media: %s is not a local drive; not checked" % path)
    if ok:
        try:
            from PIL import Image
            rpc("Input.Left")
            rpc("Input.Right")           # something changes, so the frame is a fresh one
            time.sleep(0.5)
            ext = Image.open(shot("preflight")).convert("RGB").getextrema()
            if all(a == b for a, b in ext):
                print("FAIL  the screenshot is one flat colour: Kodi isn't drawing (TV off?)")
                ok = False
            else:
                print("ok    the screenshot has a picture")
        except ImportError:
            print("--    screenshot not checked (no Pillow on this PC)")
        except SystemExit as exc:
            print("FAIL  screenshot: %s" % exc)
            ok = False
    print("PASS" if ok else "FAIL")
    return ok


# ------------------------------------------------------------------ Kodi up / down
def kodi_up():
    try:
        return rpc("JSONRPC.Ping", timeout=3) == "pong"
    except Exception:
        return False


def stop_kodi():
    ssh("systemctl stop kodi")
    for _ in range(60):
        if ssh("pidof kodi.bin >/dev/null && echo up || echo down", check=False).strip() == b"down":
            return
        time.sleep(0.5)
    sys.exit("Kodi did not stop")


def start_kodi(wait=True):
    ssh("systemctl start kodi")
    if not wait:
        return
    t0 = time.time()
    while time.time() - t0 < 120:
        if kodi_up():
            break
        time.sleep(1)
    else:
        sys.exit("Kodi did not answer within 2 minutes")
    time.sleep(3)           # the add-on's service starts a moment after JSON-RPC
    print("Kodi up after %.0f s" % (time.time() - t0))


def wait_idle(secs=180, quiet=2.0):
    """Until the add-on's tool flag and progress dialogs have been clear for `quiet` s."""
    t0, clear_since = time.time(), None
    while time.time() - t0 < secs:
        try:
            busy = labels(BUSY_PROP).get(BUSY_PROP) or ""
            b = booleans("Window.IsActive(progressdialog)", "Window.IsActive(extendedprogressdialog)")
            busy = busy or any(b.values())
        except Exception:
            busy = True
        if busy:
            clear_since = None
        elif clear_since is None:
            clear_since = time.time()
        elif time.time() - clear_since >= quiet:
            return True
        time.sleep(0.3)
    return False


# ------------------------------------------------------------------ backup / install / restore
def backup(label=""):
    name = stamp() + ("-" + label if label else "")
    d = os.path.join(ROOT, "backups", name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "addon_data.tar.gz"), "wb") as f:
        f.write(ssh("cd /storage/.kodi/userdata/addon_data && tar czf - %s" % ADDON_ID))
    with open(os.path.join(d, "addon.tar.gz"), "wb") as f:
        f.write(ssh("cd /storage/.kodi/addons && tar czf - %s" % ADDON_ID))
    try:
        v = (rpc("Addons.GetAddonDetails", {"addonid": ADDON_ID, "properties": ["version"]}) or {})["addon"]["version"]
    except Exception:
        v = "?"
    with open(os.path.join(d, "info.txt"), "w") as f:
        f.write("add-on version %s\nmade %s\n" % (v, datetime.datetime.now().isoformat(timespec="seconds")))
    n = len(ssh("cd %s && find . -type f" % R_DATA).splitlines())
    print("Backed up addon_data (%d files) and the add-on %s -> %s" % (n, v, d))
    return d


def zip_sums(zpath, names):
    out = {}
    with zipfile.ZipFile(zpath) as z:
        for n in names:
            try:
                out[n] = hashlib.md5(z.read(ADDON_ID + "/" + n)).hexdigest()
            except KeyError:
                pass
    return out


def install(zpath):
    if not os.path.isfile(zpath):
        sys.exit("No such zip: %s" % zpath)
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        if not all(n.startswith(ADDON_ID + "/") for n in names):
            sys.exit("Not a %s zip (top folder)" % ADDON_ID)
        version = re.search(r'<addon[^>]*\sversion="([^"]+)"', z.read(ADDON_ID + "/addon.xml").decode()).group(1)
    check = ["addon.xml", "resources/lib/scheduler.py", "resources/lib/manager.py"]
    if any(n.endswith("resources/lib/specials_editor.py") for n in names):
        check.append("resources/lib/specials_editor.py")
    sums = zip_sums(zpath, check)
    print("Installing %s (version %s)" % (os.path.basename(zpath), version))
    backup("before-install")
    with open(zpath, "rb") as f:
        ssh("cat > /storage/.n2-install.zip", data=f.read(), timeout=300)
    stop_kodi()
    ssh("rm -rf %s && unzip -q -o /storage/.n2-install.zip -d /storage/.kodi/addons && rm -f /storage/.n2-install.zip"
        % R_ADDON)
    start_kodi()
    # the version Kodi logged on start, and checksums of the files on the box
    t0, logged = time.time(), None
    while time.time() - t0 < 60 and not logged:
        txt = ssh("grep -a '%s v' %s | tail -3" % (ADDON_ID, R_LOG), check=False).decode("utf-8", "replace")
        m = re.findall(r"%s v(\S+)" % re.escape(ADDON_ID), txt)
        logged = m[-1] if m else None
        if not logged:
            time.sleep(2)
    try:
        api = rpc("Addons.GetAddonDetails", {"addonid": ADDON_ID, "properties": ["version", "enabled"]})["addon"]
    except Exception as exc:
        api = {"version": "? (%s)" % exc, "enabled": "?"}
    remote = ssh("cd %s && md5sum %s" % (R_ADDON, " ".join(check))).decode()
    rs = {l.split()[1]: l.split()[0] for l in remote.splitlines() if l.strip()}
    same = [n for n in sums if rs.get(n) == sums[n]]
    print("Log: %s v%s   JSON-RPC: v%s enabled=%s   files matching the zip: %d/%d"
          % (ADDON_ID, logged, api.get("version"), api.get("enabled"), len(same), len(sums)))
    ok = logged == version and api.get("version") == version and len(same) == len(sums)
    print("INSTALL %s" % ("PASS" if ok else "FAIL"))
    return ok


def backups():
    d = os.path.join(ROOT, "backups")
    return sorted(x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x))) if os.path.isdir(d) else []


def restore(name, addon=False):
    if name == "latest":
        b = backups()
        if not b:
            sys.exit("No backups")
        name = b[-1]
    d = os.path.join(ROOT, "backups", name)
    if not os.path.isfile(os.path.join(d, "addon_data.tar.gz")):
        sys.exit("No backup %s" % d)
    stop_kodi()
    with open(os.path.join(d, "addon_data.tar.gz"), "rb") as f:
        ssh("rm -rf %s && cd /storage/.kodi/userdata/addon_data && tar xzf -" % R_DATA, data=f.read())
    if addon:
        with open(os.path.join(d, "addon.tar.gz"), "rb") as f:
            ssh("rm -rf %s && cd /storage/.kodi/addons && tar xzf -" % R_ADDON, data=f.read())
    start_kodi()
    # check: every file in the backup is back with the same checksum
    import tarfile
    with tarfile.open(os.path.join(d, "addon_data.tar.gz")) as t:
        want = {m.name.split("/", 1)[1]: hashlib.md5(t.extractfile(m).read()).hexdigest()
                for m in t.getmembers() if m.isfile() and "/" in m.name}
    have = {}
    for l in ssh("cd %s && find . -type f -exec md5sum {} +" % R_DATA).decode().splitlines():
        s, p = l.split(None, 1)
        have[p.strip()[2:]] = s
    diff = [p for p in want if have.get(p) != want[p]]
    extra = [p for p in have if p not in want]
    print("Restored %s%s: %d files, %d differ now, %d new since"
          % (name, " (and the add-on)" if addon else "", len(want), len(diff), len(extra)))
    for p in (diff + extra)[:20]:
        print("   changed since restore (Kodi or the add-on wrote it on start): %s" % p)
    return name


# ------------------------------------------------------------------ keys, screenshots, logs
def send_key(k):
    k = k.lower()
    if any(f in k for f in FORBIDDEN_ACTIONS):
        sys.exit("Refusing key %r (audio/settings actions are off limits)" % k)
    if k in KEYS:
        m, p = KEYS[k]
        return rpc(m, p)
    return rpc("Input.ExecuteAction", {"action": ACTIONS.get(k, k)})


def keys(seq, gap=0.4):
    for item in seq:
        if item.startswith("wait:"):
            time.sleep(float(item[5:]))
            continue
        k, _, n = item.partition("*")
        for _ in range(int(n or 1)):
            send_key(k)
            time.sleep(gap)


def goto(text, key="down", most=40):
    """Press key until the focused control's label contains text (case-insensitive)."""
    seen = []
    for _ in range(most + 1):
        cur = re.sub(r"\[/?[A-Z]+[^\]]*\]", "", labels("System.CurrentControl")["System.CurrentControl"])
        if text.lower() in cur.lower():
            print("focus: %s" % cur)
            return cur
        if seen[-3:].count(cur) == 3:
            break              # stuck at the end of a list
        seen.append(cur)
        send_key(key)
        time.sleep(0.25)
    sys.exit("Didn't reach %r (last focus %r)" % (text, seen[-1] if seen else ""))


def hold(k, secs):
    t0, n = time.time(), 0
    while time.time() - t0 < secs:
        send_key(k)
        n += 1
        time.sleep(0.1)
    return n


def shot_dir():
    p = rpc("Settings.GetSettingValue", {"setting": "debug.screenshotpath"})["value"]
    if not p:
        sys.exit("Kodi has no screenshot folder (Settings > System > Logging > Screenshot folder); "
                 "without one Kodi would ask on screen. Not taking it.")
    return p.rstrip("/")


def shot(name):
    d = shot_dir()
    before = ssh("ls -t %s/*.png 2>/dev/null | head -1" % d, check=False).strip()
    rpc("Input.ExecuteAction", {"action": "screenshot"})
    for _ in range(40):
        time.sleep(0.25)
        now = ssh("ls -t %s/*.png 2>/dev/null | head -1" % d, check=False).strip()
        if now and now != before:
            break
    else:
        sys.exit("No new screenshot in %s" % d)
    # let Kodi finish writing it: a 1080p PNG can take a few seconds on the N2 (a copy
    # taken too early was 0 bytes); its size must be non-zero and the same twice
    last = -1
    for _ in range(40):
        time.sleep(0.5)
        size = ssh("stat -c %%s '%s' 2>/dev/null || echo 0" % now.decode(), check=False).strip()
        size = int(size or 0)
        if size > 0 and size == last:
            break
        last = size
    local = fetch(now.decode(), os.path.join(ROOT, "shots", name + ".png"))
    if os.path.getsize(local) == 0:
        sys.exit("Screenshot %s came back empty" % now.decode())
    print(local)
    return local


def get_log(name=None):
    local = fetch(R_LOG, os.path.join(ROOT, "logs", (name or stamp()) + ".log"))
    print(local)
    return local


def read_log(path=None):
    if path:
        with open(path, "rb") as f:
            return f.read().decode("utf-8", "replace")
    return ssh("cat %s" % R_LOG).decode("utf-8", "replace")


def audio(path=None, since=None):
    lines = [l for l in read_log(path).splitlines() if AUDIO_RE.search(l)]
    if since:
        lines = [l for l in lines if l[11:19] >= since]
    kinds = {}
    for l in lines:
        k = re.sub(r"^\S+ \S+ T:\d+\s+\w+ <\w+>: ", "", l)
        k = re.sub(r"\d+", "#", k)[:90]
        kinds[k] = kinds.get(k, 0) + 1
    for l in lines[-40:]:
        print(l[:200])
    print("--- %d audio lines; by kind:" % len(lines))
    for k, n in sorted(kinds.items(), key=lambda x: -x[1]):
        print("%5d  %s" % (n, k))
    return lines


# ------------------------------------------------------------------ settings.xml
def settings_edit(pairs):
    local = os.path.join(ROOT, "logs", "settings-%s.xml" % stamp())
    stop_kodi()
    try:
        fetch(R_DATA + "/settings.xml", local)
        with open(local, encoding="utf-8") as f:
            xml = f.read()
        for sid, val in pairs:
            val_x = val.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            pat = re.compile(r'<setting id="%s"[^>]*?(/>|>[^<]*</setting>)' % re.escape(sid))
            new = '<setting id="%s">%s</setting>' % (sid, val_x) if val else '<setting id="%s" />' % sid
            if pat.search(xml):
                xml = pat.sub(new, xml, count=1)
            else:
                xml = xml.replace("</settings>", "    %s\n</settings>" % new)
            print("%s = %r" % (sid, val))
        with open(local + ".new", "w", encoding="utf-8", newline="\n") as f:
            f.write(xml)
        put(local + ".new", R_DATA + "/settings.xml")
    finally:
        start_kodi()
    for sid, val in pairs:
        if get_setting(sid) != val:
            sys.exit("%s did not stick" % sid)


def get_setting(sid):
    xml = ssh("cat %s/settings.xml" % R_DATA).decode("utf-8", "replace")
    m = re.search(r'<setting id="%s"[^>]*?(?:/>|>([^<]*)</setting>)' % re.escape(sid), xml)
    return (m.group(1) or "") if m else None


# ------------------------------------------------------------------ timing
def last_refresh(path=None):
    hits = [REFRESH_RE.match(l) for l in read_log(path).splitlines()]
    hits = [h for h in hits if h]
    return hits[-1] if hits else None


def time_log(path=None):
    h = last_refresh(path)
    if not h:
        print("No 'Refresh schedules ... s' line in the log (1.1.1 doesn't write one: use 'time run').")
        return None
    end = datetime.datetime.strptime(h.group(1)[:23], "%Y-%m-%d %H:%M:%S.%f")
    took = float(h.group(3))
    print("Refresh schedules: %s channels, %.1f s (log, ended %s, started %s)"
          % (h.group(2), took, end.strftime("%H:%M:%S.%f")[:-3],
             (end - datetime.timedelta(seconds=took)).strftime("%H:%M:%S.%f")[:-3]))
    return took


def time_run(tool="rebuild"):
    """Start Settings > Tools > Rebuild schedules the way the menu does (RunScript ... tool,rebuild),
    answer a Yes/No question with Yes (1.1.1), and time from the OK to the end on the PC by
    polling Kodi every 0.1 s: the add-on's busy flag and its progress dialogs."""
    if not wait_idle(240):
        sys.exit("The add-on stays busy; not timing")
    before = last_refresh()
    before = before.group(0) if before else None
    rpc("Addons.ExecuteAddon", {"addonid": ADDON_ID, "params": ["tool", tool]})
    t_ok = time.time()
    asked = False
    seen_busy = False
    clear_since = None
    while time.time() - t_ok < 600:
        lb = labels(BUSY_PROP, "System.CurrentControl")
        b = booleans("Window.IsActive(yesnodialog)", "Window.IsActive(progressdialog)",
                     "Window.IsActive(extendedprogressdialog)")
        if b["Window.IsActive(yesnodialog)"]:
            # 1.1.1: "Rebuild every channel's schedule from now?" (Cancel / Rebuild): the yes
            # button is control 11 whatever its label; move to it and press it
            yes = labels("Control.GetLabel(11)")["Control.GetLabel(11)"]
            cur = ""
            for _ in range(4):
                cur = labels("System.CurrentControl")["System.CurrentControl"]
                if cur == yes:
                    break
                rpc("Input.Right")
                time.sleep(0.15)
            if not yes or labels("System.CurrentControl")["System.CurrentControl"] != yes:
                sys.exit("Couldn't reach the yes button %r (focused: %r)" % (yes, cur))
            rpc("Input.Select")
            t_ok, asked = time.time(), True       # the stopwatch starts at that OK
            time.sleep(0.1)
            continue
        busy = bool(lb.get(BUSY_PROP)) or b["Window.IsActive(progressdialog)"] or \
            b["Window.IsActive(extendedprogressdialog)"]
        now = time.time()
        if busy:
            seen_busy, clear_since = True, None
        elif seen_busy:
            if clear_since is None:
                clear_since = now
            elif now - clear_since > 0.6:
                break
        elif now - t_ok > 1.5:
            # never saw it busy: maybe it was quicker than a poll - look for the log line
            h = last_refresh()
            if h and h.group(0) != before:
                clear_since = now
                break
        time.sleep(0.1)
    else:
        sys.exit("Still busy after 10 minutes")
    wall = clear_since - t_ok
    print("Stopwatch (PC): %.1f s from %s to the end%s" % (
        wall, "its OK" if asked else "starting the tool", " (answered its question)" if asked else ""))
    time.sleep(1.0)
    h = last_refresh()
    if h and h.group(0) != before:
        took = float(h.group(3))
        print("Log: %.1f s for %s channels; PC stopwatch - log = %+.1f s (startup, saving, the notice)"
              % (took, h.group(2), wall - took))
    else:
        print("Log: no new 'Refresh schedules' line (this build doesn't log its time)")
    return wall


# ------------------------------------------------------------------ snapshots of Kodi's own files
def snap(name):
    d = os.path.join(ROOT, "snaps", name)
    os.makedirs(d, exist_ok=True)
    for f in ("guisettings.xml", "sources.xml"):
        try:
            fetch("%s/%s" % (R_USERDATA, f), os.path.join(d, f))
        except SystemExit:
            open(os.path.join(d, f), "w").close()
    lst = ssh("cd %s && find . -type f ! -path './addon_data/%s/*' ! -path './Thumbnails/*' "
              "! -path './Database/Textures*' -exec md5sum {} + | sort -k2" % (R_USERDATA, ADDON_ID), check=False)
    with open(os.path.join(d, "userdata.md5"), "wb") as f:
        f.write(lst)
    print("%s (%d userdata files outside the add-on's folder)" % (d, len(lst.splitlines())))


def compare(a, b):
    da, db = os.path.join(ROOT, "snaps", a), os.path.join(ROOT, "snaps", b)
    same = True
    for f in ("guisettings.xml", "sources.xml"):
        with open(os.path.join(da, f), encoding="utf-8", errors="replace") as x, \
                open(os.path.join(db, f), encoding="utf-8", errors="replace") as y:
            d = list(difflib.unified_diff(x.read().splitlines(), y.read().splitlines(), f + " " + a, f + " " + b,
                                          lineterm="", n=0))
        print("%s: %s" % (f, "identical" if not d else "%d lines differ" % len([l for l in d if l[:1] in "+-"])))
        for l in d[:40]:
            print("   " + l)
        same = same and not d

    def md5s(p):
        with open(os.path.join(p, "userdata.md5"), encoding="utf-8", errors="replace") as f:
            return {l.split(None, 1)[1].strip(): l.split()[0] for l in f if l.strip()}
    ma, mb = md5s(da), md5s(db)
    ch = sorted(p for p in set(ma) | set(mb) if ma.get(p) != mb.get(p))
    print("userdata files outside the add-on that changed: %d" % len(ch))
    for p in ch[:40]:
        print("   %s %s" % ("new " if p not in ma else "gone" if p not in mb else "diff", p))
    return same, ch


# ------------------------------------------------------------------ main
def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")    # labels carry ★ and the like
    except Exception:
        pass
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd, a = argv[0], argv[1:]
    if cmd == "status":
        print(json.dumps(rpc("Application.GetProperties", {"properties": ["version"]})["version"]))
        print(rpc("Addons.GetAddonDetails", {"addonid": ADDON_ID, "properties": ["version", "enabled"]})["addon"])
        print(labels("System.CurrentWindow", "System.CurrentControl", BUSY_PROP, "System.Date", "System.Time",
                     "System.ScreenResolution"))
        print("HDMI display connected:", ssh("cat /sys/class/amhdmitx/amhdmitx0/hpd_state").decode().strip() == "1")
        print("players:", rpc("Player.GetActivePlayers"))
    elif cmd == "preflight":
        sys.exit(0 if preflight() else 1)
    elif cmd == "restart":
        stop_kodi()
        start_kodi()
        print(labels("System.ScreenResolution")["System.ScreenResolution"])
    elif cmd == "install":
        sys.exit(0 if install(a[0]) else 1)
    elif cmd == "backup":
        backup(a[0] if a else "")
    elif cmd == "backups":
        for b in backups():
            print(b)
    elif cmd == "restore":
        restore(a[0], addon="--addon" in a)
    elif cmd == "key":
        gap = 0.4
        if "--gap" in a:
            i = a.index("--gap")
            gap = float(a[i + 1])
            a = a[:i] + a[i + 2:]
        keys(a, gap)
    elif cmd == "goto":
        key = a[a.index("--key") + 1] if "--key" in a else "down"
        most = int(a[a.index("--max") + 1]) if "--max" in a else 40
        goto(a[0], key, most)
    elif cmd == "hold":
        print("%d presses" % hold(a[0], float(a[1])))
    elif cmd == "text":
        rpc("Input.SendText", {"text": a[0], "done": True})
    elif cmd == "shot":
        shot(a[0])
    elif cmd == "log":
        get_log(a[0] if a else None)
    elif cmd == "grep":
        flags = re.I if "-i" in a else 0
        a = [x for x in a if x != "-i"]
        rx = re.compile(a[0], flags)
        for l in read_log(a[1] if len(a) > 1 else None).splitlines():
            if rx.search(l):
                print(l[:300])
    elif cmd == "audio":
        since = None
        if "--since" in a:
            i = a.index("--since")
            since = a[i + 1]
            a = a[:i] + a[i + 2:]
        audio(a[0] if a else None, since)
    elif cmd == "get":
        print(repr(get_setting(a[0])))
    elif cmd == "set":
        if len(a) % 2:
            sys.exit("set ID VALUE [ID VALUE...]")
        settings_edit(list(zip(a[::2], a[1::2])))
    elif cmd == "time":
        if a and a[0] == "run":
            tool = a[a.index("--tool") + 1] if "--tool" in a else "rebuild"
            time_run(tool)
        else:
            time_log(a[0] if a else None)
    elif cmd == "snap":
        snap(a[0])
    elif cmd == "compare":
        same, ch = compare(a[0], a[1])
        sys.exit(0 if same and not ch else 1)
    elif cmd == "rpc":
        print(json.dumps(rpc(a[0], json.loads(a[1]) if len(a) > 1 else None), indent=1))
    elif cmd == "info":
        for k, v in labels(*a).items():
            print("%s = %s" % (k, v))
    elif cmd == "wait-idle":
        print("idle" if wait_idle(float(a[0]) if a else 180) else "still busy")
    else:
        sys.exit("Unknown command %r; n2 help" % cmd)


if __name__ == "__main__":
    main(sys.argv[1:])
