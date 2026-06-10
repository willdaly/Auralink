#!/usr/bin/env python3
"""Editable heart-rate zone configuration for live style mapping.

Team notes:
- This file is intended as the safe place to tune zone boundaries and prompts.
- Keep tuples in ascending BPM order as: (low_inclusive, high_exclusive, label, prompt).
- Keep `{bpm}` in each prompt; it is filled at runtime.

Prompt design (musical version):
- Every zone keeps a "deep soft heartbeat pulse drum" so the kick still reads as
  the heart and the live drum-onset tempo still lands on something musical.
- All zones share one key (D dorian) so rising heart rate feels like one evolving
  piece building in intensity, not four unrelated tracks.
- Harmony, melody and motion can ONLY enter through this text (MRT2's only inputs
  here are style text + the drum pulse), so each zone names chords, a motif, and
  movement instead of "sparse / drone / empty".
"""

from __future__ import annotations

HR_ZONES = [
    (
        0,
        98,
        "calm",
        "warm cinematic neo-classical in D dorian, a deep soft heartbeat pulse "
        "drum, gentle felt piano playing a simple memorable 4-note motif, warm "
        "sustained string pads moving slowly through Dm - F - C - G, soft analog "
        "synth bloom, tender and spacious but musical, {bpm} BPM",
    ),
    (
        98,
        105,
        "rest",
        "warm cinematic post-rock in D dorian, a deep soft heartbeat pulse drum, "
        "felt piano motif answered by a slow plucked synth arpeggio, warm strings "
        "swelling through Dm - F - C - G, soft sub bass following the root, "
        "flowing and emotional, gentle forward motion, {bpm} BPM",
    ),
    (
        105,
        112,
        "active",
        "uplifting cinematic electronic in D dorian, a steady deep heartbeat pulse "
        "drum, bright plucked synth arpeggio over warm evolving pads, piano motif "
        "rising, strings building through Dm - F - C - G, melodic sub bass, "
        "focused momentum and warmth, {bpm} BPM",
    ),
    (
        112,
        999,
        "peak",
        "epic cinematic electronic in D dorian, a strong deep heartbeat pulse drum, "
        "soaring lead synth carrying the main melody, full driving arpeggios, "
        "dramatic swelling strings and brass over Dm - F - C - G, powerful melodic "
        "bass, euphoric and emotional climax, {bpm} BPM",
    ),
]
