"""Cut full audio into short scroll-friendly segments.

Two strategies:
- transcript-aligned: group subtitle cues into 10-35s chunks breaking at
  sentence boundaries, so clips start/end on natural speech.
- silence-based fallback (no transcript): use ffmpeg silencedetect to find
  pauses and cut between them.
"""
import re
import subprocess

MIN_S = 8.0
TARGET_S = 20.0
MAX_S = 35.0

_SENTENCE_END = re.compile(r"[.!?…][\"')\]]?$")


def group_cues(cues, min_s=MIN_S, target_s=TARGET_S, max_s=MAX_S):
    """Group cues into segments: list of (start, end, text)."""
    segments = []
    bucket = []

    def flush():
        if not bucket:
            return
        start = bucket[0].start
        end = bucket[-1].end
        if end - start >= min_s / 2:  # drop tiny trailing scraps
            segments.append((start, end, " ".join(c.text for c in bucket)))
        bucket.clear()

    for cue in cues:
        bucket.append(cue)
        dur = bucket[-1].end - bucket[0].start
        at_sentence = bool(_SENTENCE_END.search(cue.text.strip()))
        if dur >= max_s or (dur >= target_s and at_sentence) or (dur >= min_s and at_sentence and dur >= target_s * 0.6):
            flush()
    flush()
    return segments


def detect_silences(audio_path, noise_db="-30dB", min_silence=0.6):
    """Return list of (silence_start, silence_end) using ffmpeg silencedetect."""
    proc = subprocess.run(
        ["ffmpeg", "-i", audio_path, "-af",
         f"silencedetect=noise={noise_db}:d={min_silence}",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    out = proc.stderr
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", out)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", out)]
    return list(zip(starts, ends))


def probe_duration(audio_path):
    proc = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", audio_path],
        capture_output=True, text=True, check=True,
    )
    return float(proc.stdout.strip())


def silence_segments(audio_path, min_s=MIN_S, target_s=TARGET_S, max_s=MAX_S):
    """Segment audio at pauses. Returns list of (start, end, "") — no text."""
    total = probe_duration(audio_path)
    # candidate cut points = middles of silences
    cuts = [(s + e) / 2 for s, e in detect_silences(audio_path)]
    segments = []
    seg_start = 0.0
    for cut in cuts:
        dur = cut - seg_start
        if dur >= max_s:
            # no pause found in time; hard cut at max_s boundaries
            while cut - seg_start >= max_s:
                segments.append((seg_start, seg_start + max_s, ""))
                seg_start += max_s
        elif dur >= min_s:
            segments.append((seg_start, cut, ""))
            seg_start = cut
    if total - seg_start >= min_s:
        segments.append((seg_start, min(total, seg_start + max_s), ""))
    return segments


def cut_clip(audio_path, start, end, out_path):
    """Extract [start, end] into an mp3 clip."""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
         "-i", audio_path,
         "-vn", "-acodec", "libmp3lame", "-b:a", "96k", "-ac", "1",
         out_path],
        check=True,
    )
