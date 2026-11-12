"""Test zip without the zip tool (Git Bash has none):
    python .claude/tools/build_zip.py OUT.zip
Same layout as the release checklist: top folder script.cablebox42/, no dot-folders,
no __pycache__ or .pyc."""
import os
import sys
import zipfile

repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
out = os.path.abspath(sys.argv[1])
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__pycache__")
        for f in sorted(files):
            if f.startswith(".") or f.endswith(".pyc"):
                continue
            full = os.path.join(root, f)
            z.write(full, os.path.join("script.cablebox42", os.path.relpath(full, repo)).replace(os.sep, "/"))
print(out)
