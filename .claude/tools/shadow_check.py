"""A function's local variable that has the name of an imported module hides that
module in the whole function: `promos = []` in tv.fill_guide made every
`promos.fit_font(...)` there fail (an empty guide in retro14).  pyflakes doesn't
catch it.  Lists every function that both shadows a module and uses it (FAIL),
and the harmless ones (shadowed but the module isn't used there) with -v.

    python .claude/tools/shadow_check.py [-v]
"""
import ast
import glob
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
bad, quiet = [], []
for f in sorted(glob.glob(os.path.join(REPO, "resources", "lib", "*.py"))) + [os.path.join(REPO, "default.py"),
                                                                              os.path.join(REPO, "service.py")]:
    tree = ast.parse(open(f, encoding="utf-8").read())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                mods.add(a.asname or a.name.split(".")[0])
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        local = set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                local.add(n.id)
            elif isinstance(n, ast.arg):
                local.add(n.arg)
        for m in sorted(local & mods):
            used = sorted({n.lineno for n in ast.walk(fn) if isinstance(n, ast.Attribute)
                           and isinstance(n.value, ast.Name) and n.value.id == m})
            line = "%s:%d %s(): local '%s' hides the module" % (os.path.basename(f), fn.lineno,
                                                                getattr(fn, "name", "lambda"), m)
            (bad if used else quiet).append(line + (" - and uses it at %s" % used if used else ""))
if "-v" in sys.argv:
    for q in quiet:
        print("  ok", q)
for b in bad:
    print("FAIL", b)
print("PASS" if not bad else "FAIL")
sys.exit(1 if bad else 0)
