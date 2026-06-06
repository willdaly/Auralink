#!/usr/bin/env python3
"""MagentaEngine — Magenta RealTime 2 as a live, controllable instrument.

This is the heart of AURALINK and what keeps the project on-challenge for the
Google DeepMind / Magenta RealTime 2 track: MRT2 generates audio continuously in
real time, and its sound can be steered live through `set_style()` (and the
sampling controls). An external controller (a heartbeat) calls those hooks.

The model is MRT2 `mrt2_small`, which streams in real time on an M1 Pro. Audio
is generated in a background thread and consumed block-by-block by whoever owns
the output stream (see auralink.py), so the engine can be mixed with other
layers.
"""

from __future__ import annotations

import queue
import threading
import time

import numpy as np

SAMPLE_RATE = 48_000  # MRT2 native output rate
FRAMES_PER_SECOND = 25  # 25 generation frames == 1 second of audio


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
    ) -> None:
        self.size = size
        self.bits = bits
        self.chunk_frames = chunk_frames
        self.prebuffer_chunks = prebuffer_chunks
        self.temperature = temperature
        self.play_drums = play_drums

        self._mrt = None
        self._embedding = None
        self._state = None
        self._style_label = ""

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

    # -- Generation -------------------------------------------------------

    def _generate_chunk(self) -> np.ndarray:
        """Generate one audio chunk, advancing the streaming state."""
        with self._lock:
            embedding = self._embedding
            temperature = self.temperature
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
