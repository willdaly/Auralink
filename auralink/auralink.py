#!/usr/bin/env python3
"""Auralink runtime orchestration and heart-rate style mapping."""

from __future__ import annotations

import csv
import threading
import time
from pathlib import Path

import numpy as np

from .engine import SAMPLE_RATE, MagentaEngine
from .heartbeat import HeartbeatSource, PulsoidHeartbeat
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
        self._csv_path = Path(f"auralink_{time.strftime('%Y%m%d_%H%M%S')}.csv")
        self._csv_file = None
        self._csv_writer = None

    def _effective_bpm(self) -> float:
        """The BPM that drives Magenta: live heartbeat, or the manual override."""
        with self._lock:
            bio, manual = self._bio_mode, self._manual_bpm
        return self.heart.bpm if bio else manual

    @property
    def _manual_override_allowed(self) -> bool:
        """Manual tempo is disabled when the source is live Pulsoid."""
        return not isinstance(self.heart, PulsoidHeartbeat)

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
        if not enabled and not self._manual_override_allowed:
            return
        with self._lock:
            self._bio_mode = bool(enabled)

    def set_manual_bpm(self, bpm: float) -> None:
        """Set the manual tempo and switch off bio mode (UI slider drag)."""
        if not self._manual_override_allowed:
            return
        with self._lock:
            self._manual_bpm = float(bpm)
            self._bio_mode = False

    def get_state(self) -> dict:
        """Snapshot of live state for the dashboard (JSON-serialisable)."""
        heart_bpm = float(self.heart.bpm)
        with self._lock:
            effective = self._current_bpm or (heart_bpm if self._bio_mode else self._manual_bpm)
            bio_mode = self._bio_mode
            return {
                "bpm": round(effective, 1),
                "heart_bpm": round(heart_bpm, 1),
                "effective_bpm": round(effective, 1),
                "heartbeat_source": (
                    "Pulsoid"
                    if isinstance(self.heart, PulsoidHeartbeat)
                    else "Simulated"
                ),
                "zone": self._current_zone,
                "style_label": self.engine.style_label,
                "prompt": self._current_prompt,
                "playing": self._playing,
                "bio_mode": bio_mode,
                "manual_override_allowed": self._manual_override_allowed,
                "tempo_source": "heartbeat" if bio_mode else "manual",
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
        self._csv_file = self._csv_path.open("w", newline="")
        self._csv_writer = csv.writer(self._csv_file)
        self._csv_writer.writerow(["timestamp", "heart_bpm", "music_bpm", "zone", "corr_10s", "hrv_rmssd_ms"])
        self._csv_file.flush()
        print(f"Logging to {self._csv_path}")

        heart_buf: list[float] = []
        music_buf: list[float] = []
        rr_buf: list[float] = []   # real RR intervals from measured_at timestamps
        _tick = 0
        _corr: str = "n/a"
        _hrv: str = "n/a"
        _hrv_val: float = -1.0

        while not self._stop_poll.is_set() and not self.engine.stopped:
            self.update_style_for_hr()
            _tick += 1
            if _tick % 4 == 0:  # ~1 Hz
                heart_bpm = round(self.heart.bpm, 1)
                music_bpm = round(self.engine.bpm, 1)
                zone = self._current_zone or "—"

                heart_buf.append(heart_bpm)
                music_buf.append(music_bpm)

                # Collect real RR intervals from Pulsoid measured_at timestamps
                if hasattr(self.heart, "pop_rr_intervals"):
                    rr_buf.extend(self.heart.pop_rr_intervals())
                    if len(rr_buf) > 60:  # keep last ~60 beats
                        rr_buf = rr_buf[-60:]

                # Every 10 seconds: recompute correlation and HRV
                if _tick % 40 == 0:
                    if len(heart_buf) >= 10:
                        h = np.array(heart_buf[-10:])
                        m = np.array(music_buf[-10:])
                        if h.std() > 0 and m.std() > 0:
                            _corr = f"{np.corrcoef(h, m)[0, 1]:.3f}"
                        else:
                            _corr = "1.000"

                    # RMSSD from real RR intervals
                    if len(rr_buf) >= 2:
                        diffs = np.diff(np.array(rr_buf))
                        _hrv_val = float(np.sqrt(np.mean(diffs ** 2)))
                        _hrv = f"{_hrv_val:.1f}"

                    print(
                        f"  --> Correlation (last 10s): r = {_corr}  |  HRV RMSSD: {_hrv} ms",
                        flush=True,
                    )

                print(
                    f"Heart: {heart_bpm:5.1f} BPM  |  Music: {music_bpm:5.1f} BPM  |  Zone: {zone:<15}  |  r = {_corr}  |  HRV: {_hrv} ms",
                    flush=True,
                )
                self._csv_writer.writerow([time.strftime("%Y-%m-%dT%H:%M:%S"), heart_bpm, music_bpm, zone, _corr, _hrv])
                self._csv_file.flush()
            time.sleep(0.25)

        self._csv_file.close()
        self._csv_file = None

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
