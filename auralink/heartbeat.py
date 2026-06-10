#!/usr/bin/env python3
"""Heartbeat sources for AURALINK.

A heartbeat is the *controller* that plays Magenta RealTime 2. This module
defines a small interface so the same orchestrator works with a simulated
heartbeat for demos and a live heart rate (Pulsoid) for real input.

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
    """A stand-in heart rate that gently drifts, for demos without a live feed.

    The BPM oscillates slowly around a resting value so you can hear AURALINK
    respond (tempo + Magenta style changes) without a connected monitor. Set
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
        if self._thread is not None and self._thread.is_alive():
            return
        if self._stop.is_set():
            self._stop = threading.Event()
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
            self._thread = None


def parse_hr_measurement(data: bytes | bytearray) -> float | None:
    """Parse a BLE Heart Rate Measurement value (characteristic 0x2A37).

    Per the Bluetooth Heart Rate Service spec, byte 0 is a flags field whose
    bit 0 selects the heart-rate value width: 0 = uint8 in byte 1, 1 = uint16
    little-endian in bytes 1-2. (Higher flag bits cover sensor contact, energy
    expended and RR intervals, which we don't need.) Returns the BPM, or None
    if the payload is too short to contain a value.
    """
    if not data:
        return None
    flags = data[0]
    if flags & 0x01:  # 16-bit heart rate
        if len(data) < 3:
            return None
        return float(int.from_bytes(bytes(data[1:3]), "little"))
    if len(data) < 2:
        return None
    return float(data[1])


