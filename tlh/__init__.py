"""Trim Tieulinh HOTA stream VODs down to the parts that are actually played.

See README.md for why the cut rule is "keep unless provably dead" rather than
the more obvious "cut whenever Tieulinh's clock is frozen".
"""
from . import (config, daycount, encoder, ffmpeg, render, screens,
               segments, signal, timeline)
from .process import process_video

__all__ = ["config", "daycount", "encoder", "ffmpeg", "render", "screens",
           "segments", "signal", "timeline", "process_video"]
