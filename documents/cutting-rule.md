# How it decides what to cut

**Keep by default.** Only three things are removed, and each has to be
positively identified:

| removed | how it is recognised | reference VOD |
|---|---|---|
| the opponent's adventure-map turn | clock overlay up, their digits ticking regularly, Tieulinh's not | 44:00 |
| HotA lobby / menu / reconnect screens | template match against `templates/` | 18:59 |
| waiting while the opponent fights | both clocks frozen, but the map is still on Tieulinh's screen | 7:38 |

Everything else is kept: combat, the tactics phase, the spell book, towns, hero
screens, level-up dialogs, and games played with no timer at all.

The rule lives in `tlh/segments.py`; every coordinate and threshold it depends
on is in `tlh/config.py`.

## Why not the obvious rule

The intuitive rule is "cut whenever Tieulinh's clock is frozen". It is wrong,
and it fails in the most expensive possible way. Facts found the hard way while
building this, each of which breaks that rule:

1. **Combat freezes BOTH clocks.** HotA stops the timers for the duration of a
   battle. So the naive rule cuts every fight — on the reference VOD it threw
   away **23:49 of real gameplay**, essentially all the combat.

2. **"Both clocks frozen" is ambiguous.** It means *somebody* is in a battle.
   If it is Tieulinh, keep it; if it is the opponent and Tieulinh is sitting on
   the map waiting, cut it. The two are told apart by the bottom of the screen:
   the adventure map shows the blue resource bar, combat a wooden status bar
   (`mean(blue) - mean(red)` is about +45 on the map and about -42 in combat, so
   the threshold of +10 has a wide margin).

3. **HotA sometimes hides the clock overlay entirely** — during combat in some
   games, and in town, hero and dialog screens. "No clock" therefore does *not*
   mean "nothing is happening"; on the reference VOD, 17:52 of the 32:37 with no
   clock visible was real play.

4. **Some games run with no timer.** From 1:35:54 to 1:52:24 of the reference
   VOD there is no clock overlay at all for ~16 minutes of ordinary gameplay.

5. **Tieulinh is not always the same colour.** The HUD seats the red player on
   the left of the centre title and the blue player on the right, always — so
   the *seat* fixes the colour, and Tieulinh changes seats between games. On the
   reference VOD Tieulinh is blue except for 1:35:54–1:52:24, playing red.

6. **HotA opens with simultaneous turns.** Early on both clocks run at once
   because both players are moving. Tieulinh's clock running is what matters, so
   these stretches are kept, and they are a large share of the early game.

7. **Sampling at 1 fps aliases against a 1 Hz clock.** Two consecutive samples
   can land inside the same clock second and look frozen mid-turn. Fixed by
   sampling at 2 fps and asking whether the clock moved anywhere in a window.

8. **A binary colour mask is not stable enough.** Thresholding "is this pixel
   blue" flips borderline pixels every time the encoder emits a keyframe, which
   reads as a ticking clock every 7 seconds. Scoring blueness as a continuous
   value and thresholding the *difference* removes that.

9. **How MUCH the clock pixels changed cannot decide whether it is running.**
   The overlay is semi-transparent, so while the opponent moves their hero the
   map scrolls behind it and the anti-aliased edge pixels of a *frozen* clock
   genuinely change colour. Measured on such a stretch, a frozen clock reached
   **48** changed pixels against a running one's **42** — the two distributions
   overlap, and no threshold separates them. A tighter colour window gave the
   same 48 against 42; eroding the mask to keep only stroke cores made it worse
   still, 18 against 11.

   What does separate them is **regularity**. A clock ticking at 1 Hz changes in
   every one-second bin; scrolling map noise arrives in bursts and leaves bins
   untouched. On the same stretch the frozen clock reached 0.50 of its bins and
   the running one 1.00, and across the whole video the distribution is bimodal
   with a clear valley — only 199 of 8600 samples land between 0.4 and 0.6.
   `THR_REGULAR` sits in that valley. This cost two wrong fixes first: raising
   the threshold, then demanding two ticks per window. Both were chasing the
   noise rather than measuring the right thing, and both left whole opponent
   turns in the cut.

10. **The clock-present test needs both lines.** Checking only the upper line
    false-positives on the HotA lobby, whose blue table fills that band while the
    lower band stays empty.

11. **A minimum cut length has to be measured after padding, not before.**
    `MIN_CUT` is applied to the raw gap and padding then takes `PAD_PRE +
    PAD_POST` off it, so the real floor was 3.8 s: cuts that saved four seconds
    while costing a one-second transition, and a segment count that wobbled
    between 42 and 46 on sub-second sampling noise. `MIN_GAP` enforces the
    minimum on the final gaps.

## Transitions

Every join is fade out 0.3 s, hold black 0.4 s, fade in 0.3 s, on **video and
audio**. The audio fade is not cosmetic: cuts land mid-sentence in the
commentary, and without `afade` every join pops.

The black hold is appended to each segment during its own encode (`tpad` /
`apad`), so every file in the concat list comes from the same encoder with the
same parameters and the final join is a stream copy that cannot drift.
