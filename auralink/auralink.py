#!/usr/bin/env python3
"""Auralink runtime orchestration and heart-rate style mapping."""

from __future__ import annotations

import time

import numpy as np

from .engine import SAMPLE_RATE, MagentaEngine
from .heartbeat import HeartbeatSource
from .hr_zones import HR_ZONES


def hr_to_style(bpm: float) -> tuple[str, str]:
    """Map a heart rate to a (zone_label, magenta_prompt) with tempo filled in."""
    for low, high, label, prompt in HR_ZONES:
        if low <= bpm < high:
            return label, prompt.format(bpm=int(round(bpm)))
    label, prompt = HR_ZONES[-1][2], HR_ZONES[-1][3]
    return label, prompt.format(bpm=int(round(bpm)))


class Auralink:
    """Wires a heartbeat to Magenta RealTime 2; Magenta is the only sound source."""

    def __init__(
        self,
        engine: MagentaEngine,
        heart: HeartbeatSource,
        restyle_bpm_delta: float = 4.0,
    ) -> None:
        self.engine = engine
        self.heart = heart
        self.restyle_bpm_delta = restyle_bpm_delta
        self._current_zone = ""
        self._last_bpm = -1.0

    def update_style_for_hr(self) -> None:
        """Retune Magenta's live style when the zone changes or tempo drifts."""
        bpm = self.heart.bpm
        self.engine.set_bpm(bpm)
        zone, prompt = hr_to_style(bpm)
        if zone != self._current_zone or abs(bpm - self._last_bpm) >= self.restyle_bpm_delta:
            self._current_zone = zone
            self._last_bpm = bpm
            self.engine.set_style(prompt, label=f"{zone} @ {bpm:.0f} BPM")

    def mix_block(self, frames: int, *, offline: bool = False) -> np.ndarray:
        """Return one (frames, 2) block straight from Magenta."""
        out = self.engine.read(frames, offline=offline)
        np.clip(out, -1.0, 1.0, out=out)
        return out.astype(np.float32)

    def run(self) -> None:
        """Play AURALINK live until interrupted (Ctrl-C)."""
        import sounddevice as sd

        self.update_style_for_hr()
        self.engine.start()
        self.heart.start()

        def callback(outdata, frames, _time, status):
            if status:
                print(f"Playback status: {status}")
            outdata[:] = self.mix_block(frames)

        print("AURALINK live: heartbeat -> Magenta RealTime 2 (all audio). Ctrl-C to stop.")
        try:
            with sd.OutputStream(
                samplerate=SAMPLE_RATE,
                channels=2,
                dtype="float32",
                callback=callback,
            ):
                while not self.engine.stopped:
                    self.update_style_for_hr()
                    time.sleep(0.25)
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            self.heart.stop()
            self.engine.stop()

    def render(self, seconds: float, path: str = "auralink_demo.wav") -> str:
        """Render `seconds` of the Magenta pipeline to a WAV (offline, no device)."""
        import soundfile as sf

        self.update_style_for_hr()
        total = int(seconds * SAMPLE_RATE)
        block = 4800  # 0.1s
        chunks = []
        rendered = 0
        while rendered < total:
            self.update_style_for_hr()
            n = min(block, total - rendered)
            chunks.append(self.mix_block(n, offline=True))
            rendered += n
        audio = np.concatenate(chunks, axis=0)
        sf.write(path, audio, SAMPLE_RATE)
        print(f"Wrote {path} ({seconds:g}s).")
        return path
