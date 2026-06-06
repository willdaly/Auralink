"""AURALINK — a heartbeat plays Magenta RealTime 2 as a live instrument."""

from .app import Auralink, hr_to_style, main
from .engine import SAMPLE_RATE, MagentaEngine
from .heartbeat import (
    HeartbeatSource,
    PulsoidHeartbeat,
    SerialHeartbeat,
    SimulatedHeartbeat,
)

__all__ = [
    "Auralink",
    "hr_to_style",
    "main",
    "SAMPLE_RATE",
    "MagentaEngine",
    "HeartbeatSource",
    "PulsoidHeartbeat",
    "SerialHeartbeat",
    "SimulatedHeartbeat",
]
