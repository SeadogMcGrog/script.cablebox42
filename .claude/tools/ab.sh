#!/bin/bash
# A/B two builds' planning from the same saved state (Git Bash, from the repo):
#   bash .claude/tools/ab.sh save                 # keep the current CableBox data as the start
#   bash .claude/tools/ab.sh run NAME ZIP [ID=VALUE...]   # restore it, set settings, install ZIP,
#                                                 # let the start-up refresh plan, keep the schedules as NAME
#   bash .claude/tools/ab.sh diff A B [CH_ID...]  # entries from the refresh point on: identical?
# AB_START=NAME runs from /root/test/NAME instead of the saved start.
# AB_IGNORE=t,sub compares entries without those keys (e.g. names only may differ).
# Every run pins the four defaults that changed in 1.2.0~defaults1 to their old values (OLD_DEFAULTS),
# so a build from before that compares with one after it; a run's own ID=VALUE wins. AB_NEW_DEFAULTS=1: no pin.
# Both runs must start within the same programme (refresh plans from the end of what's on air).
S=.claude/kodi21-test-vm.sh
D=/root/.kodi/userdata/addon_data/script.cablebox42
OLD_DEFAULTS="promos_on=false house_breaks=0 promo_extras=false summer_reruns=0"
case "$1" in
  save) bash $S sh "rm -rf /root/test/ab_start && cp -a $D /root/test/ab_start && echo saved" ;;
  run)
    name=$2; zip=$3; shift 3
    bash $S stop >/dev/null 2>&1
    bash $S sh "rm -rf $D && cp -a /root/test/${AB_START:-ab_start} $D && python3 -c \"
import json; f='$D/applied.json'; d=json.load(open(f)); d.pop('code', None); json.dump(d, open(f, 'w'))\""   # every run replans
    pin=$OLD_DEFAULTS; [ "${AB_NEW_DEFAULTS:-}" = 1 ] && pin=
    [ -n "$pin$*" ] && bash $S setting $pin "$@" | tail -1
    bash $S install "$zip" | tail -1
    bash $S sh "for i in \$(seq 1 30); do grep -q 'Refresh schedules' /root/.kodi/temp/kodi.log && break; sleep 1; done; \
      grep -E 'Schedules:|Refresh schedules' /root/.kodi/temp/kodi.log | tail -2 | cut -c1-150; \
      rm -rf /root/test/ab_$name && cp -a $D/schedules /root/test/ab_$name"
    ;;
  diff)
    a=$2; b=$3; shift 3
    bash $S sh "AB_IGNORE=$AB_IGNORE python3 - $a $b $* <<'PY'
import json, sys, glob, os, time
a, b = sys.argv[1], sys.argv[2]
chs = sys.argv[3:] or [os.path.basename(f)[:-5] for f in glob.glob('/root/test/ab_%s/*.json' % a)]
start = json.load(open('/root/test/ab_start/state.json')) if False else None
for ch in sorted(chs):
    A = json.load(open('/root/test/ab_%s/%s.json' % (a, ch)))['entries']
    B = json.load(open('/root/test/ab_%s/%s.json' % (b, ch)))['entries']
    t0 = time.time()
    ign = [k for k in os.environ.get('AB_IGNORE', '').split(',') if k]
    A = [{k: v for k, v in e.items() if k not in ign} for e in A if e['s'] >= t0]
    B = [{k: v for k, v in e.items() if k not in ign} for e in B if e['s'] >= t0]
    n = min(len(A), len(B))
    diff = [i for i in range(n) if A[i] != B[i]]
    print('%s: %d vs %d entries from %s, %d differ%s' % (ch, len(A), len(B), time.strftime('%H:%M', time.localtime(t0)),
          len(diff), (' - first: %s | %s' % (A[diff[0]], B[diff[0]])) if diff else ''))
PY"
    ;;
esac
