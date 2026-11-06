#!/bin/bash
# Headless Kodi 21 test rig for CableBox 42 (not shipped with the add-on).
#
# Builds an Ubuntu 26.04 ("resolute") chroot with Kodi 21.3, Xvfb and a PulseAudio
# null sink whose output can be recorded, then installs and exercises the add-on.
# Needs Linux, root, ~3 GB of disk and network access to archive.ubuntu.com.
# Audio timing in this rig is not hardware-accurate: use it to catch errors and
# regressions; the CoreELEC box has the final word.
#
#   sudo .claude/kodi21-test-vm.sh setup             # once: build the chroot (~10 min)
#   sudo .claude/kodi21-test-vm.sh start             # start Xvfb + PulseAudio + Kodi
#   sudo .claude/kodi21-test-vm.sh install ZIP       # install a build, enable it, restart Kodi
#   sudo .claude/kodi21-test-vm.sh zap [N] [SECS]    # TV on, flip N channels, count audio errors
#   sudo .claude/kodi21-test-vm.sh shot FILE.png     # screenshot (look at it to check UI)
#   sudo .claude/kodi21-test-vm.sh send ACTION       # send a Kodi action, e.g. Down, Select, Back
#   sudo .claude/kodi21-test-vm.sh scan              # add /root/library/tv to Kodi's library
#   sudo .claude/kodi21-test-vm.sh log               # tail CableBox and audio lines of kodi.log
#
# Kodi needs a library for CableBox to build channels: put videos (with .nfo files and
# genres) under $ROOT/root/library/tv and run `scan`, or copy a channels.json into
# $ROOT/root/.kodi/userdata/addon_data/script.cablebox42/.
set -euo pipefail
ROOT=${KODI_CHROOT:-/opt/k21}
ADDON=script.cablebox42

in_root() { chroot "$ROOT" /bin/bash -c "export HOME=/root DISPLAY=:9 XDG_RUNTIME_DIR=/tmp/xdg; $1"; }

mounts() {
  for m in proc dev sys; do mountpoint -q "$ROOT/$m" || mount --bind "/$m" "$ROOT/$m"; done
  mountpoint -q "$ROOT/dev/pts" || mount -t devpts devpts "$ROOT/dev/pts"
  cp /etc/resolv.conf "$ROOT/etc/resolv.conf"
}

setup() {
  command -v debootstrap >/dev/null || apt-get install -y -qq debootstrap
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
      python3 python3-numpy sqlite3 x11-apps imagemagick unzip libgl1-mesa-dri dbus-x11 ca-certificates'
  cat > "$ROOT/root/start.sh" <<'EOF'
#!/bin/bash
export HOME=/root DISPLAY=:9 XDG_RUNTIME_DIR=/tmp/xdg
mkdir -p $XDG_RUNTIME_DIR; chmod 700 $XDG_RUNTIME_DIR
pkill -9 -x kodi.bin; pkill -9 Xvfb; pkill -9 pulseaudio; sleep 1
rm -f /tmp/.X9-lock /tmp/.X11-unix/X9
Xvfb :9 -screen 0 1280x720x24 >/tmp/xvfb.log 2>&1 &
sleep 2
# a null sink: everything Kodi plays can be recorded from out.monitor
pulseaudio --daemonize=yes --exit-idle-time=-1 -n --load="module-null-sink sink_name=out rate=48000" \
  --load="module-native-protocol-unix" --load="module-always-sink" >/tmp/pa.log 2>&1
sleep 1; pactl set-default-sink out
/usr/lib/x86_64-linux-gnu/kodi/kodi.bin --standalone --windowing=x11 >/tmp/kodi.out 2>&1 &
EOF
  chmod +x "$ROOT/root/start.sh"
  mkdir -p "$ROOT/root/.kodi/userdata" "$ROOT/root/test"
  echo '<advancedsettings version="1.0"><loglevel>1</loglevel></advancedsettings>' \
    > "$ROOT/root/.kodi/userdata/advancedsettings.xml"
  echo "Kodi: $(in_root 'dpkg-query -W -f=\${Version} kodi-bin')"
}

