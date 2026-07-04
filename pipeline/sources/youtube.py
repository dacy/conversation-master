"""Fetch YouTube audio + subtitles with yt-dlp.

Accepts a search query ("ytsearchN:..." is built for you) or direct URLs.
Prefers videos that have subtitles (manual or auto) so segmentation can be
transcript-aligned and questions can be generated.
"""
import glob
import os
import shutil
import sys

import yt_dlp

from ..models import SourceItem
from ..transcript import parse_vtt


def fetch(query_or_urls, workdir, max_items=3, language="en", max_duration=900,
          cookies_from_browser=None, verbose=False, source="youtube"):
    """Download audio+subs. Returns list[SourceItem]."""
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH — install it first "
                 "(brew install ffmpeg / sudo apt install ffmpeg) and retry.")
    os.makedirs(workdir, exist_ok=True)
    if isinstance(query_or_urls, str) and not query_or_urls.startswith("http"):
        # overfetch: search results are often long videos that get skipped below
        targets = [f"ytsearch{max_items * 5}:{query_or_urls}"]
    elif isinstance(query_or_urls, str):
        targets = [query_or_urls]
    else:
        targets = list(query_or_urls)

    skipped = []

    def too_long(info, *, incomplete):
        dur = info.get("duration")
        if dur and dur > max_duration:
            msg = (f"skipped {info.get('title') or info.get('id')!r}: "
                   f"{int(dur)}s > {max_duration}s limit")
            skipped.append(msg)
            print(f"  {msg}", file=sys.stderr)
            return msg
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
        "quiet": not verbose,
        "no_warnings": not verbose,
    }
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)

    items = []
    with yt_dlp.YoutubeDL(opts) as ydl:
        for target in targets:
            try:
                info = ydl.extract_info(target, download=True)
            except yt_dlp.utils.DownloadError as e:
                print(f"  error on {target!r}: {e}", file=sys.stderr)
                continue
            if info is None:
                continue
            entries = info.get("entries", [info])
            for entry in entries:
                if entry is None:
                    continue
                item = _to_item(entry, workdir, language, source=source)
                if item:
                    items.append(item)
                    print(f"  fetched {item.title!r}"
                          f" ({'with' if item.cues else 'no'} transcript)",
                          file=sys.stderr)
                if len(items) >= max_items:
                    return items

    if not items:
        if skipped:
            print(f"\nAll {len(skipped)} result(s) were longer than "
                  f"{max_duration}s. Retry with --max-duration {max_duration * 4} "
                  "or a query that finds shorter videos "
                  '(e.g. add "shorts" or "1 minute").', file=sys.stderr)
        else:
            print("\nNothing was downloaded. Common causes:\n"
                  "  - YouTube bot-check on this network: retry with "
                  "--cookies-from-browser chrome (or firefox, safari, edge)\n"
                  "  - outdated yt-dlp: upgrade with `uv sync --upgrade-package yt-dlp`\n"
                  "Add --verbose to see yt-dlp's full output.", file=sys.stderr)
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
