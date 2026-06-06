#!/usr/bin/env python3
"""MagentaEngine — Magenta RealTime 2 as a live, controllable instrument.

This is the heart of AURALINK and what keeps the project on-challenge for the
Google DeepMind / Magenta RealTime 2 track: MRT2 generates audio continuously in
real time, and its sound can be steered live through `set_style()` (and the
sampling controls). An external controller (a heartbeat) calls those hooks.

The model is MRT2 `mrt2_small`, which streams in real time on an M1 Pro. Audio
is generated in a background thread and consumed block-by-block by whoever owns
the output stream (see app.py), so the engine can be mixed with other
layers.
"""

from __future__ import annotations

import queue
import threading
import time

import numpy as np

SAMPLE_RATE = 48_000  # MRT2 native output rate
FRAMES_PER_SECOND = 25  # 25 generation frames == 1 second of audio


class TempoConductor:
    """Schedules a drum-onset pulse train at a live, settable BPM.

    Magenta RT2 has no text "tempo" knob — but its drum conditioning is sampled
    per frame at 25 fps (40 ms), which acts like a MIDI rhythm input. By placing
    a drum onset (drums=[1]) only on the frames that land on a beat and silence
    (drums=[0]) in between, the *spacing* of the onsets encodes the tempo, and
    Magenta follows it. This conductor produces that per-frame onset signal and
    tracks a global frame clock so the pulse stays continuous across chunks.

    Thread-safe: the heart-rate poller calls set_bpm() while the generation
    thread calls drum_for_next_frame().
    """

    def __init__(
        self,
        fps: int = FRAMES_PER_SECOND,
        bpm: float = 60.0,
        min_bpm: float = 20.0,
        max_bpm: float = 240.0,
    ) -> None:
        self._fps = fps
        self._min_bpm = min_bpm
        self._max_bpm = max_bpm
        self._lock = threading.Lock()
        self._bpm = max(min_bpm, min(max_bpm, bpm))
        self._frame = 0  # global frame counter
        self._next_beat = 0.0  # frame index of the next onset (frame 0 is a beat)

    def set_bpm(self, bpm: float) -> None:
        with self._lock:
            self._bpm = max(self._min_bpm, min(self._max_bpm, float(bpm)))

    @property
    def bpm(self) -> float:
        with self._lock:
            return self._bpm

    def drum_for_next_frame(self) -> list[int]:
        """Return [1] on a beat-onset frame else [0], then advance the clock.

        Adapts immediately to BPM changes: the next onset is always at most one
        (current-tempo) beat away, so speeding up never waits on a stale slow
        interval.
        """
        with self._lock:
            f = self._frame
            frames_per_beat = self._fps * 60.0 / self._bpm
            # If a tempo increase left the next beat too far out, pull it in.
            if self._next_beat - f > frames_per_beat:
                self._next_beat = f + frames_per_beat
            if f >= self._next_beat:
                drum = [1]
                self._next_beat += frames_per_beat
            else:
                drum = [0]
            self._frame = f + 1
            return drum


