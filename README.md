#Auralink
## An adaptive bio-music instrument that translates interpersonal biometrics into generative, synchronized musical structures.

> **Built for the Music Technology Hackathon — Boston, 6–7 June 2026** for the **Google DeepMind Challenge: _Build and play your own live AI instruments with [Magenta RealTime 2](https://github.com/magenta/magenta-realtime)._**
> Magenta RealTime 2 is the live AI instrument at the core of AURALINK; a person's heartbeat plays it in real time.

## What does it do?
AURALINK is an adaptive bio-music framework designed to break the static relationship between listeners and music. By capturing real-time biometrics (heart rate), the system treats the human body as a digital musical instrument (DMI). 

## Contributors:
Javier Roqueni
I am a student at Berklee College of Music with an Audio Engineering background from SAE Institute. I bring the music theory, psychoacoustic concepts, audio signal flow, and the core vision for the adaptive composition templates (defining how parameters like HRV or pitch shift modulate harmonic extensions, filters, and dynamic ranges).

Will Daly
Graduate Student in Artificial Intelligence at Northeastern University. Background in music production and yoga instruction.

Dania Myers
Self-taught frontend developer transitioning into full stack coding program. Background in Entrepreneurship.

## What's interesting about it?
Instead of just generating music *for* someone, AURALINK turns empathy and physiology *into* the composition itself. It shifts the paradigm from passive streaming to organic, shared audio improvisation—giving a completely new meaning to "jamming" with someone.

Let's turn collective physiology into live composition

## How it works (live instrument)
A heartbeat plays Magenta RealTime 2 as a live instrument — **Magenta generates all of the audio, including the four-on-the-floor TR-808 kick.**

```
body (heartbeat)  ->  signal (BPM)  ->  Magenta RealTime 2  ->  sound
```

The heart rate steers Magenta in real time: its heart-rate zone selects the live prompt (calm pads → steady 808 groove → driving techno → peak-time rave) and fills the tempo into the prompt, all re-embedded on the fly. A live heart rate comes from [Pulsoid](https://pulsoid.net/) (e.g. an Apple Watch); a simulated heartbeat drives the whole pipeline when no monitor is connected, so it is always demoable.

**Components**
- [auralink/engine.py](auralink/engine.py) — `MagentaEngine`: MRT2 (`mrt2_small`) streaming continuously, steerable live via `set_style()`. This is the instrument.
- [auralink/heartbeat.py](auralink/heartbeat.py) — `SimulatedHeartbeat` (demo) and `PulsoidHeartbeat` (live heart rate via Pulsoid, e.g. an Apple Watch).
- [auralink/app.py](auralink/app.py) — orchestrator mapping heart rate → Magenta style.

**Requirements:** Apple Silicon Mac (`mrt2_small` streams in real time on an M1 Pro).

**Setup:**
```bash
# Create and activate a Python 3.12 environment
uv venv --python 3.12
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# One-time: download Magenta resources + the small model
mrt models init
mrt checkpoints download mrt2_small.safetensors
```

**Run:**
```bash
# Play live: simulated heartbeat -> Magenta (Ctrl-C to stop)
python -m auralink
python -m auralink --bpm 80 --steady     # pin a fixed heart rate

# Render to a WAV instead of playing live (no audio device needed)
python -m auralink --render 12 --bpm 90

# Quick model + real-time check
python -m auralink --selftest
```

**Live heart rate (Pulsoid):**
Stream your heart rate from an Apple Watch (or any monitor) via
[Pulsoid](https://pulsoid.net/).
```bash
# 1. Create a Manual Token at https://pulsoid.net/ui/keys
#    with the data:heart_rate:read scope.
# 2. Put it in a local .env (gitignored):
cp .env.example .env        # then edit .env and set PULSOID_TOKEN=...

# 3. Verify the feed without loading Magenta (start your watch streaming first):
python -m auralink --pulsoid-check

# 4. Play live from your heartbeat:
python -m auralink --pulsoid
```


`MagentaEngine.set_style()` is the live-control hook; the heartbeat calls it to retune Magenta from a real pulse in real time. See [HACKATHON.md](HACKATHON.md) for the challenge charter.

