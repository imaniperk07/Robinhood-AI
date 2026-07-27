"""Import every .py file in the repo (except app.py, which needs a real Streamlit
script-run context and isn't safe to plain-import) and fail loudly if any of them
raise on import. Catches missing dependencies and broken imports before they reach
a real deploy. Run from the repo root, locally or in CI:

    python .github/scripts/check_imports.py
"""
import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SKIP = {"app.py"}
SKIP_DIRS = {"venv", "node_modules", "__pycache__", ".git", ".github"}


def find_modules() -> list[str]:
    modules = []
    for path in sorted(REPO_ROOT.rglob("*.py")):
        if path.name in SKIP:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        relative = path.relative_to(REPO_ROOT).with_suffix("")
        modules.append(".".join(relative.parts))
    return modules


def main() -> int:
    sys.path.insert(0, str(REPO_ROOT))
    failures = []

    for module_name in find_modules():
        try:
            importlib.import_module(module_name)
        except Exception as e:
            failures.append((module_name, e))

    if failures:
        print(f"{len(failures)} module(s) failed to import:\n")
        for module_name, error in failures:
            print(f"  {module_name}: {error}")
        return 1

    print(f"All {len(find_modules())} modules imported successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
