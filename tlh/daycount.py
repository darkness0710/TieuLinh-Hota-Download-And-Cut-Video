"""Read the "Month: M, Week: W, Day: D" counter at the bottom right.

Isolating the glyphs is the fiddly part, and two measured facts drive it:

* In combat, and throughout a game played without a timer, the whole bottom
  panel is dimmed -- the text peak drops from 250 to 228 and its 90th
  percentile from 167 to 97. A fixed brightness threshold loses half the
  strokes, so the strip is binarised with Otsu instead.
* In that same dimmed variant the leading "M" of "Month:" is clipped, so the
  word "Week:" is the anchor: it survives both variants and its match score
  doubles as an "are we in a game at all" test (0.79-0.97 in game, 0.29 in the
  lobby or a menu).

Reading a single frame is not relied on. Values are voted on across a run of
samples and constrained to advance the way Heroes 3 does -- Day 1..7, then the
week rolls over -- so an occasional misread cannot move the timeline.
"""
import cv2
import numpy as np

from . import config as C

ORDER = "0123456789"


def binarise(strip_gray):
    _, b = cv2.threshold(strip_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return b


def glyph_blobs(binary_strip):
    """Digit blobs per field, left to right, as {field: [image, ...]}."""
    y0, y1 = C.DIGIT_Y
    lo, hi = C.GLYPH_H
    out = {}
    for field, (x0, x1) in C.DIGIT_X.items():
        win = binary_strip[y0:y1, x0:x1]
        cols = (win > 0).sum(axis=0)
        spans, run = [], None
        for i, c in enumerate(cols):
            if c and run is None:
                run = i
            elif not c and run is not None:
                spans.append((run, i))
                run = None
        if run is not None:
            spans.append((run, len(cols)))

        keep = []
        for a, b in spans:
            if b - a < C.GLYPH_W_MIN:
                continue
            blob = win[:, a:b]
            rows = np.where((blob > 0).sum(axis=1) > 0)[0]
            if not len(rows):
                continue
            height = rows.max() - rows.min() + 1
            if lo <= height <= hi:
                keep.append((a, b, blob[rows.min():rows.max() + 1]))

        # The number is the rightmost run of blobs that sit close together.
        # Anything further left, across a word-sized gap, is the label -- and
        # the colon of "Day:" is not filtered out by height, because the box
        # from its top dot to its bottom dot is as tall as a digit. read_field
        # would then try to match it, fail, and refuse the whole field: which
        # is why one VOD whose panel sits ten pixels right of the measured
        # windows read its day counter in 0.4% of samples instead of 91%.
        first = len(keep) - 1
        while first > 0 and keep[first][0] - keep[first - 1][1] <= C.GLYPH_GAP:
            first -= 1
        out[field] = [blob for _x0, _x1, blob in keep[max(first, 0):]]
    return out


def load_atlas(path=None):
    """Digit templates as {character: [image, ...]}.

    A digit gets more than one template because the same glyph renders bright
    on the adventure map and dimmed in combat, and the two binarise to slightly
    different strokes.
    """
    path = path or (C.TEMPLATES / "digits.npz")
    if not path.exists():
        return None
    blob = np.load(path, allow_pickle=False)
    atlas = {}
    for key in blob.files:
        ch = key.split("_")[0]
        if ch in ORDER:
            atlas.setdefault(ch, []).append(blob[key])
    return atlas or None


def _norm(img, size=(14, 20)):
    return cv2.resize(img, size, interpolation=cv2.INTER_NEAREST)


def read_field(blobs, atlas):
    """Digits of one field as an int, or None if nothing matched."""
    if not blobs or not atlas:
        return None
    digits = ""
    for blob in blobs:
        norm = _norm(blob).astype(np.int16)
        best, score = None, 1e9
        for ch, variants in atlas.items():
            for tpl in variants:
                d = float(np.abs(norm - tpl.astype(np.int16)).mean())
                if d < score:
                    best, score = ch, d
        # An unmatched glyph means an unseen digit (this VOD only ever shows
        # 1-7) or a bad frame. Refusing to answer is right: the vote downstream
        # simply ignores the sample rather than being poisoned by a guess.
        if best is None or score > 55:
            return None
        digits += best
    return int(digits) if digits else None


def read_strip(strip_gray, atlas):
    """(month, week, day) from one counter strip; any field may be None."""
    blobs = glyph_blobs(binarise(strip_gray))
    return tuple(read_field(blobs.get(f), atlas) for f in ("month", "week", "day"))


def plausible(prev, cur):
    """Is `cur` a legal successor of `prev`? Heroes 3 runs 7 days to a week."""
    if prev is None or cur is None or None in prev or None in cur:
        return True                            # nothing to contradict
    if cur == prev:
        return True
    pm, pw, pd = prev
    cm, cw, cd = cur
    if cm == pm and cw == pw and cd == pd + 1:
        return True                            # next day
    if cm == pm and cw == pw + 1 and pd == 7 and cd == 1:
        return True                            # next week
    if cm == pm + 1 and pw == 4 and pd == 7 and cw == 1 and cd == 1:
        return True                            # next month
    return False
