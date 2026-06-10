#!/usr/bin/env python3
"""Test: the playback watchdog reopens the output stream when the device drops.

Uses fakes (no real audio device, no Magenta model) so it runs anywhere. Drives
Auralink.start_audio(), simulates the OutputStream dying (active -> False, as
PortAudio does when the aux jack is unplugged), and asserts the watchdog
rebuilds it without a full restart; then checks a clean stop.

Run: python scripts/test_audio_reconnect.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auralink.auralink import Auralink


class FakeStream:
    def __init__(self) -> None:
        self.active = True
        self.closed = False

    def start(self) -> None:
        pass

    def stop(self) -> None:
        self.active = False

    def close(self) -> None:
        self.closed = True
        self.active = False


class FakeEngine:
    def __init__(self) -> None:
        self.style_label = ""
        self._stopped = False

    @property
    def stopped(self) -> bool:
        return self._stopped

    def set_bpm(self, bpm: float) -> None:
        pass

    def set_style(self, prompt: str, label: str | None = None) -> None:
        self.style_label = label or prompt

    def start(self) -> None:
        pass

    def stop(self) -> None:
        self._stopped = True


class FakeHeart:
    bpm = 60.0

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


def main() -> None:
    link = Auralink(engine=FakeEngine(), heart=FakeHeart())

    opened: list[FakeStream] = []

    def fake_open() -> FakeStream:
        s = FakeStream()
        opened.append(s)
        return s

    link._open_stream = fake_open  # bypass real sounddevice

    link.start_audio()
    assert link._playing, "should be playing after start_audio"
    assert len(opened) == 1, f"expected 1 stream opened, got {len(opened)}"

    # A healthy stream must NOT be reopened (no spurious reconnect spam).
    time.sleep(1.2)
    assert len(opened) == 1, f"watchdog reopened a healthy stream ({len(opened)})"

    # Simulate the aux device dropping: PortAudio aborts the stream.
    opened[0].active = False
    deadline = time.time() + 3.0
    while len(opened) < 2 and time.time() < deadline:
        time.sleep(0.1)
    assert len(opened) == 2, "watchdog did not reconnect after device drop"
    assert opened[1].active, "reconnected stream should be active"
    assert opened[0].closed, "dropped stream should be closed"

    link.stop_audio()
    assert not link._playing, "should not be playing after stop_audio"
    assert link._stream is None, "stream handle should be cleared on stop"

    print("PASS: watchdog reconnects the output stream after a device drop")


if __name__ == "__main__":
    main()