class BleHeartbeat(HeartbeatSource):
    """Live heart rate from a Bluetooth LE chest/arm strap (Polar, Garmin,
    Wahoo, Coros, CooSpo, ...).

    Any strap that implements the standard BLE Heart Rate Service (0x180D)
    works without per-vendor code: we subscribe to the Heart Rate Measurement
    characteristic (0x2A37) and smooth the notified BPM into a stable tempo for
    Magenta, exactly like PulsoidHeartbeat — so the orchestrator is unchanged.
    Unlike Pulsoid this needs no account, token or network; it talks to the
    strap directly over Bluetooth.

    By default it auto-discovers the first device advertising the heart-rate
    service. Pass ``name=`` to match a substring of the advertised name, or
    ``address=`` to target a specific device. The bleak backend runs its async
    work on a private event loop in a background thread.
    """

    HR_SERVICE = "0000180d-0000-1000-8000-00805f9b34fb"
    HR_MEASUREMENT_CHAR = "00002a37-0000-1000-8000-00805f9b34fb"

    def __init__(
        self,
        address: str | None = None,
        name: str | None = None,
        smoothing: float = 0.3,
    ) -> None:
        self._address = address
        self._name = name
        self._smoothing = smoothing
        self._bpm = 60.0
        self._got_first = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop = None
        self._lock = threading.Lock()

    @property
    def bpm(self) -> float:
        with self._lock:
            return self._bpm

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        if self._stop.is_set():
            self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        import asyncio

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._read_loop())
        finally:
            self._loop.close()
            self._loop = None

    async def _discover(self):
        from bleak import BleakScanner

        if self._address:
            return await BleakScanner.find_device_by_address(
                self._address, timeout=10.0
            )

        def match(device, adv) -> bool:
            if self._name and self._name.lower() in (device.name or "").lower():
                return True
            uuids = [u.lower() for u in (adv.service_uuids or [])]
            return self.HR_SERVICE in uuids

        return await BleakScanner.find_device_by_filter(match, timeout=10.0)

    async def _read_loop(self) -> None:
        import asyncio

        from bleak import BleakClient

        backoff = 1.0
        while not self._stop.is_set():
            try:
                device = await self._discover()
                if device is None:
                    print("No BLE heart-rate strap found; rescanning...")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 10.0)
                    continue
                async with BleakClient(device) as client:
                    backoff = 1.0
                    print(
                        "Connected to heart-rate strap: "
                        f"{device.name or device.address}"
                    )
                    await client.start_notify(
                        self.HR_MEASUREMENT_CHAR, self._on_measurement
                    )
                    while not self._stop.is_set() and client.is_connected:
                        await asyncio.sleep(0.2)
                    if client.is_connected:
                        await client.stop_notify(self.HR_MEASUREMENT_CHAR)
            except Exception as exc:  # noqa: BLE001 - reconnect on any drop
                if self._stop.is_set():
                    break
                print(f"BLE strap connection lost ({exc}); reconnecting...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 10.0)

    def _on_measurement(self, _characteristic, data: bytearray) -> None:
        bpm = parse_hr_measurement(data)
        if bpm is None or not 30.0 <= bpm <= 240.0:  # sanity window
            return
        with self._lock:
            if self._got_first:
                self._bpm = (
                    self._smoothing * bpm + (1 - self._smoothing) * self._bpm
                )
            else:
                self._bpm = bpm
                self._got_first = True

    def stop(self) -> None:
        self._stop.set()
        loop = self._loop
        if loop is not None:
            try:  # wake the loop so it sees _stop promptly
                loop.call_soon_threadsafe(lambda: None)
            except Exception:  # noqa: BLE001
                pass
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None


def check_ble(address: str | None = None, name: str | None = None,
              seconds: float = 20.0) -> int:
    """Connect to a BLE heart-rate strap and print live BPM, then exit.

    Verifies the strap/Bluetooth path without loading Magenta — the BLE analog
    of check_pulsoid. Returns 0 if at least one reading arrived, else 1.
    """
    import asyncio

    from bleak import BleakClient, BleakScanner

    async def run() -> int:
        if address:
            print(f"Looking for strap at address {address} ...")
            device = await BleakScanner.find_device_by_address(address, timeout=10.0)
        else:
            label = f"name~={name!r}" if name else "any heart-rate strap"
            print(f"Scanning for {label} (service 0x180D) ...")

            def match(dev, adv) -> bool:
                if name and name.lower() in (dev.name or "").lower():
                    return True
                uuids = [u.lower() for u in (adv.service_uuids or [])]
                return BleHeartbeat.HR_SERVICE in uuids

            device = await BleakScanner.find_device_by_filter(match, timeout=10.0)

        if device is None:
            print("No BLE heart-rate strap found. Is it on and worn (sensors "
                  "need skin contact to advertise)? Is Bluetooth enabled and "
                  "permitted for your terminal?")
            return 1

        received = 0

        def on_measurement(_char, data: bytearray) -> None:
            nonlocal received
            bpm = parse_hr_measurement(data)
            if bpm is not None:
                received += 1
                print(f"  -> {bpm:.0f} BPM")

        print(f"Connecting to {device.name or device.address} ...")
        async with BleakClient(device) as client:
            await client.start_notify(
                BleHeartbeat.HR_MEASUREMENT_CHAR, on_measurement
            )
            await asyncio.sleep(seconds)
            await client.stop_notify(BleHeartbeat.HR_MEASUREMENT_CHAR)

        if received:
            print(f"OK: received {received} reading(s). The strap works.")
            return 0
        print("Connected but no readings arrived. Make sure the strap has skin "
              "contact and isn't paired to another app.")
        return 1

    return asyncio.run(run())


def check_pulsoid(token: str | None = None, seconds: float = 20.0,
                  url: str | None = None) -> int:
    """Print live Pulsoid messages for a few seconds to verify the feed.

    A lightweight diagnostic that confirms the token, endpoint, and watch are
    streaming, without loading Magenta. Prints each raw frame and the BPM we
    parse from it. Returns 0 if at least one heart rate was received, else 1, so
    it can be used as a CLI exit code.
    """
    import json
    import os
    import time

    import websocket  # websocket-client

    token = token or os.environ.get("PULSOID_TOKEN")
    if not token:
        print("No Pulsoid token. Set PULSOID_TOKEN (see .env.example) or pass "
              "--pulsoid-token.")
        return 1

    endpoint = url or PulsoidHeartbeat.DEFAULT_URL
    print(f"Connecting to Pulsoid ({endpoint}) for {seconds:g}s...")
    try:
        ws = websocket.create_connection(f"{endpoint}?access_token={token}",
                                         timeout=10)
    except Exception as exc:  # noqa: BLE001
        print(f"Could not connect: {exc}")
        print("Check the token/scope (data:heart_rate:read) and your network.")
        return 1

    received = 0
    deadline = time.time() + seconds
    try:
        ws.settimeout(seconds)
        while time.time() < deadline:
            try:
                raw = ws.recv()
            except Exception:  # noqa: BLE001 - timeout/closed
                break
            if not raw:
                continue
            print(f"  raw: {raw}")
            try:
                bpm = float(json.loads(raw)["data"]["heart_rate"])
                received += 1
                print(f"  -> parsed BPM: {bpm:.0f}")
            except (ValueError, KeyError, TypeError):
                print("  -> could not parse heart_rate from this message "
                      "(the JSON shape may differ; share this line).")
    finally:
        try:
            ws.close()
        except Exception:  # noqa: BLE001
            pass

    if received:
        print(f"OK: received {received} heart-rate message(s). Pulsoid is working.")
        return 0
    print("No heart-rate messages received. Is the watch streaming to Pulsoid, "
          "and is the token correct?")
    return 1

