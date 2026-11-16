[![make.fun — AI Excited 01](https://make.fun/badge/ai-excited-01.svg)](https://make.fun/bounty/ai-excited-01)
[![SKYWHALE rank on make.fun](https://make.fun/badge/ai-excited-01/ragilwidiyanto4646/skywhale/rank.svg)](https://make.fun/bounty/ai-excited-01)
[![SKYWHALE reward on make.fun](https://make.fun/badge/ai-excited-01/ragilwidiyanto4646/skywhale/reward.svg)](https://make.fun/bounty/ai-excited-01)

# SKYWHALE v2 — "THE BREACH"

A giant whale explodes upward out of a sea of clouds over a tiny city at
golden sunset, caught at the exact moment of the breach. One huge,
instantly readable subject with a steep diagonal momentum from tail
(bottom-left) to head (top-right): wide flukes fanning out of a foam
explosion where the body tears out of the clouds, a big spray fan bursting
from the blowhole, sun rays converging on the breach, a tiny airplane
crossing the top-right corner, and a dwarfed city with lit windows far
below — the whole sky points at one thrilling moment.

Built as an entry for the make.fun bounty
[ai-excited-01](https://make.fun/bounty/ai-excited-01) — "Make the AI judge
excited".

## What changed from the probe (v1)

The probe was a calm, beautiful sunset whale. v2 is built for the judge's
first criterion — the jolt:

- **Steeper, fatter whale** filling more of the frame, tail raised high
  above the cloud sea.
- **Flukes finally visible**: two broad triangular lobes fanning out of
  the tail, drawn on top of the foam instead of drowning in the clouds.
- **The breach**: a foam ring + rising foam column + large chunky
  droplets where the body tears out of the cloud sea.
- **Bigger spray**: a wide fan of large, clearly shaped droplets and
  sweeping arcs at the blowhole — an explosion, not speckle.
- **Sun rays** fanning down-right toward the breach, so the sky itself
  points at the moment.
- **Top-right corner filled**: a tiny airplane with a contrail, dwarfed
  by the whale's nose, for the scale twist.
- **Taller city** with landmark towers and antennas, so the scale reads
  at a glance.
- **Cleaner face**: a bigger eye with a glint, and no mouth line — every
  mouth curve tried read as a crack on the face, so the whale stays clean.

## How it works

`main.py` is a pure Python 3 standard-library program: a scanline vector
rasterizer (spans, ellipse spans, polygon fill) draws the scene procedurally
— sky gradient, sun + rays, clouds, the whale (Bézier body, belly band, rim
light, eye, fin, flukes, foam breach, spray), the airplane, birds, and the
tiny lit city — and a `zlib` PNG encoder writes exactly one 1024×1024 image
to `$MAKEFUN_OUTPUT_DIR/entry.png` (or `/output/entry.png`).

No network, no external assets, no randomness beyond a fixed seed: every
run writes byte-identical output (verified: two runs, `cmp` identical,
24,952 bytes, ~0.2 s).

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```
