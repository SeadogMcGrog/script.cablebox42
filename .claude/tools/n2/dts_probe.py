"""Which starts of a DTS file make Kodi misread the first frame (N2, the 18 Nov wedge).

    python .claude/tools/n2/dts_probe.py NAME FILE MODE POS...

MODE resume: Player.Open with resume at POS (how CableBox's StartOffset tunes in);
MODE seek: Player.Open at 0, then Player.Seek to POS once playing;
MODE zero: Player.Open at 0 only (POS ignored).
Per start: the SyncDTS line(s) and layout errors in 3 s.  A wedge is cleared by restarting
Kodi (n2 restart) before the next start.  Positions are whole seconds or s.mmm.  Results
appended to n2/logs/dts/NAME.tsv.  Changes no setting."""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import n2  # noqa: E402
import dts_starts as D  # noqa: E402


def tobj(pos):
    ms = int(round(pos * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return {"hours": h, "minutes": m, "seconds": s, "milliseconds": ms}


def restart():
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "n2.py"), "restart"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    for _i in range(60):
        try:
            if n2.rpc("JSONRPC.Ping", timeout=3) == "pong":
                time.sleep(3)
                return
        except Exception:
            pass
        time.sleep(1)


def one(f, mode, pos):
    start = D.log_size()
    if mode == "resume":
        n2.rpc("Player.Open", {"item": {"file": f}, "options": {"resume": tobj(pos)}}, timeout=15)
    else:
        n2.rpc("Player.Open", {"item": {"file": f}}, timeout=15)
        if mode == "seek":
            for _i in range(50):
                time.sleep(0.2)
                if "SyncDTS" in D.log_since(start):
                    break
            time.sleep(0.5)
            pl = n2.rpc("Player.GetActivePlayers")
            n2.rpc("Player.Seek", {"playerid": pl[0]["playerid"], "value": {"time": tobj(pos)}}, timeout=15)
    time.sleep(3.0)
    new = D.log_since(start)
    syncs = [m.groups() for m in D.SYNC.finditer(new)]
    errs = new.count(D.WEDGE)
    try:
        D.stop()
    except Exception:
        pass
    return syncs, errs


def main():
    name, f, mode = sys.argv[1], sys.argv[2], sys.argv[3]
    out = open(os.path.join(n2.ROOT, "logs", "dts", name + ".tsv"), "a")
    for p in [float(x) for x in sys.argv[4:]]:
        syncs, errs = one(f, mode, p)
        desc = "; ".join("%s %sch %s fs%s" % g for g in syncs)
        print("%-6s %9.3f  %-70s layout errors %d%s" % (mode, p, desc[:70], errs, "  <- WEDGED" if errs else ""))
        out.write("%s\t%s\t%.3f\t%s\t%d\n" % (os.path.basename(f), mode, p, desc, errs))
        out.flush()
        if errs:
            restart()
            time.sleep(2)


if __name__ == "__main__":
    main()
