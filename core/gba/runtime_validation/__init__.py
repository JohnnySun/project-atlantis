"""Manifest-driven, fail-closed GBA ROM runtime validation."""

from .manifest import ManifestError, load_manifest
from .result import Report

__all__ = ["ManifestError", "Report", "load_manifest"]