start() { mounts; in_root '/root/start.sh'; sleep 25; echo "Kodi running: $(in_root 'pgrep -x kodi.bin || echo no')"; }

install_zip() {
  local zip=$1
  mounts
  in_root 'pkill -x kodi.bin || true'; sleep 2
  # Kodi creates its databases on first start
  ls "$ROOT"/root/.kodi/userdata/Database/Addons*.db >/dev/null 2>&1 || { start; in_root 'pkill -x kodi.bin || true'; sleep 2; }
  local dir="$ROOT/root/.kodi/addons"
  mkdir -p "$dir"
  [ -d "$dir/$ADDON" ] && mv "$dir/$ADDON" "$ROOT/root/test/old-$ADDON-$(date +%s)"
  (cd "$dir" && unzip -q "$(readlink -f "$zip")")
  # Kodi installs add-ons copied in by hand as disabled: enable them in its database
  local db
  db=$(ls "$ROOT"/root/.kodi/userdata/Database/Addons*.db 2>/dev/null | tail -1 || true)
  if [ -n "$db" ]; then
    in_root "sqlite3 /root/.kodi/userdata/Database/$(basename "$db") \
      \"insert or ignore into installed (addonID, enabled, installDate) values ('$ADDON', 1, datetime('now')); \
        update installed set enabled=1, disabledReason=0, origin='b6a50484-93a0-4afb-a01c-8d17e059feda' where addonID='$ADDON';\""
  fi
  start
  grep -o "version=\"[0-9.]*\"" "$dir/$ADDON/addon.xml" | head -2 | tail -1
}

scan() {
  # registers /root/library/tv as a TV-show source read by Kodi's own NFO scraper
  # (metadata.local, offline) and scans it; every show folder needs a tvshow.nfo
  # with <title>, <genre> and <studio>, every episode an .nfo with <season>/<episode>
  mounts
  in_root 'pkill -x kodi.bin || true'; sleep 2
  printf '%s\n' '<sources><video><default pathversion="1"></default><source><name>TV</name><path pathversion="1">/root/library/tv/</path><allowsharing>true</allowsharing></source></video></sources>' \
    > "$ROOT/root/.kodi/userdata/sources.xml"
  local db; db=$(basename "$(ls "$ROOT"/root/.kodi/userdata/Database/MyVideos*.db | tail -1)")
  in_root "sqlite3 /root/.kodi/userdata/Database/$db \"delete from path where strPath='/root/library/tv/'; \
    insert into path (strPath, strContent, strScraper, scanRecursive, useFolderNames, strSettings, noUpdate, exclude) \
    values ('/root/library/tv/', 'tvshows', 'metadata.local', 0, 0, '', 0, 0);\""
  start
  in_root "kodi-send --action='UpdateLibrary(video,/root/library/tv/)' >/dev/null"
  sleep 20
  echo "TV shows in library: $(in_root "sqlite3 /root/.kodi/userdata/Database/$db 'select count(*) from tvshow;'")"
}

zap() {
  local n=${1:-30} iv=${2:-3}
  local log=$ROOT/root/.kodi/temp/kodi.log l0
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
  echo "(the VM's virtual sound card logs 'Sink Timer expired' on its own; ignore those)"
  rm -f "$t"
}

case "${1:-}" in
  setup) setup ;;
  start) start ;;
  install) install_zip "${2:?zip file}" ;;
  scan) scan ;;
  zap) zap "${2:-30}" "${3:-3}" ;;
  shot) in_root 'xwd -root -silent | convert xwd:- -resize 60% /root/test/shot.png'; cp "$ROOT/root/test/shot.png" "${2:-shot.png}" ;;
  send) in_root "kodi-send --action='${2:?action}' >/dev/null" ;;
  log) grep -E "$ADDON|cablebox|AESink|ActiveAE|Traceback" "$ROOT/root/.kodi/temp/kodi.log" | tail -60 ;;
  *) sed -n '2,25p' "$0"; exit 1 ;;
esac
