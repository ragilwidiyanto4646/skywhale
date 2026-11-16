[![make.fun — AI Excited 01](https://make.fun/badge/ai-excited-01.svg)](https://make.fun/bounty/ai-excited-01)
[![SKYWHALE rank on make.fun](https://make.fun/badge/ai-excited-01/ragilwidiyanto4646/skywhale/rank.svg)](https://make.fun/bounty/ai-excited-01)
[![SKYWHALE reward on make.fun](https://make.fun/badge/ai-excited-01/ragilwidiyanto4646/skywhale/reward.svg)](https://make.fun/bounty/ai-excited-01)

# SKYWHALE v3 — "THE BREACH" (full rewrite)

A whale the size of a skyscraper rips itself out of a sunset sea at the
exact second of the breach. The whole frame is one diagonal surge: the
tail is still underwater, the flukes are fanned flat across the foam, the
body arcs up through the orange sky, and the head — eye glinting, jaw
set — is already above the sun, with the blowhole blast scattering
droplets across the top of the frame.

The surprise is the scale. Down on the horizon a whole city stands with
its windows lit, and a jet crosses the top-right corner trailing a
contrail — both of them tiny next to the animal. The sun sits low behind
the whale's shoulder, its light path glittering across the water straight
toward the breach, so every element in the picture points at the same
single thrilling moment.

This is an entry for the make.fun bounty
[ai-excited-01](https://make.fun/bounty/ai-excited-01) — "Make the AI
judge excited". If you like the project, you can join make.fun through
my referral link: https://make.fun/r/ztnjpsw2

## Why a full rewrite (v3 vs v2)

Round 2 was rejected by the server's transcript gate, not by the judge:
it was an incremental edit of the probe, so too little of the code
counted as authored in the recorded session. v3 is therefore written
from zero in one recorded session, with a different renderer
architecture (a row-buffer `Canvas` with spans and alpha blends, a
tube-along-a-spine whale instead of polygon body parts, a per-row
filter-choosing PNG encoder) — and the picture itself was rebuilt
alongside it:

- **Leaner, more diagonal whale**: the spine runs from the lower-left
  tail to a head high on the right, and the mid-body is slimmer, so the
  animal reads as a breaching whale instead of a vertical blob.
- **Flukes that read as flukes**: two broad, flat lobes with pale
  undersides, spread wide across the bottom of the frame.
- **Foam that stays at the water**: the breach ring, the rising column
  and the droplet fans are all placed around the waterline, and every
  droplet is tested against the whale's silhouette so none of them
  lands on the body like a barnacle.
- **Spray, not a target**: the blowhole blast is a dense droplet core
  plus a wide fan, with only three faint sweeping arcs behind it.
- **Sun moved clear of the whale**: the disc and its halo now show in
  full at the right of the head, with rays fanning down toward the
  breach point.
- **Quieter details**: a shorter rim-light dash, a smaller tucked fin,
  a soft-feathered belly edge, and a clean face with just an eye, a
  glint, and a faint jaw line.

## How the picture is made

`main.py` is a pure Python 3 standard-library program — no packages, no
network, no external assets. It works in layers:

1. **Sky and light** — a five-stop vertical gradient from deep violet
   to gold, the sun with a layered halo, translucent ray wedges aimed
   at the breach, and thin high cloud wisps.
2. **The world below** — a rolling cloud sea on the horizon, a tiny
   lit skyline with two antenna towers, and the dark sea with a
   glittering sun path, swell lines and drifting foam flecks.
3. **The whale** — a tapered tube of overlapping discs along a
   quadratic Bézier spine, with a darker outline pass, a pale belly
   tube offset to the lower side, a sunlit rim dash, a snout, an eye
   with a glint, one tucked pectoral fin, and the fanned flukes.
4. **Water in motion** — the foam ring at the waterline, the foam
   column hugging the tail, two droplet fans that are checked to
   clear the body, and the blowhole spray.
5. **Scale cues** — the jet with its contrail in the top-right
   corner and a few distant gulls.

A small PNG writer then encodes the 1024×1024 buffer: for every row it
tries all five PNG filters and keeps the one that compresses best, so
the file stays well under the 1 MiB limit. Everything random comes
from one fixed seed (`SEED = 20261117`), so every run writes
byte-identical output — verified: two runs to fresh directories,
`cmp` identical, 88,226 bytes, ~4.4 s per run.

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

The program writes `entry.png` to `$MAKEFUN_OUTPUT_DIR` (or
`/output/entry.png` when the variable is not set), which is where the
bounty harness reads it.
