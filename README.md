#Auralink
## An adaptive bio-music instrument that translates interpersonal biometrics into generative, synchronized musical structures.

> **Built for the Music Technology Hackathon — Boston, 6–7 June 2026** (David Friend Recital Hall, Berklee College of Music), for the **Google DeepMind Challenge: _Build and play your own live AI instruments with [Magenta RealTime 2](https://github.com/magenta/magenta-realtime)._**
> Magenta RealTime 2 is the live AI instrument at the core of AURALINK; a person's heartbeat plays it in real time. See [HACKATHON.md](HACKATHON.md) for our charter and on-track tracker.

## What does it do?
AURALINK is an adaptive bio-music framework designed to break the static relationship between listeners and music. By capturing real-time biometrics (heart rate, respiration) and vocal inputs, the system treats the human body as a digital musical instrument (DMI). 

Its long-term core innovation is **Interpersonal Bio-Feedback**: when two users sync their Aura Links, the system dynamically generates musical structures based on their physiological relationship. If their heart rates align, the harmony resolves; if they differ, the system creates complex polyrhythms and syncopations (e.g., one heart triggers the kick drum, the other dictates the subdivision). It acts as a shared biological canvas for wellness, performance, and human connection. **For this hackathon we are focused on a single user**; the two-user interpersonal mode is a future goal for development after the event.

## What we plan to build during this Hackathon:
We want to create a working Minimum Viable Product (MVP) **for a single user**:
1. **Low-Latency Hardware:** A sensor setup that captures cardiac peaks (systole) with minimal delay.
2. **Audio Engine Bridge:** A Max/MSP (or Pure Data/Ableton Live) patch that translates biometric triggers into MIDI parameters (e.g., your heartbeat triggers a TR-808 kick drum in real-time).

### Future goal (post-hackathon)
- **Dual-User Framework:** A basic interactive template where two distinct pulses can generate counterpoint, syncopation, and cross-modulations. This is a future goal for after the hackathon, not part of the MVP.

## Who I am & Who I'm looking for:
I am a student at Berklee College of Music with an Audio Engineering background from SAE Institute. I bring the music theory, psychoacoustic concepts, audio signal flow, and the core vision for the adaptive composition templates (defining how parameters like HRV or pitch shift modulate harmonic extensions, filters, and dynamic ranges).

**I am looking for hackers to join the team!** Especially:
* **Hardware/Embedded Systems geeks** (Arduino, ESP32, or sensor hacking).
* **Creative Coders** (Max/MSP, Pure Data, Python for DSP, or Ableton Live/Max for Live integration).
* **UI/UX or Frontend developers** if we want to visually map the data in real-time.

## What's interesting about it?
Instead of just generating music *for* someone, AURALINK turns empathy and physiology *into* the composition itself. It shifts the paradigm from passive streaming to organic, shared audio improvisation—giving a completely new meaning to "jamming" with someone.

Let's turn collective physiology into live composition

## How it works (live instrument)
A heartbeat plays Magenta RealTime 2 as a live instrument — **Magenta generates all of the audio, including the four-on-the-floor TR-808 kick. There are no samples.**

```
body (heartbeat)  ->  signal (BPM)  ->  Magenta RealTime 2  ->  sound
```

The heart rate steers Magenta in real time: its heart-rate zone selects the live prompt (calm pads → steady 808 groove → driving techno → peak-time rave) and fills the tempo into the prompt, all re-embedded on the fly. Until the Arduino pulse sensor arrives, a simulated heartbeat drives the whole pipeline so it is demoable today.

**Components**
- [auralink/engine.py](auralink/engine.py) — `MagentaEngine`: MRT2 (`mrt2_small`) streaming continuously, steerable live via `set_style()`. This is the instrument.
- [auralink/heartbeat.py](auralink/heartbeat.py) — `SimulatedHeartbeat` (demo) and `SerialHeartbeat` (Arduino, ready for hardware).
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

`MagentaEngine.set_style()` is the live-control hook; the heartbeat calls it to retune Magenta from a real pulse in real time. See [HACKATHON.md](HACKATHON.md) for the challenge charter.

