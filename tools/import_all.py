# tools/import_all.py
import pkgutil, importlib, sys, traceback
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

errors = 0
for mod in pkgutil.walk_packages([str(root)], onerror=lambda x: None):
    name = mod.name
    # skip common noise; tweak as needed
    if any(part in name for part in (".venv", "venv", "tests")):
        continue
    try:
        importlib.import_module(name)
    except Exception as e:
        errors += 1
        print(f"[IMPORT FAIL] {name}: {e}")
        traceback.print_exc()

print(f"\nImport scan complete. Errors: {errors}")
