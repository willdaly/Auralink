#!/usr/bin/env python3
"""Soak test: drive the real generation loop and watch MLX memory.

Reproduces the long-run workload that crashed with
"[metal::malloc] Resource limit (...) exceeded" and confirms the per-chunk
mx.clear_cache() keeps the buffer cache bounded. Headless (no audio device).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow `python scripts/soak_mlx_cache.py` from the repo root: put the repo
# root (this file's parent's parent) on the path so `auralink` imports.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mlx.core as mx

from auralink.auralink import hr_to_style
from auralink.engine import MagentaEngine

N_CHUNKS = int(sys.argv[1]) if len(sys.argv) > 1 else 250
MB = 1 << 20

eng = MagentaEngine()
eng.load_model()
eng.set_style(hr_to_style(60)[1], label="soak")
eng._ensure_thread_stream()
eng.warmup_pulse()

print(f"soak: {N_CHUNKS} chunks (~{N_CHUNKS}s of audio)")
for i in range(1, N_CHUNKS + 1):
    try:
        eng._generate_chunk()
        eng._release_mlx_cache()
    except Exception as exc:
        print(f"FAIL at chunk {i}: {exc}")
        raise SystemExit(1)
    if i % 25 == 0 or i == 1:
        print(
            f"chunk {i:4d}  active={mx.get_active_memory()/MB:7.1f}MB  "
            f"cache={mx.get_cache_memory()/MB:7.1f}MB  "
            f"peak={mx.get_peak_memory()/MB:7.1f}MB"
        )
print(f"PASS: survived {N_CHUNKS} chunks with no Metal resource error")
