#!/usr/bin/env python3
"""Auralink runtime orchestration and heart-rate style mapping."""

from __future__ import annotations

import threading
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
        # Live state shared with the web bridge (see get_state()).
        self._lock = threading.Lock()
        self._bio_mode = True  # True: follow the heartbeat; False: manual tempo.
        self._manual_bpm = 60.0
        self._current_bpm = 0.0
        self._current_prompt = ""
        self._playing = False
        # Non-blocking playback handles.
        self._stream = None
        self._poll_thread: threading.Thread | None = None
        self._stop_poll = threading.Event()

    def _effective_bpm(self) -> float:
        """The BPM that drives Magenta: live heartbeat, or the manual override."""
        with self._lock:
            bio, manual = self._bio_mode, self._manual_bpm
        return self.heart.bpm if bio else manual

    def update_style_for_hr(self) -> None:
        """Retune Magenta's live style when the zone changes or tempo drifts."""
        bpm = self._effective_bpm()
        self.engine.set_bpm(bpm)
        zone, prompt = hr_to_style(bpm)
        with self._lock:
            self._current_bpm = bpm
            self._current_prompt = prompt
        if zone != self._current_zone or abs(bpm - self._last_bpm) >= self.restyle_bpm_delta:
            self._current_zone = zone
            self._last_bpm = bpm
            self.engine.set_style(prompt, label=f"{zone} @ {bpm:.0f} BPM")

    # -- Live control + state (used by the web bridge) --------------------

    def set_bio_mode(self, enabled: bool) -> None:
        """Follow the live heartbeat (True) or a manual tempo slider (False)."""
        with self._lock:
            self._bio_mode = bool(enabled)

    def set_manual_bpm(self, bpm: float) -> None:
        """Set the manual tempo and switch off bio mode (UI slider drag)."""
        with self._lock:
            self._manual_bpm = float(bpm)
            self._bio_mode = False

    def get_state(self) -> dict:
        """Snapshot of live state for the dashboard (JSON-serialisable)."""
        with self._lock:
            return {
                "bpm": round(self._current_bpm, 1),
                "zone": self._current_zone,
                "style_label": self.engine.style_label,
                "prompt": self._current_prompt,
                "playing": self._playing,
                "bio_mode": self._bio_mode,
                "manual_bpm": round(self._manual_bpm, 1),
            }

    def mix_block(self, frames: int, *, offline: bool = False) -> np.ndarray:
        """Return one (frames, 2) block straight from Magenta."""
        out = self.engine.read(frames, offline=offline)
        np.clip(out, -1.0, 1.0, out=out)
        return out.astype(np.float32)

    def start_audio(self) -> None:
        """Start live playback in the background (non-blocking).

        Opens the audio device, starts Magenta + the heartbeat, and runs a poll
        thread that retunes the style as the heart rate changes. Returns once
        audio is flowing; call stop_audio() to end it.
        """
        import sounddevice as sd

        if self._playing:
            return
        self.update_style_for_hr()
        self.engine.start()
        self.heart.start()

        def callback(outdata, frames, _time, status):
            if status:
                print(f"Playback status: {status}")
            outdata[:] = self.mix_block(frames)

        self._stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=2,
            dtype="float32",
            callback=callback,
        )
        self._stream.start()
        self._stop_poll.clear()
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        with self._lock:
            self._playing = True

    def _poll_loop(self) -> None:
        while not self._stop_poll.is_set() and not self.engine.stopped:
            self.update_style_for_hr()
            time.sleep(0.25)

    def stop_audio(self) -> None:
        """Stop live playback and release the audio device."""
        if not self._playing:
            return
        self._stop_poll.set()
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=1.0)
            self._poll_thread = None
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self.heart.stop()
        self.engine.stop()
        with self._lock:
            self._playing = False

    def run(self) -> None:
        """Play AURALINK live until interrupted (Ctrl-C)."""
        print("AURALINK live: heartbeat -> Magenta RealTime 2 (all audio). Ctrl-C to stop.")
        self.start_audio()
        try:
            while self._playing and not self.engine.stopped:
                time.sleep(0.25)
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            self.stop_audio()

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
