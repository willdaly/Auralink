# AGENTS.md — instructions for AI coding agents

This repository is built by multiple people during a hackathon. To avoid many
agents pushing to `main` at once, follow this Git workflow.

## Git workflow (required)

**Never commit or push directly to `main`.** Always work on a feature branch.

1. Before making changes, create and switch to a feature branch off the latest `main`:
   ```bash
   git switch main && git pull --ff-only
   git switch -c <type>/<short-description>
   ```
   Branch name format: `<type>/<short-description>`, where `<type>` is one of
   `feat`, `fix`, `chore`, `docs`, or `refactor` (e.g. `feat/heartbeat-serial`,
   `fix/audio-underrun`).

2. Commit your work to that branch and push the branch (not `main`):
   ```bash
   git add -A
   git commit -m "<concise message>"
   git push -u origin <branch-name>
   ```

3. Open a Pull Request into `main` for review. Do not merge your own PR without
   a teammate's review unless told otherwise.

## Rules

- If you find yourself on `main`, **stop** and create a feature branch before
  committing. Use `git switch -c <branch>` (uncommitted changes move with you).
- Do not run `git push` to `main`, and never use `git push --force`.
- Keep each branch focused on one feature or fix.
- If the user explicitly asks you to commit to `main`, confirm once before doing so.
- Pull the latest `main` before branching so branches don't drift.
- Do not delete or force-overwrite work you don't recognise — it may be a
  teammate's in-progress changes. Ask first.

## Project overview

AURALINK is a bio-music instrument built for the **Google DeepMind / Magenta
RealTime 2** challenge: a heartbeat plays Magenta RealTime 2 as a live AI
instrument. See [HACKATHON.md](HACKATHON.md) for the full charter and the
anti-drift checklist, and [README.md](README.md) for how it works.

## The challenge (stay oriented to this)

- **Event:** Music Technology Hackathon, Boston, 6–7 June 2026 (Berklee).
  <https://musichackspace.org/events/hackathon-boston-june-2026>
- **Track:** Google DeepMind Challenge — *"Build and play your own live AI
  instruments with Magenta RealTime 2."* ($2,000 prize.)
- **Judged on:** creativity, technical execution, and real-world product potential.
- **Hard requirement:** **Magenta RealTime 2 must be the live instrument in the
  signal path.** Magenta generates all audio (including the kick) — do not
  replace it with samples or a synth. If a change makes the demo work *without*
  Magenta, it is off-challenge: stop and reconsider.

Before a non-trivial change, sanity-check it against this and the anti-drift
checklist in [HACKATHON.md](HACKATHON.md).

Key files:
- `magenta_engine.py` — `MagentaEngine`: MRT2 streaming, steerable via `set_style()`.
- `heartbeat.py` — heart-rate sources (simulated for demos; Arduino serial stub).
- `auralink.py` — orchestrator mapping heart rate → live Magenta style.

## Dev environment

Apple Silicon required (MLX backend). Python 3.12 in a local `.venv`:

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -r requirements.txt
# One-time model download:
mrt models init
mrt checkpoints download mrt2_small.safetensors
```

Verify changes without an audio device before committing:

```bash
python auralink.py --selftest        # model loads + real-time check
python auralink.py --render 8        # render a WAV offline
```

## Conventions

- Do not commit large or generated artifacts: `.venv/`, model checkpoints,
  `*.wav`, `.DS_Store` (already covered by `.gitignore`).
- Match the existing code style; keep edits focused and avoid unrelated churn.