class MagentaEngine:
    """Continuously generates audio with Magenta RealTime 2, steerable live."""

    def __init__(
        self,
        size: str = "mrt2_small",
        bits: int = 8,
        chunk_frames: int = FRAMES_PER_SECOND,
        prebuffer_chunks: int = 2,
        temperature: float | None = None,
        play_drums: bool = True,
        tempo_mode: str = "pulse",
    ) -> None:
        self.size = size
        self.bits = bits
        self.chunk_frames = chunk_frames
        self.prebuffer_chunks = prebuffer_chunks
        self.temperature = temperature
        self.play_drums = play_drums
        self.tempo_mode = tempo_mode  # "pulse" = tempo-locked drum onsets; "constant" = old always-on drums

        self._mrt = None
        self._embedding = None
        self._state = None
        self._style_label = ""
        self._conductor = TempoConductor(fps=FRAMES_PER_SECOND)

        self._lock = threading.Lock()
        self._audio_q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=8)
        self._residual = np.zeros((0, 2), dtype=np.float32)
        self._stop = threading.Event()
        self._gen_thread: threading.Thread | None = None

    # -- Model loading & live control -------------------------------------

    def load_model(self) -> None:
        """Load the MRT2 MLX model (heavy import; call once at startup)."""
        from magenta_rt import MagentaRT2Mlx

        print(f"Loading Magenta RealTime 2 '{self.size}' ...")
        t0 = time.time()
        self._mrt = MagentaRT2Mlx(size=self.size, bits=self.bits)
        print(f"Magenta model ready in {time.time() - t0:.1f}s.")

    def set_style(self, prompt: str, label: str | None = None) -> None:
        """Re-embed the style prompt. Thread-safe; safe to call live."""
        if self._mrt is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        embedding = self._mrt.embed_style(prompt)
        with self._lock:
            self._embedding = embedding
            self._style_label = label or prompt
        print(f'Magenta style -> {self._style_label!r}')

    @property
    def style_label(self) -> str:
        return self._style_label

    def set_bpm(self, bpm: float) -> None:
        """Set the live tempo (beats per minute) of the drum pulse. Thread-safe."""
        self._conductor.set_bpm(bpm)

    @property
    def bpm(self) -> float:
        return self._conductor.bpm

    # -- Generation -------------------------------------------------------

    def _generate_chunk(self) -> np.ndarray:
        """Generate one audio chunk, advancing the streaming state.

        In "pulse" tempo mode the chunk is built frame-by-frame so the drum
        onset for each frame comes from the conductor — the kick pulse tracks
        the live BPM. In "constant" mode the whole chunk is generated in one
        call with drums held on (the original behavior).
        """
        with self._lock:
            embedding = self._embedding
            temperature = self.temperature

        if self.tempo_mode == "pulse":
            frames_out: list[np.ndarray] = []
            for _ in range(self.chunk_frames):
                drums = self._conductor.drum_for_next_frame() if self.play_drums else None
                wav, self._state = self._mrt.generate(
                    style=embedding,
                    drums=drums,
                    temperature=temperature,
                    frames=1,
                    state=self._state,
                )
                frames_out.append(np.asarray(wav.samples, dtype=np.float32))
            return np.concatenate(frames_out, axis=0)

        drums = [1] if self.play_drums else None
        wav, self._state = self._mrt.generate(
            style=embedding,
            drums=drums,
            temperature=temperature,
            frames=self.chunk_frames,
            state=self._state,
        )
        return np.asarray(wav.samples, dtype=np.float32)

    def _generate_loop(self) -> None:
        while not self._stop.is_set():
            try:
                chunk = self._generate_chunk()
            except Exception as exc:  # surface errors then stop cleanly
                print(f"Magenta generation error: {exc}")
                self._stop.set()
                break
            while not self._stop.is_set():
                try:
                    self._audio_q.put(chunk, timeout=0.1)
                    break
                except queue.Full:
                    continue

    def start(self) -> None:
        """Start the background generation thread and pre-buffer audio."""
        if self._embedding is None:
            raise RuntimeError("No style set. Call set_style() before start().")
        self._gen_thread = threading.Thread(target=self._generate_loop, daemon=True)
        self._gen_thread.start()
        while (
            self._audio_q.qsize() < self.prebuffer_chunks
            and not self._stop.is_set()
        ):
            time.sleep(0.05)

    def stop(self) -> None:
        self._stop.set()
        if self._gen_thread is not None:
            self._gen_thread.join(timeout=2.0)

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    # -- Consumption ------------------------------------------------------

    def read(self, frames: int, *, offline: bool = False) -> np.ndarray:
        """Return `frames` of (frames, 2) audio.

        In streaming mode, pulls from the generation queue and pads with silence
        on underrun. In offline mode, generates synchronously (for rendering).
        """
        while self._residual.shape[0] < frames:
            if offline:
                chunk = self._generate_chunk()
            else:
                try:
                    chunk = self._audio_q.get_nowait()
                except queue.Empty:
                    pad = np.zeros(
                        (frames - self._residual.shape[0], 2), dtype=np.float32
                    )
                    self._residual = np.vstack([self._residual, pad])
                    break
            self._residual = (
                chunk
                if self._residual.shape[0] == 0
                else np.vstack([self._residual, chunk])
            )
        out = self._residual[:frames]
        self._residual = self._residual[frames:]
        return out

    def selftest(self, num_chunks: int = 3) -> None:
        """Generate a few chunks without playback and report real-time factor."""
        for i in range(num_chunks):
            t0 = time.time()
            chunk = self._generate_chunk()
            seconds = chunk.shape[0] / SAMPLE_RATE
            elapsed = time.time() - t0
            rtf = elapsed / seconds if seconds else float("inf")
            print(
                f"chunk {i + 1}/{num_chunks}: {chunk.shape} "
                f"({seconds:.2f}s) in {elapsed:.2f}s — RTF {rtf:.2f}x "
                f"({'real-time OK' if rtf < 1 else 'too slow'})"
            )

    # -- Phase 0 spike: tempo via a MIDI-like drum pulse ------------------

    def render_pulse(
        self,
        bpm: float,
        seconds: float,
        *,
        mode: str = "pulse",
    ) -> np.ndarray:
        """Offline de-risk spike: render audio with a drum pulse train at `bpm`.

        Instead of leaning on a text "{bpm} BPM" word (which MRT2 does not lock
        tempo to), this drives Magenta's drum conditioning *per frame* — the
        model's MIDI-like rhythm input at 25 fps. A drum onset (drums=[1]) is
        placed only on the frames that land on a beat; the spacing of those
        onsets encodes the tempo for Magenta to follow.

        Args:
            bpm: Pulse rate (beats per minute) for the drum onsets.
            seconds: Length of audio to render.
            mode: "pulse" = onset on beat frames only; "constant" = drums on
                every frame (the old behavior, for an A/B comparison).

        Returns:
            (N, 2) float32 audio. Requires a style set via set_style().
        """
        if self._mrt is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        if self._embedding is None:
            raise RuntimeError("No style set. Call set_style() before render_pulse().")

        total_frames = int(round(seconds * FRAMES_PER_SECOND))
        frames_per_beat = FRAMES_PER_SECOND * 60.0 / bpm

        state = None
        next_beat = 0.0  # frame index of the next beat onset (frame 0 is a beat)
        beats = 0
        chunks: list[np.ndarray] = []
        t0 = time.time()
        for f in range(total_frames):
            if mode == "constant":
                drums = [1]
            else:
                if f >= next_beat:
                    drums = [1]
                    next_beat += frames_per_beat
                    beats += 1
                else:
                    drums = [0]
            wav, state = self._mrt.generate(
                style=self._embedding,
                drums=drums,
                temperature=self.temperature,
                frames=1,
                state=state,
            )
            chunks.append(np.asarray(wav.samples, dtype=np.float32))

        audio = np.concatenate(chunks, axis=0)
        elapsed = time.time() - t0
        rtf = elapsed / seconds if seconds else float("inf")
        print(
            f"render_pulse: {mode} @ {bpm:.1f} BPM — {beats} onsets over "
            f"{seconds:g}s, {frames_per_beat:.2f} frames/beat. "
            f"Generated in {elapsed:.1f}s (RTF {rtf:.2f}x)."
        )
        return audio
