"""Log Kodi player notifications (JSON-RPC, port 9090) with arrival times, inside the rig:
    python3 notes.py SECS OUT.tsv
OnStop(end=true) -> next OnAVStart is the switch time."""
import json, socket, sys, time
secs, out = float(sys.argv[1]), sys.argv[2]
s = socket.create_connection(("127.0.0.1", 9090))
s.settimeout(0.5)
buf, end, f = b"", time.time() + secs, open(out, "w")
dec = json.JSONDecoder()
while time.time() < end:
    try:
        d = s.recv(65536)
    except socket.timeout:
        continue
    now = time.time()
    buf += d
    txt = buf.decode("utf-8", "ignore")
    i = 0
    while True:
        txt2 = txt[i:].lstrip()
        if not txt2:
            i = len(txt); break
        try:
            obj, n = dec.raw_decode(txt2)
        except ValueError:
            break
        i = len(txt) - len(txt2) + n
        m = obj.get("method", "")
        if m.startswith("Player."):
            p = obj.get("params", {}).get("data", {})
            item = p.get("item", {})
            f.write("%.3f\t%s\t%s\t%s\n" % (now, m, json.dumps(p.get("end")), item.get("file") or item.get("title") or item.get("type")))
            f.flush()
    buf = txt[i:].encode()
