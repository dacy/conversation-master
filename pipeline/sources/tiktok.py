"""Fetch TikTok videos with yt-dlp.

TikTok has no search support in yt-dlp, so you pass video or profile URLs
(e.g. https://www.tiktok.com/@npr/video/123..., or a profile URL to pull the
latest posts). TikTok rarely has subtitles, so clips usually fall back to
silence-based segmentation with no quiz (listen-and-shadow mode).
"""
from . import youtube


def fetch(urls, workdir, max_items=5, language="en", **kwargs):
    return youtube.fetch(list(urls), workdir, max_items=max_items,
                         language=language, source="tiktok", **kwargs)
