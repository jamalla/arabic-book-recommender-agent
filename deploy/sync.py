"""Keep this folder's copy of the shipped agent equal to the course code.

    python deploy/sync.py           # copy changed bookrec/*.py and data/catalog.csv into deploy/
    python deploy/sync.py --check   # exit 1 if deploy/ is out of date (run before building the image)

deploy/ is self-contained on purpose (build and run it without the course files), so the agent
code exists twice; this script keeps the copy honest.
"""
import filecmp
import shutil
import sys
from pathlib import Path

DEPLOY = Path(__file__).resolve().parent
ROOT = DEPLOY.parent
SHARED = [
    "bookrec/__init__.py", "bookrec/agent.py", "bookrec/agent_langgraph.py",
    "bookrec/factory.py", "bookrec/search.py", "data/catalog.csv",
]


def main(check=False):
    stale = [f for f in SHARED if not (DEPLOY / f).exists() or not filecmp.cmp(ROOT / f, DEPLOY / f, shallow=False)]
    if check:
        print(f"out of date: {', '.join(stale)}" if stale else "deploy/ is up to date")
        return 1 if stale else 0
    for f in stale:
        (DEPLOY / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, DEPLOY / f)
        print("copied", f)
    return 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
