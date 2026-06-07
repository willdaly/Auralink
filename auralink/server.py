#!/usr/bin/env python3
"""Local web bridge for the AURALINK dashboard.

Serves the static frontend and streams live state (heart rate, zone, tempo) to
the browser over a WebSocket, and accepts control messages (play/stop, bio
toggle, manual tempo) back from it.

Audio is NOT sent to the browser: Magenta RealTime 2 still generates every sound
and it plays locally through sounddevice. The browser is a telemetry + control
surface only, which keeps Magenta as the live instrument in the signal path.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from .auralink import Auralink

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def create_app(link: Auralink) -> FastAPI:
    """Build the FastAPI app wired to a (model-loaded) Auralink instance."""
    api = FastAPI(title="AURALINK")

    @api.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        await websocket.accept()
        push_task = asyncio.create_task(_push_state(websocket, link))
        try:
            while True:
                raw = await websocket.receive_text()
                # Control handlers may block (start/stop audio); offload them.
                await asyncio.to_thread(_handle_control, link, raw)
        except WebSocketDisconnect:
            pass
        finally:
            push_task.cancel()

    # Mount the dashboard at / last so /ws takes precedence.
    api.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
    return api


async def _push_state(websocket: WebSocket, link: Auralink) -> None:
    """Push a state snapshot to the browser ~5x/second."""
    try:
        while True:
            await websocket.send_text(json.dumps(link.get_state()))
            await asyncio.sleep(0.2)
    except (WebSocketDisconnect, RuntimeError):
        pass


def _handle_control(link: Auralink, raw: str) -> None:
    """Apply a control message from the browser."""
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        return
    action = msg.get("action")
    if action == "play":
        link.start_audio()
    elif action == "stop":
        link.stop_audio()
    elif action == "toggle_bio":
        link.set_bio_mode(not link.get_state()["bio_mode"])
    elif action == "set_bio":
        link.set_bio_mode(bool(msg.get("value", True)))
    elif action == "set_manual_bpm":
        link.set_manual_bpm(float(msg.get("value", 60.0)))


def serve(link: Auralink, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the dashboard server (blocking). Model must already be loaded."""
    import uvicorn

    print(f"AURALINK dashboard: http://{host}:{port}  (Ctrl-C to stop)")
    uvicorn.run(create_app(link), host=host, port=port)
