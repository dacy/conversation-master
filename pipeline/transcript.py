"""WebVTT parsing tolerant of yt-dlp auto-generated captions."""
import html
import re

from .models import Cue

_TS = re.compile(r"(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})")
_CUE_LINE = re.compile(
    r"(?P<start>[\d:.,]+)\s+-->\s+(?P<end>[\d:.,]+)"
)
_TAG = re.compile(r"<[^>]+>")


def _parse_ts(ts: str) -> float:
    m = _TS.search(ts)
    if not m:
        raise ValueError(f"bad timestamp: {ts}")
    h, mm, ss, ms = m.groups()
    return int(h or 0) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0


def parse_vtt(path: str) -> list:
    """Parse a .vtt file into deduplicated cues.

    yt-dlp auto-subs repeat lines across rolling cues; consecutive duplicate
    text is collapsed so each spoken line appears once.
    """
    cues = []
    with open(path, encoding="utf-8") as f:
        block_start = block_end = None
        for raw in f:
            line = raw.strip()
            m = _CUE_LINE.match(line)
            if m:
                block_start = _parse_ts(m.group("start"))
                block_end = _parse_ts(m.group("end"))
                continue
            if block_start is None or not line or line == "WEBVTT" or line.startswith(("NOTE", "Kind:", "Language:", "STYLE")):
                continue
            # Strip timing/style tags first, then decode WebVTT entities
            # (&gt;&gt; speaker markers, &amp;, &nbsp;, etc.) to real characters.
            text = html.unescape(_TAG.sub("", line)).strip()
            if not text:
                continue
            if cues and cues[-1].text == text:
                cues[-1].end = max(cues[-1].end, block_end)
                continue
            cues.append(Cue(block_start, block_end, text))
    return cues
