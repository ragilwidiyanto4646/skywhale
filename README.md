[![make.fun — AI Excited 01](https://make.fun/badge/ai-excited-01.svg)](https://make.fun/bounty/ai-excited-01)
[![SKYWHALE rank on make.fun](https://make.fun/badge/ai-excited-01/ragilwidiyanto4646/skywhale/rank.svg)](https://make.fun/bounty/ai-excited-01)
[![SKYWHALE reward on make.fun](https://make.fun/badge/ai-excited-01/ragilwidiyanto4646/skywhale/reward.svg)](https://make.fun/bounty/ai-excited-01)

# SKYWHALE

A giant whale breaches upward through a sea of clouds over a tiny city at
golden sunset — one huge, instantly readable subject with a strong diagonal
momentum from tail (bottom-left) to head (top-right), bold flat colours, a
sunset rim light along its back, and a burst of spray at its nose.

Built as an entry for the make.fun bounty
[ai-excited-01](https://make.fun/bounty/ai-excited-01) — "Make the AI judge
excited".

## How it works

`main.py` is a pure Python 3 standard-library program: a scanline vector
rasterizer (spans, ellipse spans, polygon fill) draws the scene procedurally
— sky gradient, sun, clouds, the whale (Bézier body, belly band, rim light,
eye, mouth, fin, flukes, spray) and the tiny lit city — and a `zlib` PNG
encoder writes exactly one 1024×1024 image to
`$MAKEFUN_OUTPUT_DIR/entry.png` (or `/output/entry.png`).

No network, no external assets, no randomness beyond a fixed seed: every
run writes byte-identical output.

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```
