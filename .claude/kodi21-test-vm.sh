#!/bin/bash
# Headless Kodi 21 test rig for CableBox 42 (not shipped with the add-on).
#
# An Ubuntu 26.04 ("resolute") system with Kodi 21.3, Xvfb and a PulseAudio null sink
# whose output can be recorded, plus a small test library. Audio timing here is not
# hardware-accurate: use it to catch errors and regressions; the N2 has the final word.
#
# On Windows the rig is a WSL distro of its own, CableBoxRig, kept for good: its disk in
# %LOCALAPPDATA%\wsl\CableBoxRig\ (SSD), snapshots in G:\CableBox42\rig\snapshots\.
# Run this script from Git Bash; it passes each command on to the rig:
#
#   bash .claude/kodi21-test-vm.sh ensure          # reuse the rig; build it only if missing or broken
#   bash .claude/kodi21-test-vm.sh start | stop    # start (or restart) / stop Xvfb + PulseAudio + Kodi
#   bash .claude/kodi21-test-vm.sh status          # where it is, what runs, which CableBox is installed
#   bash .claude/kodi21-test-vm.sh install ZIP     # install a build, enable it, restart Kodi
#   bash .claude/kodi21-test-vm.sh reset-profile   # fresh Kodi profile + test library (Kodi itself stays)
#   bash .claude/kodi21-test-vm.sh lineup [FILE]   # CableBox lineup (default: 3 test channels), commercials on
#   bash .claude/kodi21-test-vm.sh setting ID=VALUE...  # CableBox settings (Kodi restarted around it)
#   bash .claude/kodi21-test-vm.sh send A [SECS] B # Kodi actions, e.g. Down Select 2 Back (numbers = pauses)
#   bash .claude/kodi21-test-vm.sh shot FILE.png   # screenshot (look at it to check UI)
#   bash .claude/kodi21-test-vm.sh rec FILE.mp4 SECS [A [SECS] B...]  # record picture + sound
#   bash .claude/kodi21-test-vm.sh zap [N] [SECS]  # TV on, flip N channels, count audio errors
#   bash .claude/kodi21-test-vm.sh log [N]         # CableBox and audio lines of kodi.log
#   bash .claude/kodi21-test-vm.sh sh 'CMD'        # run a command in the rig (HOME=/root, DISPLAY=:9)
#   bash .claude/kodi21-test-vm.sh snapshot [NAME] # wsl --export to G:\CableBox42\rig\snapshots\NAME.tar
#   bash .claude/kodi21-test-vm.sh restore FILE    # replace the rig with a snapshot (wsl --import)
#
# On plain Linux (a cloud VM) the same commands run as root against a chroot
# ($KODI_CHROOT, default /opt/k21); `setup` builds it there (~10 min).
# Kodi's profile is /root/.kodi, the test library /root/library/tv, outputs /root/test.
#
# A Windows checkout may give this file CRLF line endings (.gitattributes asks for LF);
# it then reruns itself from an LF copy. Xvfb, PulseAudio and Kodi start with setsid,
# so they keep running when the command that started them ends.
#
# CRLF-safe: rerun from an LF copy (the comment mark keeps a CR off the last command)
if grep -q $'\r' "$0" 2>/dev/null; then f=$(mktemp); tr -d '\r' < "$0" > "$f"; exec bash "$f" "$@"; fi #
set -euo pipefail
ADDON=script.cablebox42
DISTRO=${CABLEBOX_RIG_DISTRO:-CableBoxRig}
RIG_HOME=${CABLEBOX_RIG_HOME:-G:/CableBox42/rig}       # Windows side: snapshots (and a build's tar)
# the distro's disk: on the SSD (G: is a USB hard disk; a cold Kodi start there took 20 s)
RIG_DISK=${CABLEBOX_RIG_DISK:-${LOCALAPPDATA:-C:/Users/${USERNAME:-}/AppData/Local}/wsl/$DISTRO}
BUILDER=${CABLEBOX_RIG_BUILDER:-Ubuntu}                 # a WSL distro that can debootstrap a new rig
KODI_BIN=/usr/lib/x86_64-linux-gnu/kodi/kodi.bin
SEED_LINEUP='{"version": 2, "channels": [
 {"id": "guide002", "number": 2, "name": "TV Guide", "type": "guide", "sources": [], "dayparts": [], "offair": [], "slots": [], "commercials": false, "midroll": false, "bumps": false, "lineup": "shuffle", "slot": 30, "callsign": "TG"},
 {"id": "keys0003", "number": 3, "name": "Keystone", "type": "network", "sources": [{"type": "tvgenre", "value": "Comedy"}, {"type": "tvgenre", "value": "Science Fiction"}], "dayparts": [], "offair": [], "slots": [], "commercials": true, "callsign": "KEY"},
 {"id": "beac0004", "number": 4, "name": "Beacon", "type": "network", "sources": [{"type": "tvgenre", "value": "Comedy"}], "dayparts": [], "offair": [], "slots": [], "commercials": true, "callsign": "BCN"}
]}'

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) MODE=windows ;;
  *) if [ -e /etc/cableboxrig ]; then MODE=native; else MODE=chroot; fi ;;
