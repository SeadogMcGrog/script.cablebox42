"""Show breaks item by item, and how far programme parts start from their planned point
(inside the rig): python3 breaks.py CHANNEL_ID [N_BREAKS]"""
import json
import os
import sys
import time

D = "/root/.kodi/userdata/addon_data/script.cablebox42/schedules"
d = json.load(open(os.path.join(D, sys.argv[1] + ".json")))
n = int(sys.argv[2]) if len(sys.argv) > 2 else 4
ents, blocks = d["entries"], d["blocks"]
shown, brk = 0, []
for e in ents:
    if e["k"] == "show":
        if brk:
            print("  break %.2f s: %s" % (brk[-1]["e"] - brk[0]["s"], "  ".join(
                "%s%s %.2f" % (b["k"], ("(" + os.path.basename(b["p"])[:10] + ")") if b.get("p") else
                               ("(" + b.get("sub", "") + ")" if b.get("sub") else ""), b["e"] - b["s"]) for b in brk)))
            brk = []
            shown += 1
            if shown >= n:
                break
        print("%s show o=%7.2f len %7.2f  %s" % (time.strftime("%H:%M:%S", time.localtime(e["s"])),
                                                e.get("o", 0), e["e"] - e["s"], e.get("t")))
    else:
        brk.append(e)
# programme starts vs guide (block) times
off = []
for b in blocks:
    first = [e for e in ents if e["k"] == "show" and abs(e["s"] - b["s"]) < 5]
    if first:
        off.append(first[0]["s"] - b["s"])
print("first part vs guide time: %d blocks, max early %.2f s, max late %.2f s" % (
    len(off), -min(off + [0]), max(off + [0])))
