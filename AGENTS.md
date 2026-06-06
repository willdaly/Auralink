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

## Collaboration etiquette

- **Keep `main` demo-ready.** It is what the team presents from — never leave it
  broken. If a branch isn't working yet, keep it on the branch.
- **Stay on your own branch.** Don't commit to, rebase, or force-push a branch
  someone else is using. Only the branch author rewrites its history.
- **Push small and often.** Frequent, focused commits with clear messages make
  work-in-progress visible and reduce conflicts. Avoid giant, mixed commits.
- **No secrets in the repo.** Never commit API keys, tokens (e.g. a Hugging Face
  `HF_TOKEN`), or credentials. Use environment variables; add new ignore rules
  if needed.
- **Flag dependency changes.** If you add or bump a package, update
  `requirements.txt` and call it out so teammates re-run `uv pip install`.
- **Resolve conflicts by pulling/merging, not forcing.** When a push is
  rejected, `git pull` and integrate — never `git push --force` to fix it.
- **Don't reformat or refactor unrelated code.** Sweeping changes create noisy
  diffs and conflicts; keep each branch scoped to its stated purpose.
- **Coordinate before large or shared-file changes** (e.g. `auralink/app.py`,
  `requirements.txt`, this file) so two people don't rewrite the same thing.
- **Leave the workspace clean.** Don't commit local experiments, scratch files,
  or rendered audio; they belong in `.gitignore`.

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
- `auralink/engine.py` — `MagentaEngine`: MRT2 streaming, steerable via `set_style()`.
- `auralink/heartbeat.py` — heart-rate sources (simulated for demos; Arduino serial stub).
- `auralink/app.py` — orchestrator mapping heart rate → live Magenta style.

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
python -m auralink --selftest        # model loads + real-time check
python -m auralink --render 8        # render a WAV offline
```

## Conventions

- Do not commit large or generated artifacts: `.venv/`, model checkpoints,
  `*.wav`, `.DS_Store` (already covered by `.gitignore`).
- Match the existing code style; keep edits focused and avoid unrelated churn.
