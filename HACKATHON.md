# AURALINK — Hackathon Charter & On-Track Tracker

> Single source of truth to keep us aligned with the challenge we entered.
> Re-read the **Anti-Drift Checklist** before every major coding decision.

## The event
- **Music Technology Hackathon** — Boston, **6–7 June 2026**
- David Friend Recital Hall, Berklee College of Music
- Co-hosted by Music Hackspace + Berklee (following the AIMS conference)

## The challenge we're building for
**Google DeepMind Challenge — Magenta RealTime 2**
- Tagline: *"Build and play your own live AI instruments with Magenta RealTime 2."*
- 💰 $2,000 cash prize (premium challenge sponsor)
- Repo: https://github.com/magenta/magenta-realtime
- Magenta jury member: **Ilaria Manco** (Google DeepMind Magenta)
- Magenta mentors on site: Jesse Engel, Ethan Manilow, Kehang Han, Yotam Mann, David Braun

### Non-negotiable requirement
**Magenta RealTime 2 must be the live AI instrument at the core of the demo.**
If MRT2 can be removed and the demo still works, we are off-challenge.

## Judging criteria (build toward these)
1. **Creativity** — original musical interaction; not a generic generator.
2. **Technical execution** — it works live, in real time, on stage.
3. **Real-world product potential** — a believable path beyond the weekend.
   - Optional cross-cutting prize: **MIDI Association "Most Accessible Product"** (opt in at submission if accessibility is a real design driver).

## Our north star (AURALINK)
An adaptive bio-music instrument: **live human biometrics (heart rate) play
Magenta RealTime 2 as a musical instrument.**

**Hackathon scope: a single user.** One person's heartbeat plays Magenta live.
Two-user interpersonal counterpoint is a compelling extension but is a
**post-hackathon future goal** (see Build plan) — we are not building it this
weekend.

The heartbeat is the *controller*; **Magenta RT2 is the instrument/sound engine.**

## Definition of "on-challenge" (Definition of Done for the demo)
- [ ] MRT2 is generating live audio during the demo (not a pre-baked file).
- [ ] A live human signal (heartbeat / biometric) controls MRT2 in real time.
- [ ] The mapping is musically meaningful and visible to the audience.
- [ ] Runs end-to-end on the M1 Pro without manual babysitting.
- [ ] A clear 2-minute story: body → signal → Magenta → sound.

## Anti-Drift Checklist (read before each decision)
1. Does this change keep **Magenta RT2 in the live signal path**? If no → stop.
2. Is Magenta the **instrument**, or did it slip to a side feature? Keep it central.
3. Are we polishing something the judges won't hear? Refocus on the live loop.
4. If we're using a raw sample/synth, is it **supporting** Magenta, not replacing it?

> Lesson learned (6 Jun): we briefly replaced the MRT2 kick with a plain sample
> sequencer. It sounded clean but used **zero Magenta** — off-challenge. A sample
> may support the groove, but Magenta must remain the live instrument.

## Build plan (in priority order)
- **P0 — Magenta live loop:** MRT2 streaming continuously on the M1 Pro using
  `mrt2_small` (real-time on this chip). This is the heartbeat of the demo.
- **P0 — Control hook:** a `set_*()` API that retargets MRT2 live (style/prompt,
  tempo, drum/note conditioning) so an external signal can drive it.
- **P1 — Biometric input:** Arduino heart-rate → BPM / onsets feeding the hook.
  Until hardware arrives, drive the hook from a **simulated heartbeat** so the
  whole pipeline is demoable today.
- **P1 — Musical mapping:** define how HR maps to MRT2 (tempo, intensity, prompt
  mood, drum density). Make it audibly responsive.
- **P2 — Sound design polish & a kick that actually sounds good** (prompt tuning,
  lower temperature, `drums` conditioning; sample only as a supporting layer).
- **P3 — Visuals** mapping the live data for the audience.

### Future goals (post-hackathon)
- **Two-user / interpersonal counterpoint:** two pulses → counterpoint /
  polyrhythm from the players' physiological relationship. Likely via Pulsoid
  **room mode** (each member streams BPM to a shared channel). This is the
  product's long-term differentiator but is **out of scope for the hackathon** —
  we are focused on getting one user working end-to-end first.

## Sound-quality notes for MRT2 (the earlier kick sounded bad — fixable in Magenta)
- NO SAMPLES. Magenta generates the kick and everything else.
- Prompt richer than "kick drum": e.g. *"punchy four-on-the-floor techno kick,
  tight, driving, deep sub"* (see HR_ZONES in auralink/app.py).
- Lower `temperature` (~1.0) for a steadier kick; `drums=[1]` conditioning is on.
- Generate a full groove (kick + bass + texture), not an isolated transient.

## Current status
- ✅ Env ready: `.venv` (py3.12), `magenta-rt[mlx]` installed, `mrt2_small`
  checkpoint + shared resources downloaded. MRT2 generates at ~0.78× real-time
  factor on the M1 Pro (keeps ahead of playback).
- ✅ **On-challenge live instrument working.** `auralink/app.py` = heartbeat → MRT2
  style; Magenta generates ALL audio (kick included). **No samples.**
  - `auralink/engine.py` — MagentaEngine (live streaming + `set_style()` hook).
  - `auralink/heartbeat.py` — SimulatedHeartbeat (demo) + SerialHeartbeat (Arduino stub).
  - Verified: `--selftest` real-time OK; `--render` produces valid Magenta audio.
- ⏭ Next: tune kick prompt/temperature for punch; wire live heart rate (Pulsoid /
  Arduino) for one user. Two-user counterpoint is a post-hackathon future goal.

## Logistics
- **Sun 7 Jun, 4:00 PM** — team presentations. 3:00 PM doc/prep phase.
- Venue closes 11 PM Sat (no overnight). Build accordingly.
