"""Dylink-Protokoll (TCP 5005) — lokale Dyness-Junior-Box-Anbindung.

Reverse engineered 2026-10-31 (siehe docs/ROADMAP.md). Enthält:
- frames_gen.py : generierte, byte-exakte Frame-Templates (Regenerator tools/gen_frames.py)
- frames.py     : bequeme Builder
- parser.py     : Telemetrie-/Register-Dekodierung (best-effort, experimentell)
- server.py     : asyncio-Server, der die Box lokal bedient (MITM-Ersatz der Cloud)
"""
from __future__ import annotations

from .frames import *  # noqa: F401,F403
from .server import DylinkServer  # noqa: F401