"""Locate the pinned upstream framework (anthropic-experimental/agentic-misalignment)."""
import os, sys, subprocess
from pathlib import Path

PINNED = "ea0630e1a3eaae7f9f9740fd2703229d3854ccda"

def upstream_root() -> Path:
    p = Path(os.environ.get("AM_UPSTREAM", Path(__file__).resolve().parents[3] / "related_repos/agentic-misalignment"))
    if not (p / "classifiers").exists():
        raise FileNotFoundError(f"upstream repo not found at {p}; set AM_UPSTREAM")
    return p

def upstream_commit() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(upstream_root()), "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"

def upstream_dirty() -> bool:
    try:
        return bool(subprocess.check_output(["git", "-C", str(upstream_root()), "status", "--porcelain"], text=True).strip())
    except Exception:
        return True

def check_pinned() -> str | None:
    """Return a problem description if the upstream checkout is not the pinned, clean commit."""
    c = upstream_commit()
    if c != PINNED:
        return f"upstream is at {c[:12]}, pinned {PINNED[:12]}"
    if upstream_dirty():
        return "upstream working tree is dirty"
    return None

def import_upstream():
    root = upstream_root()
    for p in (root, root / "templates", root / "scripts"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
