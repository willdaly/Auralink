#!/usr/bin/env python3
from __future__ import annotations

import argparse

from .auralink import Auralink, hr_to_style
from .engine import SAMPLE_RATE, MagentaEngine
from .heartbeat import (
    HeartbeatSource,
    PulsoidHeartbeat,
    SimulatedHeartbeat,
    check_pulsoid,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="auralink", description=__doc__)
    parser.add_argument("--bpm", type=float, default=60.0, help="Base heart rate (BPM).")
    parser.add_argument(
        "--steady", action="store_true", help="Pin a fixed heart rate (no drift)."
    )
    parser.add_argument("--size", default="mrt2_small", help="Magenta model variant.")
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.9,
        help="Magenta sampling temperature. Lower = steadier kick (default 0.9).",
    )
    parser.add_argument(
        "--cfg-drums",
        type=float,
        default=6.0,
        help="Drum-pulse authority (classifier-free guidance). Higher = the kick "
        "locks to the heart-rate pulse more strongly over the style (default 6.0).",
    )
    parser.add_argument(
        "--render",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Render to a WAV instead of playing live (no audio device needed).",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Generate a few Magenta chunks, report real-time factor, then exit.",
    )
    parser.add_argument(
        "--pulse-test",
        type=float,
        default=None,
        metavar="SECONDS",
        help="De-risk spike: render SECONDS of audio with a drum pulse train at "
        "--bpm (Magenta's MIDI-like drum onset per frame) and write a WAV.",
    )
    parser.add_argument(
        "--pulsoid",
        action="store_true",
        help="Use a live Pulsoid heart rate (e.g. Apple Watch) instead of the "
        "simulated heartbeat.",
    )
    parser.add_argument(
        "--pulsoid-token",
        default=None,
        help="Pulsoid access token. Defaults to the PULSOID_TOKEN env var. "
        "Keep it secret; never commit it.",
    )
    parser.add_argument(
        "--pulsoid-check",
        action="store_true",
        help="Connect to Pulsoid and print live heart-rate messages for a few "
        "seconds, then exit. Verifies the token/watch without loading Magenta.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Launch the web dashboard (frontend/) and stream live heart-rate / "
        "tempo / zone state to the browser. Audio still plays locally.",
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port for --serve (default 8000)."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Load a local .env (e.g. PULSOID_TOKEN) if python-dotenv is installed.
    # Optional: the app still works with plain environment variables.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    # Quick Pulsoid connectivity check — no Magenta model needed.
    if args.pulsoid_check:
        return check_pulsoid(token=args.pulsoid_token)

    engine = MagentaEngine(
        size=args.size,
        temperature=args.temperature,
        cfg_drums=args.cfg_drums,
    )
    engine.load_model()

    if args.selftest:
        engine.set_style(hr_to_style(args.bpm)[1])
        engine.selftest()
        return 0

    if args.pulse_test is not None:
        import soundfile as sf

        label, prompt = hr_to_style(args.bpm)
        engine.set_style(prompt, label=f"{label} @ {args.bpm:.0f} BPM")
        audio = engine.render_pulse(args.bpm, args.pulse_test)
        path = f"auralink_pulse_{int(round(args.bpm))}bpm.wav"
        sf.write(path, audio, SAMPLE_RATE)
        print(f"Wrote {path} ({args.pulse_test:g}s).")
        return 0

    if args.pulsoid:
        heart: HeartbeatSource = PulsoidHeartbeat(token=args.pulsoid_token)
    else:
        heart = SimulatedHeartbeat(bpm=args.bpm, drift=0.0 if args.steady else 8.0)
    app = Auralink(engine=engine, heart=heart)

    if args.serve:
        from .server import serve

        serve(app, port=args.port)
    elif args.render is not None:
        app.render(args.render)
    else:
        app.run()
    return 0
