#!/usr/bin/env python3
"""Editable heart-rate zone configuration for live style mapping.

Team notes:
- This file is intended as the safe place to tune zone boundaries and prompts.
- Keep tuples in ascending BPM order as: (low_inclusive, high_exclusive, label, prompt).
- Keep `{bpm}` in each prompt; it is filled at runtime.
"""

from __future__ import annotations

HR_ZONES = [
    (
        0,
        98,
        "calm",
        "slow cinematic ambient, a single deep soft heartbeat pulse drum, "
        "warm sustained pads, gentle drone, sparse, lots of empty space, "
        "no hi-hats, no fast rhythm, no techno, calm and still, {bpm} BPM",
    ),
    (
        98,
        105,
        "rest",
        "calm cinematic ambient, one deep soft pulsing bass drum like a slow "
        "heartbeat, warm sustained strings, spacious, mellow, "
        "no hi-hats, no fast rhythm, no techno, restful, {bpm} BPM",
    ),
    (
        105,
        112,
        "active",
        "warm cinematic ambient with gentle weight, a steady deep heartbeat "
        "pulse drum, soft sustained bass, swelling pads, spacious, "
        "no hi-hats, no fast rhythm, no techno, focused and calm, {bpm} BPM",
    ),
    (
        112,
        999,
        "peak",
        "intense cinematic ambient, a strong deep heartbeat pulse drum, "
        "dramatic swelling strings, warm sustained bass, powerful but unhurried, "
        "no hi-hats, no fast rhythm, no techno, emotional, {bpm} BPM",
    ),
]
