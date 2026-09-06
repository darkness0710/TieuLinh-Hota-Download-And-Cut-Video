"""Every coordinate and threshold the detector depends on.

If a VOD uses a different overlay layout, THIS is the file to change -- the
logic in the other modules does not hardcode any geometry. Rebuild the
reference crops with `tools/make_templates.py` and check coordinates with
`tools/inspect_frames.py grid`.

All coordinates assume a 1920x1080 frame.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"

# ------------------------------------------------------------- sampling ----
SR = 2.0            # signal samples per second. The H2H clocks tick at 1 Hz, so
                    # sampling at exactly 1 fps aliases: two consecutive samples
                    # can land inside the same clock second and look frozen.

# --------------------------------------------------------- clock overlay ----
# One crop holds both clock lines; the band slices are relative to that crop.
CLK = (30, 44, 90, 50)                        # x, y, w, h
# The two clock lines, named by POSITION, never by colour. Which colour sits on
# which line is not fixed: the upper line belongs to whoever holds slot 1, and
# Tieulinh's colour changes from game to game. signal.py therefore measures both
# colours in both lines and lets the pixels say which line is which. Hard-coding
# "upper is blue" read the wrong colour in both lines of the [LKnJTE1fPyg] VOD,
# scored 0/12 on overlay presence against 11/12 with the lines swapped, and made
# every clock look permanently frozen -- so nothing was ever cut.
UPPER_BAND = (slice(2, 18), slice(5, 85))
LOWER_BAND = (slice(30, 48), slice(5, 85))

# ------------------------------------------------------------ name slots ----
# The tournament HUD seats the two players either side of the centre title, and
# the seat fixes the colour: LEFT seat is always the red player, RIGHT seat the
# blue one. Tieulinh switches seats between games, so the colour must be read
# per game rather than assumed once.
NAME_L = (620, 8, 224, 38)                    # x, y, w, h -- left seat  (red)
NAME_R = (1100, 8, 224, 38)                   # x, y, w, h -- right seat (blue)
# Widths and offsets MUST stay even: the source is yuv420p, so ffmpeg rounds an
# odd crop down, and the stacked branches then disagree on width.

# Where the "Tieulinh HOTA" reference crop is taken from, as (y0, y1, x0, x1).
# Only tools/make_templates.py uses this; matching searches the whole slot.
TIEULINH_TPL = (14, 38, 1112, 1232)

# ----------------------------------------------------------- day counter ----
# "Month: 1, Week: 3, Day: 3" at the bottom right, present on every in-game
# screen -- adventure map, combat, town, hero -- and absent in the lobby and
# menus, where the reader simply finds no digits.
#
# Two things make a fixed brightness threshold fail here, and both were measured
# rather than guessed: in combat and in a game played without a timer the whole
# bottom panel is DIMMED (text peak 250 -> 228, p90 167 -> 97), so the strip is
# binarised with Otsu; and in that same variant the leading "M" of "Month:" is
# clipped, which is why nothing keys off that word.
DAY = (1600, 1044, 248, 32)                   # x, y, w, h -- the counter strip
# Digit windows, relative to the DAY crop. Measured across map, combat and the
# no-timer game: positions vary by at most 2 px.
DIGIT_X = {"month": (68, 96), "week": (145, 173), "day": (208, 240)}
DIGIT_Y = (4, 28)
# A digit blob is 13-14 px tall and at least 4 wide. The comma after the month
# and week values is about 7 tall, the panel border that clips the right of the
# day window is the full 24, and single-pixel columns are compression fringe --
# an absolute range separates all of them, where a fraction of the window
# height does not (the obvious 0.6 lands at 14.4 and rejects every real digit).
GLYPH_H = (10, 20)
GLYPH_W_MIN = 3
# How far apart two blobs can sit and still belong to the same number.
# Measured on the [LCPHoRAiE18] VOD, whose bottom panel sits about ten pixels
# right of where the windows were measured, so the label's colon falls inside
# the digit window: colon to digit is 7-9 px in all three fields, while the
# letters inside a word are 1 px apart and the digits of a number no more.
# Five separates the two with room on both sides.
GLYPH_GAP = 5

# --------------------------------------------------------- PvP combat ----
# A battle screen shows a hero panel per side, each with a "Spell Points" line.
# Two of them means hero against hero; one means the fight is against neutral
# guards. Both land at fixed pixels -- left (190, 288), right (1637, 288) -- in
# every battle checked, and the score separates cleanly: 0.95+ when the panel is
# there against at most 0.35 on an adventure map, town, hero screen, lobby or
# menu. This is far sharper than judging a battle by the colour of the bottom
# bar, which cannot tell combat from a tavern or an open spell book.
SPELL_L = (186, 284, 106, 30)                 # x, y, w, h -- text lands at 190
SPELL_R = (1632, 284, 108, 30)                # text lands at 1637; x must be even
# Both hero panels on screen means a fight between the two players. The
# template is cut from one VOD, and another draws the same panel at another
# size, so it is searched over scales the way the name plate is.
SPELL_SCALES = (0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15)
# Measured on [LCPHoRAiE18], twelve combat frames and fifteen that are not,
# all read by eye first because "both clocks stopped" covers towns and the
# lobby as well as fights: combat scored 0.52 at worst and everything else
# 0.29 at best. The old 0.70 was above BOTH clusters, so that VOD came out
# with no combat chapters at all -- and over 32 minutes the answer is the
# same three battles at every threshold from 0.50 down to 0.30, which is a
# plateau wide enough to sit in the middle of. This only ever moves chapter
# labels: nothing in the keep/cut rule reads it.
THR_SPELL = 0.42

# ------------------------------------------------------- map vs combat ----
# The bottom bar is the cheapest reliable way to tell the adventure map from a
# battle: the map shows the blue resource bar, combat a wooden status bar.
BAR = (350, 1035, 1000, 40)                   # x, y, w, h
THR_BAR = 10.0                                # mean(blue) - mean(red) above this => map

# ----------------------------------------------------- dead-screen crops ----
# Regions matched against templates/ to recognise screens where nothing is
# being played. Values are (y0, y1, x0, x1).
DEAD_REG = {
    "lobby_header": (172, 200, 40, 770),      # room-list header row
    "lobby_buttons": (1008, 1058, 20, 870),   # NEW GAME / LOAD GAME / JOIN
    "menu_options": (878, 912, 980, 1520),    # Show Advanced Options / More Options
    "menu_logo": (44, 270, 330, 950),         # HORN OF THE ABYSS title art
    "reconnect_abort": (644, 704, 864, 1060), # ABORT button of the reconnect dialog
}
DEAD_PAD = 20                                 # search slack around each region
THR_TPL = 0.75                                # match score that confirms a dead screen

# ------------------------------------------------------------ detection ----
THR_TICK = 5        # changed digit pixels that count as "this clock moved".
                    # 15 was set from the magnitude of a frozen clock's noise
                    # alone, without checking what a RUNNING one produces on
                    # each line. The two lines are not alike: the red digits
                    # carry ~610 ink pixels and the blue ones ~234, so a real
                    # blue tick shows up as 5-48 changed pixels and 15 threw
                    # away nearly half of them. Measured against turns whose
                    # owner was read off the digits, the running line's
                    # regularity fell to 0.48 -- under THR_REGULAR -- and whole
                    # opponent turns survived the cut. Noise is not what 15 was
                    # protecting against anyway: it is rejected by regularity,
                    # not by magnitude, and dropping to 5 leaves the frozen
                    # line at 0.00-0.05 while lifting the running one to
                    # 0.75-0.89.
WIN = 8             # +/- samples for the tick window, to absorb 1Hz/2fps
                    # aliasing. Also sets the resolution of the regularity
                    # score, which is quantised to (2*WIN+1)//SR bins: WIN=4
                    # gave only 4 bins, so a true value near THR_REGULAR landed
                    # on the wrong side about half the time and the cut mask
                    # came out dashed rather than solid. Merging in segments.py
                    # then joined the gaps and kept the whole turn. WIN=8
                    # doubles the bins and takes the two verified opponent
                    # turns from 54%/28% covered to 100%/87%, with no part of
                    # Tieulinh's own verified turn cut in any setting tried.
THR_REGULAR = 0.6   # fraction of one-second bins in that window that must show
                    # a change before the clock counts as running.
                    #
                    # Magnitude cannot decide this. The clock overlay is
                    # semi-transparent, so when the map scrolls behind it -- which
                    # is exactly what happens while the opponent moves -- the
                    # anti-aliased edge pixels of the digits genuinely change
                    # colour. Measured on such a stretch: a frozen clock produced
                    # differences up to 48 pixels while a running one sat at 42,
                    # and neither a higher threshold, a tighter colour window nor
                    # eroding the mask separated them.
                    #
                    # Regularity does. A clock ticking at 1 Hz changes in every
                    # one-second bin; scrolling map noise arrives in bursts and
                    # leaves bins untouched. On the same stretch the frozen clock
                    # reached 0.50 and the running one 1.00, with a clear valley
                    # between the two modes across the whole video.
CLOCK_GAP = 2.0     # seconds of stillness to forgive INSIDE an otherwise
                    # steady run of a clock. A running clock scores 0.75-1.00
                    # on regularity, but the digits themselves sometimes hold
                    # for a couple of seconds, and then the score straddles
                    # THR_REGULAR: measured on an opponent turn at 1:29 of the
                    # test clip, d_lo read 0,1,0,0,0,0,0 across three seconds
                    # while the score alternated 0.50/0.62 sample by sample.
                    # That dashed the cut mask into 0.5 s islands, segments.py
                    # bridged them into one 4.5 s block, padding grew it to
                    # 6.7 s, and an opponent turn was kept as seg0001.
                    #
                    # Applied by filling HOLES, never by latching a state. A
                    # hole is only closed when the clock ticks on both sides of
                    # it, so the first and last sample of every run stay put. A
                    # sticky "still running" flag would instead creep past the
                    # end of an opponent turn into the next both-frozen stretch
                    # -- which may be Tieulinh's own combat, the one thing that
                    # must never be cut. See documents/cutting-rule.md.
P_DIGIT = 150       # BOTH clock lines need this many digit pixels to count as
                    # present. Testing only one line false-positives on the
                    # lobby, whose blue UI fills the upper band.
NAME_MATCH = 0.6    # template score that identifies Tieulinh in a name slot
# The name plate is drawn at the stream's own HUD scale, which is not the
# frame's. Measured: a February 2025 VOD draws it 25% larger than the 2026 VOD
# the template was cut from, and matching at one scale tops out at 0.45 there
# -- under NAME_MATCH, so no sample ever named a seat and every one of them
# fell back to the default. At scale 1.25 the same frames match at 0.89.
# Searching these scales costs one small correlation each, once every five
# seconds of video, and finds the plate wherever the stream sizes it.
NAME_SCALES = (0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15,
               1.20, 1.25, 1.30, 1.35, 1.40, 1.45, 1.50)

# ------------------------------------------------------- segment shaping ----
MIN_CUT = 6.0       # do not bother cutting a dead stretch shorter than this
MIN_KEEP = 3.0      # discard kept fragments shorter than this
PAD_PRE = 0.7       # lead-in before a kept stretch
PAD_POST = 1.5      # let the result of the last move land on screen
MIN_GAP = 10.0      # minimum gap AFTER padding. MIN_CUT is applied before the
                    # padding, which then shrinks every gap by PAD_PRE +
                    # PAD_POST, so without this the real floor is 3.8 s and the
                    # cut list fills up with 5-second cuts that cost a 1 s
                    # transition to save 4 s. It also stabilises the segment
                    # count: borderline gaps no longer flip in and out on
                    # sub-second sampling differences.

# ---------------------------------------------------------------- render ----
FADE = 0.3          # fade out / fade in duration, video and audio
BLACK = 0.4         # black hold between segments
GQ = 28             # h264_qsv global_quality. 28 lands near the source bitrate
                    # (~2.4 Mb/s for a 2.07 Mb/s source); lower is bigger.
# ------------------------------------------------------------- estimates ----
# Measured on this machine (i5-13420H, Intel UHD) against a 2h48 VOD: the
# signal pass ran at 17.5x realtime on four workers, screen checks cost 0.032
# of the video length, and rendering ran at 4.8x realtime of the OUTPUT. Used
# only to tell the user roughly how long to expect; being wrong costs nothing
# but a misleading number, which is why the figures are shown as "about".
RATE_SIGNAL = 17.5
RATE_SCREENS = 0.032
RATE_RENDER = 4.8
KEEP_GUESS = 0.60      # fraction of a VOD that usually survives the cut

VIDEO_EXTS = (".mp4", ".mkv", ".ts", ".flv", ".mov", ".webm", ".avi")
