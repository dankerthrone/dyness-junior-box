"""Pytest setup: make the HA-free dylink package importable without HA.

The integration's dylink/ module (frames, parser, server) has NO Home Assistant
dependency, so unit tests run in a plain Python env. We add the package dir to
sys.path so `import dylink` resolves, exactly like HA does for its components.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1] / "custom_components" / "dyness_junior"
sys.path.insert(0, str(_PKG))

# Fictional 16-char serial for frame tests — never a real device SN.
TEST_SERIAL = "0123456789ABCDEF"