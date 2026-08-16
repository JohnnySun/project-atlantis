#!/usr/bin/env python3
"""CLI wrapper for the source-safe M2.2 static pipeline analyzer."""

from __future__ import annotations

import argparse
from pathlib import Path

from m2_2_static import main as analyze_main


if __name__ == "__main__":
    raise SystemExit(analyze_main())
