# What it costs

Measured on the reference VOD (2h48, i5-13420H, Intel UHD graphics):

| stage | time |
|---|---|
| analysis, cold | 15 min |
| analysis, cached signal | 5 min |
| render, 41 segments -> 1:51 | 23 min |
| **total** | **~38 min** |

And on a 30-minute test slice (i3-10100F, 4 cores, NVENC):

| stage | time |
|---|---|
| analysis, cold | 2.4 min |
| render, 11 pieces (`--parts-only`) | 4.2 min |

## Analysis

Analysis was 8.4 min before the clock detector started asking for regular ticks
rather than large ones. Being stricter about calling a clock "running" pushes
more stretches into "both frozen", and each of those has to be screen-checked —
63 spans on the reference VOD against 32 before. The extra six minutes buy 6.5
minutes of opponent turn that the old rule left in the cut.

The signal is cached per video in `work/<name>/signal.npz`, and thresholds are
deliberately left out of the cache fingerprint: they are applied downstream in
`interpret()`, so a threshold can be retuned and re-derived in seconds without
decoding the video again. Coordinates and template files ARE in the
fingerprint, because changing one of those changes what the numbers mean.

**Do not reach for `-hwaccel` to speed the analysis up.** Measured here,
hardware decode ran at **1.1x realtime against 22x for software**, because
every frame has to be copied back from the GPU for OpenCV to look at it.

## Render

The render dominates, and it is bound by the hardware encoder rather than by
threads: on the reference machine 6 parallel encoders finished in 23.4 min
against 24.2 min for 3, because integrated graphics has a single encode engine.
Raising `--render-workers` therefore buys almost nothing there; a machine with
an NVIDIA card is roughly 3x faster at this stage.

## CPU

`--workers 4` runs one ffmpeg per physical core on a 4-core machine, and each
ffmpeg is itself multithreaded, so analysis will sit at 100% CPU for its whole
duration. That is a designed-for condition, not a risk: a CPU that gets too hot
lowers its own clock. What it does cost is responsiveness — the machine feels
sluggish while a pass is running.