esac

# =========================================================== Windows: pass on to the rig
if [ "$MODE" = windows ]; then
  wsl() { MSYS_NO_PATHCONV=1 WSL_UTF8=1 wsl.exe "$@"; }
  to_wsl() {   # G:/x/y or a relative path -> /mnt/g/x/y
    local p; p=$(cygpath -m "$(cd "$(dirname "$1")" && pwd)/$(basename "$1")")
    echo "/mnt/$(echo "${p:0:1}" | tr 'A-Z' 'a-z')${p:2}"
  }
  SELF=$(to_wsl "$0")
  RIG_HOME=$(cygpath -u "$RIG_HOME")
  mkdir -p "$RIG_HOME/snapshots"
  WIN_DISK=$(cygpath -w "$RIG_DISK")
  exists() { wsl -l -q | tr -d '\r' | grep -qx "$DISTRO"; }
  run() { wsl -d "$DISTRO" -u root --cd "$(cygpath -m "$PWD")" -e bash "$SELF" "$@"; }
  latest_snapshot() { ls -t "$RIG_HOME"/snapshots/*.tar 2>/dev/null | head -1; }
  import() {   # import TAR as the rig
    mkdir -p "$(cygpath -u "$RIG_DISK")"
    echo "Importing $1 as $DISTRO ($WIN_DISK)..."
    wsl --import "$DISTRO" "$WIN_DISK" "$(cygpath -w "$1")" --version 2
  }
  build() {
    # debootstrap in the builder distro, then make that tree a distro of its own
    local tar="$RIG_HOME/rootfs-build.tar"
    echo "Building the rig in WSL distro '$BUILDER' (about 10 minutes)..."
    wsl -d "$BUILDER" -u root -e env KODI_CHROOT=/var/tmp/cableboxrig-build \
      bash "$SELF" package "$(to_wsl "$tar")"
    import "$tar"
    rm -f "$tar"
    wsl -d "$BUILDER" -u root -e rm -rf /var/tmp/cableboxrig-build
  }
  case "${1:-}" in
    ensure)
      t0=$(date +%s)
      if ! exists; then
        s=$(latest_snapshot)
        if [ -n "$s" ]; then import "$s"; else build; fi
      fi
      rc=0; run ensure || rc=$?
      if [ $rc -eq 3 ]; then
        echo "The rig is broken: replacing it."
        wsl --unregister "$DISTRO"
        s=$(latest_snapshot)
        if [ -n "$s" ]; then import "$s"; else build; fi
        rc=0; run ensure || rc=$?
      fi
      echo "ensure: $(( $(date +%s) - t0 )) s"
      exit $rc ;;
    snapshot)
      exists || { echo "No $DISTRO distro"; exit 1; }
      mkdir -p "$RIG_HOME/snapshots"
      out="$RIG_HOME/snapshots/${2:-$DISTRO-$(date +%Y%m%d-%H%M)}.tar"
      run stop || true
      wsl --terminate "$DISTRO"
      wsl --export "$DISTRO" "$(cygpath -w "$out")"
      ls -l "$out" ;;
    restore)
      f=${2:?snapshot .tar}
      [ -f "$f" ] || f="$RIG_HOME/snapshots/$f"
      [ -f "$f" ] || { echo "No such snapshot: $2"; exit 1; }
      exists && wsl --unregister "$DISTRO"
      import "$f"
      run ensure ;;
    package)
      # migrate a chroot built in the builder distro: package KODI_CHROOT and import it
      tar="$RIG_HOME/rootfs-build.tar"
      wsl -d "$BUILDER" -u root -e env KODI_CHROOT="${2:-/opt/k21}" bash "$SELF" package "$(to_wsl "$tar")"
      exists && { echo "$DISTRO already exists; not replaced"; exit 1; }
      import "$tar"; rm -f "$tar"
      run ensure ;;
    status)
      if exists; then
        echo "rig: WSL distro $DISTRO, disk $WIN_DISK\\ext4.vhdx ($(wsl -l -v | tr -d '\r' | awk -v d="$DISTRO" '$0 ~ d {print $(NF-1)}'))"
        run status
      else
        echo "rig: no $DISTRO distro yet (run ensure)"
      fi
      echo "snapshots: $(ls "$RIG_HOME"/snapshots/*.tar 2>/dev/null | xargs -r -n1 basename | tr '\n' ' ')" ;;
    install)
      exists || { echo "No rig: run ensure first"; exit 1; }
      run install "$(to_wsl "${2:?zip file}")" ;;
    lineup)
      exists || { echo "No rig: run ensure first"; exit 1; }
      if [ -n "${2:-}" ]; then run lineup "$(to_wsl "$2")"; else run lineup; fi ;;
    shot|rec)
      exists || { echo "No rig: run ensure first"; exit 1; }
      c=$1; f=${2:-shot.png}; shift; shift || true
      run "$c" "$(to_wsl "$f")" "$@" ;;
    "") sed -n '2,/^# CRLF-safe/p' "$0" | sed '$d'; exit 1 ;;
    *)
      exists || { echo "No rig: run ensure first"; exit 1; }
      run "$@" ;;
  esac
  exit
fi

# =========================================================== inside the rig (or a chroot)
if [ "$MODE" = native ]; then
  ROOT=""
  # WSLg sets PULSE_SERVER (and WAYLAND_DISPLAY, DISPLAY) for Windows' own sound and
  # screen: unset them, or Kodi and pactl talk to those instead of the rig's
  in_root() { bash -c "unset PULSE_SERVER WAYLAND_DISPLAY; export HOME=/root DISPLAY=:9 XDG_RUNTIME_DIR=/tmp/xdg; $1"; }
  mounts() { :; }
else
  ROOT=${KODI_CHROOT:-/opt/k21}
  in_root() { chroot "$ROOT" /bin/bash -c "unset PULSE_SERVER WAYLAND_DISPLAY; export HOME=/root DISPLAY=:9 XDG_RUNTIME_DIR=/tmp/xdg; $1"; }
  mounts() {
    for m in proc dev sys; do mountpoint -q "$ROOT/$m" || mount --bind "/$m" "$ROOT/$m"; done
    mountpoint -q "$ROOT/dev/pts" || mount -t devpts devpts "$ROOT/dev/pts"
    cp /etc/resolv.conf "$ROOT/etc/resolv.conf"
  }
fi
P=$ROOT/root/.kodi
DB=$P/userdata/Database

setup() {
  command -v debootstrap >/dev/null || { apt-get update -qq; apt-get install -y -qq debootstrap; }
  # debootstrap may not know the newest release yet; it uses the same script as gutsy
  [ -e /usr/share/debootstrap/scripts/resolute ] || ln -s gutsy /usr/share/debootstrap/scripts/resolute
  mkdir -p "$ROOT"
  debootstrap --variant=minbase --components=main,universe resolute "$ROOT" http://archive.ubuntu.com/ubuntu
  printf 'deb http://archive.ubuntu.com/ubuntu resolute main universe\ndeb http://archive.ubuntu.com/ubuntu resolute-updates main universe\n' \
    > "$ROOT/etc/apt/sources.list"
  mounts
  env | grep -i _proxy > "$ROOT/root/proxy.env" || true
  in_root 'export $(cat /root/proxy.env | xargs) DEBIAN_FRONTEND=noninteractive
    apt-get update -qq && apt-get install -y -qq --no-install-recommends kodi kodi-bin \
      kodi-eventclients-kodi-send xvfb xauth pulseaudio pulseaudio-utils ffmpeg sox \
      python3 python3-numpy sqlite3 x11-apps imagemagick unzip libgl1-mesa-dri dbus-x11 ca-certificates \
      libasound2-plugins procps fonts-dejavu-core'
  base_profile
  echo "Kodi: $(in_root 'dpkg-query -W -f=\${Version} kodi-bin')"
}

package() {
  # (WSL builder) the chroot as a tar that `wsl --import` turns into the rig distro
  local out=${1:?tar file}
  [ -x "$ROOT$KODI_BIN" ] || setup
  in_root 'pkill -x kodi.bin; pkill -x Xvfb; pkill -x pulseaudio; true'; sleep 1
  printf '[boot]\nsystemd=false\n[user]\ndefault=root\n[interop]\nappendWindowsPath=false\n' > "$ROOT/etc/wsl.conf"
  echo "CableBox 42 test rig (see .claude/kodi21-test-vm.sh)" > "$ROOT/etc/cableboxrig"
  for m in dev/pts dev sys proc; do mountpoint -q "$ROOT/$m" && umount -l "$ROOT/$m"; done
  mkdir -p "$(dirname "$out")"
  tar --numeric-owner -cpf "$out" -C "$ROOT" .
  ls -l "$out"
}

base_profile() {
  mkdir -p "$P/userdata" "$ROOT/root/test"
  echo '<advancedsettings version="1.0"><loglevel>1</loglevel></advancedsettings>' \
    > "$P/userdata/advancedsettings.xml"
}

# Written on every start, so an older rig picks up fixes without a new setup
write_start() {
  # ALSA's default device goes to PulseAudio (needs libasound2-plugins), so anything
  # that opens ALSA is heard on the null sink too
  printf 'pcm.!default { type pulse }\nctl.!default { type pulse }\n' > "$ROOT/etc/asound.conf"
  cat > "$ROOT/root/start.sh" <<'EOF'
#!/bin/bash
unset PULSE_SERVER WAYLAND_DISPLAY
export HOME=/root DISPLAY=:9 XDG_RUNTIME_DIR=/tmp/xdg
mkdir -p $XDG_RUNTIME_DIR /run/user/0; chmod 700 $XDG_RUNTIME_DIR /run/user/0
pkill -9 -x kodi.bin; pkill -9 -x Xvfb; pkill -9 -x pulseaudio; sleep 0.5
# WSLg mounts its own (read-only) X socket folder here: Xvfb needs a writable one
if mountpoint -q /tmp/.X11-unix; then umount -l /tmp/.X11-unix; fi
[ -L /tmp/.X11-unix ] && rm -f /tmp/.X11-unix
mkdir -p /tmp/.X11-unix; chmod 1777 /tmp/.X11-unix
rm -f /tmp/.X9-lock /tmp/.X11-unix/X9
# /tmp survives a WSL shutdown: a stale pid file makes PulseAudio think it's running
rm -rf $XDG_RUNTIME_DIR/pulse /root/.config/pulse/*-runtime
# setsid + nohup + no stdin: nothing dies when the shell (or WSL session) that ran this ends
setsid nohup Xvfb :9 -screen 0 1280x720x24 >/tmp/xvfb.log 2>&1 < /dev/null &
# a null sink: everything Kodi plays can be recorded from out.monitor
setsid nohup pulseaudio --exit-idle-time=-1 -n --load="module-null-sink sink_name=out rate=48000" \
  --load="module-native-protocol-unix" --load="module-always-sink" >/tmp/pa.log 2>&1 < /dev/null &
for i in $(seq 1 40); do [ -e /tmp/.X11-unix/X9 ] && pactl info >/dev/null 2>&1 && break; sleep 0.25; done
pactl set-default-sink out
setsid nohup /usr/lib/x86_64-linux-gnu/kodi/kodi.bin --standalone --windowing=x11 >/tmp/kodi.out 2>&1 < /dev/null &
EOF
  chmod +x "$ROOT/root/start.sh"
}

ping_kodi() {   # Kodi answers JSON-RPC (port 9090)
  in_root "python3 - <<'PY' 2>/dev/null
import json, socket
s = socket.create_connection(('127.0.0.1', 9090), 1)
s.sendall(json.dumps({'jsonrpc': '2.0', 'method': 'JSONRPC.Ping', 'id': 1}).encode())
assert b'pong' in s.recv(200)
PY"
}

running() { in_root 'pgrep -x kodi.bin && pgrep -x Xvfb && pgrep -x pulseaudio' >/dev/null && ping_kodi; }

start() {
  mounts; write_start; in_root '/root/start.sh'
  for i in $(seq 1 120); do ping_kodi && break; sleep 0.25; done
  if ping_kodi; then echo "Kodi running (pid $(in_root 'pgrep -x kodi.bin'))"; else echo "Kodi did not start: see /tmp/kodi.out"; return 1; fi
}

stop() {
  in_root 'kodi-send --action=Quit >/dev/null 2>&1; for i in $(seq 1 20); do pgrep -x kodi.bin >/dev/null || break; sleep 0.25; done
    pkill -9 -x kodi.bin; pkill -x Xvfb; pkill -x pulseaudio; true'
  echo "stopped"
}

healthy() {   # Kodi and the tools the rig needs are installed and intact
  [ -x "$ROOT$KODI_BIN" ] && in_root 'command -v Xvfb pulseaudio pactl kodi-send ffmpeg sqlite3 convert xwd unzip >/dev/null &&
    python3 -c "import numpy" && dpkg-query -W -f="\${Status}" kodi-bin | grep -q "ok installed"'
}

make_library() {
  # a small synthetic TV library: four shows with .nfo files, fanart, some logos and theme songs
  in_root 'set -e; L=/root/library/tv; rm -rf $L; mkdir -p $L
  mk() {  # folder, title, genre, studio, episodes, minutes, colour, logo(1/0), theme(1/0)
    local d="$L/$1"; mkdir -p "$d"
    printf "<tvshow><title>%s</title><genre>%s</genre><studio>%s</studio><plot>A test show.</plot></tvshow>\n" "$2" "$3" "$4" > "$d/tvshow.nfo"
    ffmpeg -loglevel error -y -f lavfi -i "color=c=$7:s=1280x720,drawtext=text=$1:fontsize=90:fontcolor=white:x=(w-tw)/2:y=(h-th)/2" -frames:v 1 "$d/fanart.jpg"
    [ "$8" = 1 ] && ffmpeg -loglevel error -y -f lavfi -i "color=c=black@0.0:s=800x310,format=rgba,drawtext=text=$1:fontsize=120:fontcolor=yellow:x=(w-tw)/2:y=(h-th)/2" -frames:v 1 "$d/clearlogo.png"
    [ "$9" = 1 ] && ffmpeg -loglevel error -y -f lavfi -i "sine=frequency=440:duration=20" -f lavfi -i "sine=frequency=660:duration=20" -filter_complex amix=inputs=2 -ac 2 -b:a 96k "$d/theme.mp3"
    for e in $(seq 1 $5); do
      local f="$d/$1 S01E0$e"
      ffmpeg -loglevel error -y -f lavfi -i "testsrc=s=320x240:r=10:d=$(( $6 * 60 ))" -f lavfi -i "sine=frequency=$(( 200 + e * 50 )):duration=$(( $6 * 60 ))" \
        -c:v libx264 -preset ultrafast -crf 40 -c:a aac -b:a 32k "$f.mp4"
      printf "<episodedetails><title>%s episode %d</title><season>1</season><episode>%d</episode><plot>The gang tries something new in episode %d.</plot></episodedetails>\n" "$2" $e $e $e > "$f.nfo"
    done
  }
  mk "Seinfeld" "Seinfeld" "Comedy" "NBC" 4 22 navy 1 1
  mk "Mr. Bean" "Mr. Bean" "Comedy" "ITV" 3 24 darkgreen 0 1
  mk "Star Trek TNG" "Star Trek: The Next Generation" "Science Fiction" "Syndication" 3 44 darkred 1 0
  mk "Friends" "Friends" "Comedy" "NBC" 4 22 purple 1 1
  echo "test library: $(du -sh $L | cut -f1)"'
  make_ads
}

make_ads() {
  # commercials (15 and 30 s): without them breaks have no room and programmes no mid-show breaks
  in_root 'set -e; A=/root/library/ads; rm -rf $A; mkdir -p $A
  for i in 1 2 3 4 5 6 7 8; do
    d=$(( i % 2 ? 30 : 15 )); c=$(echo orange teal olive maroon steelblue sienna slategray indigo | cut -d" " -f$i)
    ffmpeg -loglevel error -y -f lavfi -i "color=c=$c:s=320x240:r=10:d=$d,drawtext=text=Ad $i:fontsize=60:fontcolor=white:x=(w-tw)/2:y=(h-th)/2" \
      -f lavfi -i "sine=frequency=$(( 500 + i * 40 )):duration=$d" -c:v libx264 -preset ultrafast -crf 40 -c:a aac -b:a 32k "$A/Ad $i.mp4"
  done
  echo "commercials: $(ls $A | wc -l) in $A"'
}

# CableBox's own settings (userdata/addon_data/script.cablebox42/settings.xml), with
# Kodi stopped so it doesn't write its copy over them; Kodi is started again after
set_settings() {
  local was=0; running && was=1
  stop >/dev/null
  mkdir -p "$P/userdata/addon_data/$ADDON"
  in_root "python3 - $(printf '%q ' "$@") <<'PY'
import re, sys, html
p = '/root/.kodi/userdata/addon_data/$ADDON/settings.xml'
try:
    t = open(p, encoding='utf-8').read()
except OSError:
    t = '<settings version=\"2\">\n</settings>\n'
for a in sys.argv[1:]:
    k, v = a.split('=', 1)
    t = re.sub(r'\s*<setting id=\"%s\"[^>]*?(/>|>.*?</setting>)' % re.escape(k), '', t)
    t = t.replace('</settings>', '    <setting id=\"%s\">%s</setting>\n</settings>' % (k, html.escape(v)))
    print('setting %s = %s' % (k, v))
open(p, 'w', encoding='utf-8').write(t)
PY"
  [ $was = 1 ] && start >/dev/null
  return 0
}

tvshows() { in_root "sqlite3 /root/.kodi/userdata/Database/$(basename "$(ls "$DB"/MyVideos*.db | tail -1)") 'select count(*) from tvshow;'" 2>/dev/null || echo 0; }

scan() {
  # registers /root/library/tv as a TV-show source read by Kodi's own NFO scraper
  # (metadata.local, offline) and scans it; every show folder needs a tvshow.nfo
  # with <title>, <genre> and <studio>, every episode an .nfo with <season>/<episode>
  mounts
  ls "$DB"/MyVideos*.db >/dev/null 2>&1 || start          # Kodi makes its databases on first start
  stop >/dev/null
  printf '%s\n' '<sources><video><default pathversion="1"></default><source><name>TV</name><path pathversion="1">/root/library/tv/</path><allowsharing>true</allowsharing></source></video></sources>' \
    > "$P/userdata/sources.xml"
  local db; db=$(basename "$(ls "$DB"/MyVideos*.db | tail -1)")
  in_root "sqlite3 /root/.kodi/userdata/Database/$db \"delete from path where strPath='/root/library/tv/'; \
    insert into path (strPath, strContent, strScraper, scanRecursive, useFolderNames, strSettings, noUpdate, exclude) \
    values ('/root/library/tv/', 'tvshows', 'metadata.local', 0, 0, '', 0, 0);\""
  start
  in_root "kodi-send --action='UpdateLibrary(video,/root/library/tv/)' >/dev/null"
  for i in $(seq 1 60); do [ "$(tvshows)" -ge 4 ] && break; sleep 1; done
  sleep 2
  echo "TV shows in library: $(tvshows)"
}

lineup() {   # lineup [FILE.json]: the test lineup (or your own channels.json); schedules start afresh
  local d=$P/userdata/addon_data/$ADDON
  [ -d "$ROOT/root/library/ads" ] || make_ads
  set_settings commercials_path=/root/library/ads/
  local was=0; running && was=1
  stop >/dev/null
  mkdir -p "$d"
  if [ -n "${1:-}" ]; then cp "$1" "$d/channels.json"; else printf '%s\n' "$SEED_LINEUP" > "$d/channels.json"; fi
  rm -rf "$d/schedules" "$d/series.json"
  [ $was = 1 ] && start >/dev/null
  echo "lineup: $(in_root "python3 -c \"import json; print(', '.join('%d %s' % (c['number'], c['name']) for c in json.load(open('/root/.kodi/userdata/addon_data/$ADDON/channels.json'))['channels']))\"")"
}

ensure() {
  healthy || { echo "rig broken: Kodi or a tool it needs is missing"; exit 3; }
  [ -e "$P/userdata/advancedsettings.xml" ] || base_profile
  running || start
  if [ ! -d "$ROOT/root/library/tv/Friends" ]; then make_library; scan
  elif [ "$(tvshows)" -lt 4 ]; then scan; fi
  [ -d "$ROOT/root/library/ads" ] || make_ads
  status
}

status() {
  local v="not installed"
  [ -f "$P/addons/$ADDON/addon.xml" ] && v=$(grep -o 'version="[^"]*"' "$P/addons/$ADDON/addon.xml" | sed -n 2p)
  echo "mode: $MODE${ROOT:+ ($ROOT)}; Kodi $(in_root 'dpkg-query -W -f=\${Version} kodi-bin' 2>/dev/null)"
  if running; then echo "running: Kodi pid $(in_root 'pgrep -x kodi.bin'), answers JSON-RPC"; else echo "running: no"; fi
  echo "CableBox: $v; TV shows in library: $(tvshows); lineup: $([ -f "$P/userdata/addon_data/$ADDON/channels.json" ] && echo yes || echo none)"
}

reset_profile() {
  stop >/dev/null
  rm -rf "$P" "$ROOT/root/library" "$ROOT/root/test"
  base_profile
  make_library
  scan
  echo "Fresh Kodi profile and test library. CableBox is not installed: run install ZIP (and lineup)."
}

install_zip() {
  local zip; zip=$(readlink -f "${1:?zip file}")
  mounts
  ls "$DB"/Addons*.db >/dev/null 2>&1 || start          # Kodi makes its databases on first start
  stop >/dev/null
  local dir="$P/addons"
  mkdir -p "$dir" "$ROOT/root/test"
  [ -d "$dir/$ADDON" ] && mv "$dir/$ADDON" "$ROOT/root/test/old-$ADDON-$(date +%s)"
  (cd "$dir" && unzip -q "$zip")
  # Kodi installs add-ons copied in by hand as disabled: enable them in its database
  in_root "sqlite3 /root/.kodi/userdata/Database/$(basename "$(ls "$DB"/Addons*.db | tail -1)") \
    \"insert or ignore into installed (addonID, enabled, installDate) values ('$ADDON', 1, datetime('now')); \
      update installed set enabled=1, disabledReason=0, origin='b6a50484-93a0-4afb-a01c-8d17e059feda' where addonID='$ADDON';\""
  start
  echo "installed $(basename "$zip"): $(grep -o 'version="[^"]*"' "$dir/$ADDON/addon.xml" | sed -n 2p)"
}

send() {
  local a
  for a in "$@"; do
    if [[ $a =~ ^[0-9.]+$ ]]; then sleep "$a"; else in_root "kodi-send --action='$a' >/dev/null"; fi
  done
}

shot() {
  in_root 'xwd -root -silent -display :9 | convert xwd:- -resize 60% /root/test/shot.png'
  cp "$ROOT/root/test/shot.png" "${1:-shot.png}"
}

rec() {   # rec FILE.mp4 SECS [actions...]: 10 fps 640x360 with the null sink's sound
  local out=${1:?file.mp4} secs=${2:?seconds}; shift 2
  in_root "ffmpeg -loglevel error -y -f x11grab -framerate 10 -video_size 1280x720 -i :9 -f pulse -i out.monitor \
    -t $secs -vf scale=640:360 -c:v libx264 -preset ultrafast -c:a aac /root/test/rec.mp4" &
  sleep 1.5
  send "$@"
  wait
  cp "$ROOT/root/test/rec.mp4" "$out"
}

zap() {
  local n=${1:-30} iv=${2:-3}
  local log=$P/temp/kodi.log l0
  l0=$(wc -l < "$log")
  in_root "kodi-send --action='RunScript($ADDON,watch,3)' >/dev/null"; sleep 12
  local pid; pid=$(in_root 'pgrep -x kodi.bin')
  echo "start: threads=$(ls /proc/$pid/task | wc -l) rssMB=$(( $(awk '/VmRSS/{print $2}' /proc/$pid/status) / 1024 ))"
  for i in $(seq 1 "$n"); do
    if [ $((i % 7)) -eq 0 ]; then in_root "kodi-send --action=Down >/dev/null"; else in_root "kodi-send --action=Up >/dev/null"; fi
    sleep "$iv"
  done
  sleep 5
  echo "end:   threads=$(ls /proc/$pid/task | wc -l) rssMB=$(( $(awk '/VmRSS/{print $2}' /proc/$pid/status) / 1024 ))"
  local t; t=$(mktemp); tail -n +"$l0" "$log" > "$t"
  echo "audio renderer timeouts: $(grep -c 'AddPacketsRenderer - timeout' "$t" || true)"
  echo "audio drain failures:    $(grep -c 'DrainSink - failed' "$t" || true)"
  echo "sink open failures:      $(grep -c 'Unable to open the requested channel layout' "$t" || true)"
  echo "python tracebacks:       $(grep -c 'Traceback' "$t" || true)"
  echo "(a virtual sound card logs 'Sink Timer expired' on its own; ignore those)"
  rm -f "$t"
}

case "${1:-}" in
  setup) setup ;;
  package) package "${2:?tar file}" ;;
  ensure) ensure ;;
  start) start ;;
  stop) stop ;;
  status) status ;;
  install) install_zip "${2:?zip file}" ;;
  reset-profile) reset_profile ;;
  lineup) lineup "${2:-}" ;;
  setting) shift; set_settings "$@" ;;
  ads) make_ads ;;
  scan) scan ;;
  library) make_library; scan ;;
  zap) zap "${2:-30}" "${3:-3}" ;;
  shot) shot "${2:-shot.png}" ;;
  rec) shift; rec "$@" ;;
  send) shift; send "$@" ;;
  sh) shift; in_root "$*" ;;
  log) grep -E "$ADDON|cablebox|AESink|ActiveAE|Traceback" "$P/temp/kodi.log" | tail -"${2:-60}" ;;
  *) sed -n '2,/^# CRLF-safe/p' "$0" | sed '$d'; exit 1 ;;
esac
