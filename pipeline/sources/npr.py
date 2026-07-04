"""Fetch NPR (or any podcast) audio from an RSS feed.

NPR publishes every show as a podcast RSS feed with direct mp3 enclosures —
no scraping or API key needed. Examples:
    NPR News Now (5-min newscast):  https://feeds.npr.org/500005/podcast.xml
    Up First:                        https://feeds.npr.org/510318/podcast.xml
Feeds have no transcripts, so segmentation is silence-based (no quiz), unless
you add a speech-to-text step.
"""
import os
import re
import urllib.request
import xml.etree.ElementTree as ET

from ..models import SourceItem

FEEDS = {
    "news-now": "https://feeds.npr.org/500005/podcast.xml",
    "up-first": "https://feeds.npr.org/510318/podcast.xml",
    "fresh-air": "https://feeds.npr.org/381444908/podcast.xml",
}

_UA = {"User-Agent": "Mozilla/5.0 (clip-pipeline prototype)"}


def fetch(feed, workdir, max_items=2, language="en"):
    """feed: a key from FEEDS or a full RSS URL. Returns list[SourceItem]."""
    os.makedirs(workdir, exist_ok=True)
    url = FEEDS.get(feed, feed)
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        root = ET.fromstring(resp.read())

    items = []
    for item_el in root.iter("item"):
        if len(items) >= max_items:
            break
        title = (item_el.findtext("title") or "npr episode").strip()
        link = (item_el.findtext("link") or url).strip()
        enclosure = item_el.find("enclosure")
        if enclosure is None:
            continue
        mp3_url = enclosure.get("url")
        if not mp3_url:
            continue
        fname = re.sub(r"[^a-z0-9]+", "-", title.lower())[:50] + ".mp3"
        audio_path = os.path.join(workdir, fname)
        if not os.path.exists(audio_path):
            req = urllib.request.Request(mp3_url, headers=_UA)
            with urllib.request.urlopen(req, timeout=120) as resp, open(audio_path, "wb") as f:
                f.write(resp.read())
        items.append(SourceItem(
            source="npr", title=title, url=link,
            audio_path=audio_path, language=language, uploader="NPR",
        ))
    return items
