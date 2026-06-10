#!/usr/bin/env python3
"""Test: BLE Heart Rate Measurement parsing (characteristic 0x2A37).

Validates parse_hr_measurement against the Bluetooth Heart Rate Service spec
without any hardware. Run: python scripts/test_ble_hr_parse.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auralink.heartbeat import parse_hr_measurement

cases = [
    # (payload bytes, expected BPM)
    # flags bit0=0 -> 8-bit HR in byte 1
    (bytes([0x00, 60]), 60.0),
    (bytes([0x00, 72]), 72.0),
    (bytes([0x00, 255]), 255.0),
    # other flag bits set (sensor contact/RR) but bit0=0 -> still 8-bit
    (bytes([0x16, 88]), 88.0),
    # flags bit0=1 -> 16-bit little-endian HR in bytes 1-2
    (bytes([0x01, 0x2C, 0x01]), 300.0),  # 0x012C = 300
    (bytes([0x01, 60, 0]), 60.0),
    # bit0=1 with trailing RR-interval bytes; HR still bytes 1-2
    (bytes([0x11, 75, 0, 0xDE, 0x03]), 75.0),
    # too short / empty -> None
    (bytes([0x00]), None),
    (bytes([0x01, 0x2C]), None),
    (b"", None),
]

failed = 0
for payload, expected in cases:
    got = parse_hr_measurement(payload)
    ok = got == expected
    if not ok:
        failed += 1
        print(f"FAIL: {payload.hex() or '<empty>'} -> {got!r}, expected {expected!r}")

if failed:
    print(f"{failed} case(s) failed")
    raise SystemExit(1)
print(f"PASS: all {len(cases)} HR-measurement parse cases correct")
