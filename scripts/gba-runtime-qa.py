#!/usr/bin/env python3
"""Stable repository entry point for the GBA runtime-validation CLI."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))

from core.gba.runtime_validation.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
