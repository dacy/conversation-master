"""Offline difficulty scoring: 3 bands from speech rate + lexical load.

Pure function of (transcript, duration) — deterministic, no LLM, no I/O.
Speech rate (words per minute) is the primary signal; lexical load (mean
word length + share of 7+ character words) is secondary. The combined 0-1
score is bucketed into beginner / intermediate / advanced.
"""
import re

# ---- tunable thresholds (anchor: native conversational speech ~150 wpm) ----
MIN_WORDS = 5            # refuse to score below this many words
SLOW_WPM = 90.0          # at or below -> rate score 0
FAST_WPM = 190.0         # at or above -> rate score 1
SHORT_MEAN_LEN = 3.5     # mean word length at or below -> length score 0
LONG_MEAN_LEN = 6.0      # mean word length at or above -> length score 1
LONG_WORD_CHARS = 7      # a word this long counts as "long"
LONG_SHARE_FULL = 0.35   # this share of long words -> share score 1
RATE_WEIGHT = 0.7        # speech rate is the primary signal
LEX_WEIGHT = 0.3
BEGINNER_MAX = 0.35      # combined score below this -> beginner
INTERMEDIATE_MAX = 0.65  # below this -> intermediate; else advanced

_WORD = re.compile(r"[A-Za-zÀ-ÿ']+")


def _clamp01(x):
    return max(0.0, min(1.0, x))


def score(transcript, duration):
    """Band for one clip, or None when there is too little signal to score."""
    if not transcript or not duration or duration <= 0:
        return None
    words = _WORD.findall(transcript)
    if len(words) < MIN_WORDS:
        return None

    wpm = len(words) / duration * 60.0
    rate = _clamp01((wpm - SLOW_WPM) / (FAST_WPM - SLOW_WPM))

    mean_len = sum(len(w) for w in words) / len(words)
    length = _clamp01((mean_len - SHORT_MEAN_LEN) / (LONG_MEAN_LEN - SHORT_MEAN_LEN))
    long_share = sum(1 for w in words if len(w) >= LONG_WORD_CHARS) / len(words)
    share = _clamp01(long_share / LONG_SHARE_FULL)
    lex = 0.6 * length + 0.4 * share

    combined = RATE_WEIGHT * rate + LEX_WEIGHT * lex
    if combined < BEGINNER_MAX:
        return "beginner"
    if combined < INTERMEDIATE_MAX:
        return "intermediate"
    return "advanced"
