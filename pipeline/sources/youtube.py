"""Fetch YouTube audio + subtitles with yt-dlp.

Accepts a search query ("ytsearchN:..." is built for you) or direct URLs.
Prefers videos that have subtitles (manual or auto) so segmentation can be
transcript-aligned and questions can be generated.
"""
import glob
import os

import yt_dlp

from ..models import SourceItem
from ..transcript import parse_vtt


def fetch(query_or_urls, workdir, max_items=3, language="en", max_duration=900):
    """Download audio+subs. Returns list[SourceItem]."""
    os.makedirs(workdir, exist_ok=True)
    if isinstance(query_or_urls, str) and not query_or_urls.startswith("http"):
        targets = [f"ytsearch{max_items * 2}:{query_or_urls}"]  # overfetch; filter below
    elif isinstance(query_or_urls, str):
        targets = [query_or_urls]
    else:
        targets = list(query_or_urls)

    def too_long(info, *, incomplete):
        dur = info.get("duration")
        if dur and dur > max_duration:
            return f"skipping: {dur}s > {max_duration}s"
        return None

    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(workdir, "%(id)s.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [language, f"{language}.*"],
        "subtitlesformat": "vtt",
        "match_filter": too_long,
        "ignoreerrors": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    items = []
    with yt_dlp.YoutubeDL(opts) as ydl:
        for target in targets:
            info = ydl.extract_info(target, download=True)
            if info is None:
                continue
            entries = info.get("entries", [info])
            for entry in entries:
                if entry is None:
                    continue
                item = _to_item(entry, workdir, language, source="youtube")
                if item:
                    items.append(item)
                if len(items) >= max_items:
                    return items
    return items


def _to_item(entry, workdir, language, source):
    vid = entry["id"]
    audio = os.path.join(workdir, f"{vid}.mp3")
    if not os.path.exists(audio):
        return None
    cues = []
    for vtt in sorted(glob.glob(os.path.join(workdir, f"{vid}.{language}*.vtt"))):
        cues = parse_vtt(vtt)
        if cues:
            break
    return SourceItem(
        source=source,
        title=entry.get("title", vid),
        url=entry.get("webpage_url", ""),
        audio_path=audio,
        language=language,
        cues=cues,
        uploader=entry.get("uploader", "") or entry.get("channel", ""),
    )
