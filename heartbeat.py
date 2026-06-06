#!/usr/bin/env python3
"""Heartbeat sources for AURALINK.

A heartbeat is the *controller* that plays Magenta RealTime 2. This module
defines a small interface so the same orchestrator works with a simulated
heartbeat today and a real Arduino pulse sensor later.

A source exposes one thing the rest of the app cares about: the current tempo in
beats per minute (`bpm`), which the audio engine reads to schedule beats and to
map onto Magenta's live style.
"""

from __future__ import annotations

import math
import threading
import time


class HeartbeatSource:
    """Base interface: something that reports a heart rate in BPM."""

    @property
    def bpm(self) -> float:  # pragma: no cover - interface
        raise NotImplementedError

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class SimulatedHeartbeat(HeartbeatSource):
    """A stand-in heart rate that gently drifts, for demos without hardware.

    The BPM oscillates slowly around a resting value so you can hear AURALINK
    respond (tempo + Magenta style changes) before the Arduino arrives. Set
    `drift=0` for a perfectly steady rate, or call `set_bpm()` to drive it
    manually (e.g. from a UI slider).
    """

    def __init__(
        self,
        bpm: float = 60.0,
        drift: float = 8.0,
        period_s: float = 30.0,
    ) -> None:
        self._base_bpm = bpm
        self._drift = drift
        self._period_s = period_s
        self._manual: float | None = None
        self._t0 = time.time()
        self._lock = threading.Lock()

    @property
    def bpm(self) -> float:
        with self._lock:
            if self._manual is not None:
                return self._manual
            phase = (time.time() - self._t0) / self._period_s * 2 * math.pi
            return self._base_bpm + self._drift * math.sin(phase)

    def set_bpm(self, bpm: float) -> None:
        """Pin the heart rate to a fixed value (overrides drift)."""
        with self._lock:
            self._manual = bpm


class SerialHeartbeat(HeartbeatSource):
    """Read beats from an Arduino pulse sensor over serial (future hardware).

    The Arduino firmware should print one line per detected systolic peak (a
    beat). We convert the interval between beats into an instantaneous BPM. This
    is a stub wired for when the hardware arrives; it is not used by the demo
    yet.
    """

    def __init__(self, port: str, baud: int = 115_200, smoothing: float = 0.3) -> None:
        self._port = port
        self._baud = baud
        self._smoothing = smoothing
        self._bpm = 60.0
        self._last_beat: float | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def bpm(self) -> float:
        with self._lock:
            return self._bpm

    def start(self) -> None:
        import serial  # pyserial; only needed for real hardware

        self._serial = serial.Serial(self._port, self._baud, timeout=1.0)
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self) -> None:
        while not self._stop.is_set():
            line = self._serial.readline()
            if not line:
                continue
            now = time.time()
            if self._last_beat is not None:
                interval = now - self._last_beat
                if 0.25 < interval < 2.0:  # 30–240 BPM sanity window
                    inst = 60.0 / interval
                    with self._lock:
                        self._bpm = (
                            self._smoothing * inst
                            + (1 - self._smoothing) * self._bpm
                        )
            self._last_beat = now

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)


class PulsoidHeartbeat(HeartbeatSource):
    """Live heart rate from a Pulsoid stream (e.g. an Apple Watch).

    Pulsoid relays a phone/watch heart-rate monitor to a WebSocket. Each message
    carries the current BPM, which we smooth into a stable tempo for Magenta. The
    interface matches the other sources, so the orchestrator is unchanged.

    The access token is a secret: pass it explicitly or set ``PULSOID_TOKEN`` in
    the environment. Never commit it. Reading heart rate requires a Pulsoid token
    with the ``data:heart_rate:read`` scope (paid/trial plan).
    """

    DEFAULT_URL = "wss://dev.pulsoid.net/api/v1/data/real_time"

    def __init__(
        self,
        token: str | None = None,
        smoothing: float = 0.3,
        url: str | None = None,
    ) -> None:
        import os

        self._token = token or os.environ.get("PULSOID_TOKEN")
        if not self._token:
            raise ValueError(
                "Pulsoid access token missing. Pass token=... or set "
                "PULSOID_TOKEN in the environment."
            )
        self._url = url or self.DEFAULT_URL
        self._smoothing = smoothing
        self._bpm = 60.0
        self._got_first = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._ws = None
        self._lock = threading.Lock()

    @property
    def bpm(self) -> float:
        with self._lock:
            return self._bpm

    def start(self) -> None:
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self) -> None:
        import json

        import websocket  # websocket-client; only needed for Pulsoid

        url = f"{self._url}?access_token={self._token}"
        backoff = 1.0
        while not self._stop.is_set():
            try:
                self._ws = websocket.create_connection(url, timeout=10)
                backoff = 1.0  # reset after a successful connect
                while not self._stop.is_set():
                    raw = self._ws.recv()
                    if not raw:
                        continue
                    try:
                        payload = json.loads(raw)
                        bpm = float(payload["data"]["heart_rate"])
                    except (ValueError, KeyError, TypeError):
                        continue
                    if not 30.0 <= bpm <= 240.0:  # sanity window
                        continue
                    with self._lock:
                        if self._got_first:
                            self._bpm = (
                                self._smoothing * bpm
                                + (1 - self._smoothing) * self._bpm
                            )
                        else:
                            self._bpm = bpm
                            self._got_first = True
            except Exception as exc:  # noqa: BLE001 - reconnect on any drop
                if self._stop.is_set():
                    break
                print(f"Pulsoid connection lost ({exc}); reconnecting...")
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 10.0)
            finally:
                self._close_ws()

    def _close_ws(self) -> None:
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:  # noqa: BLE001
                pass
            self._ws = None

    def stop(self) -> None:
        self._stop.set()
        self._close_ws()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
