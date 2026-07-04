"""Turn fetched SourceItems into web-ready clips + manifest.json.

The manifest is what the web player reads. Re-running a fetch command appends
to the existing manifest so you can mix sources in one feed.
"""
import json
import os
import re

from . import questions, segment

def web_dir():
    """The web/ folder: next to this package in a checkout / editable install,
    else ./web relative to where the command is run."""
    pkg_web = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web"))
    if os.path.exists(os.path.join(pkg_web, "index.html")):
        return pkg_web
    return os.path.abspath("web")


WEB_DATA = os.path.join(web_dir(), "data")


def _slug(text, max_len=40):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len] or "clip"


def build_clips(item, out_dir=None, max_clips_per_item=8):
    """Segment one SourceItem into clips; returns manifest clip dicts."""
    out_dir = out_dir or os.path.join(WEB_DATA, "clips")
    os.makedirs(out_dir, exist_ok=True)

    if item.cues:
        segments = segment.group_cues(item.cues)
    else:
        segments = segment.silence_segments(item.audio_path)
    segments = segments[:max_clips_per_item]

    all_words = [w for _, _, text in segments for w in questions.content_words(text)]

    clips = []
    base = _slug(item.title)
    for i, (start, end, text) in enumerate(segments):
        clip_name = f"{item.source}-{base}-{i:02d}.mp3"
        clip_path = os.path.join(out_dir, clip_name)
        segment.cut_clip(item.audio_path, start, end, clip_path)
        q = questions.make_cloze(text, all_words) if text else None
        clips.append({
            "id": f"{item.source}-{base}-{i:02d}",
            "source": item.source,
            "title": item.title,
            "uploader": item.uploader,
            "url": item.url,
            "language": item.language,
            "audio": f"data/clips/{clip_name}",
            "duration": round(end - start, 1),
            "transcript": text,
            "question": q,
        })
    return clips


def append_manifest(clips, data_dir=None):
    """Merge clips into web/data/manifest.json (deduped by id)."""
    data_dir = data_dir or WEB_DATA
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "manifest.json")
    existing = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            existing = json.load(f).get("clips", [])
    by_id = {c["id"]: c for c in existing}
    for c in clips:
        by_id[c["id"]] = c
    merged = list(by_id.values())
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"clips": merged}, f, ensure_ascii=False, indent=1)
    return path, len(merged)
