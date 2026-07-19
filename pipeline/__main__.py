"""CLI for the clip pipeline.

Examples:
    python -m pipeline demo
    python -m pipeline youtube "easy english conversation" --max 3
    python -m pipeline youtube https://www.youtube.com/watch?v=VIDEO_ID
    python -m pipeline tiktok https://www.tiktok.com/@npr/video/123456
    python -m pipeline npr news-now --max 1
    python -m pipeline serve
"""
import argparse
import os
import sys
import tempfile

from . import manifest
from .sources import FFmpegNotFoundError


def _ingest(items, topic=None):
    if not items:
        print("No items fetched — nothing to do.", file=sys.stderr)
        sys.exit(1)
    all_clips = []
    for item in items:
        clips = manifest.build_clips(item, topic=topic)
        mode = "transcript-aligned" if item.cues else "silence-based, no quiz"
        print(f"  {item.title!r}: {len(clips)} clips ({mode})")
        all_clips.extend(clips)
    path, total = manifest.append_manifest(all_clips)
    print(f"Manifest now has {total} clips: {path}")
    print("Run `python -m pipeline serve` and open http://localhost:8000")


def main():
    try:
        _main()
    except FFmpegNotFoundError as e:
        sys.exit(str(e))


def _main():
    p = argparse.ArgumentParser(prog="pipeline", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    yt = sub.add_parser("youtube", help="fetch from YouTube (search query or URLs)")
    yt.add_argument("query", nargs="+", help="search query words, or one/more URLs")
    yt.add_argument("--max", type=int, default=3)
    yt.add_argument("--lang", default="en")
    yt.add_argument("--max-duration", type=int, default=900, metavar="SECONDS",
                    help="skip videos longer than this (default 900)")
    yt.add_argument("--cookies-from-browser", metavar="BROWSER",
                    help="use browser cookies to pass YouTube bot checks (chrome, firefox, safari, edge)")
    yt.add_argument("--verbose", "-v", action="store_true", help="show full yt-dlp output")

    tt = sub.add_parser("tiktok", help="fetch TikTok video/profile URLs")
    tt.add_argument("urls", nargs="+")
    tt.add_argument("--max", type=int, default=5)
    tt.add_argument("--lang", default="en")
    tt.add_argument("--cookies-from-browser", metavar="BROWSER")
    tt.add_argument("--verbose", "-v", action="store_true")

    npr_p = sub.add_parser("npr", help="fetch from an NPR/podcast RSS feed")
    npr_p.add_argument("feed", help="feed key (news-now, up-first, fresh-air) or RSS URL")
    npr_p.add_argument("--max", type=int, default=1)

    sub.add_parser("demo", help="build offline demo feed with synthesized speech")
    sub.add_parser("serve", help="serve the web player on :8000")

    daily = sub.add_parser("daily", help="build today's manifest across the fixed topic menu")
    daily.add_argument("--per-topic", type=int, default=3, metavar="N",
                       help="source items to fetch per topic (default 3)")
    daily.add_argument("--max-duration", type=int, default=900, metavar="SECONDS",
                       help="skip videos longer than this (default 900)")
    daily.add_argument("--cookies-from-browser", metavar="BROWSER",
                       help="use browser cookies to pass YouTube bot checks (chrome, firefox, safari, edge)")
    daily.add_argument("--verbose", "-v", action="store_true", help="show full yt-dlp output")

    args = p.parse_args()
    workdir = os.path.join(tempfile.gettempdir(), "clip-pipeline-cache")

    if args.cmd == "youtube":
        from .sources import youtube
        query = args.query if args.query[0].startswith("http") else " ".join(args.query)
        _ingest(youtube.fetch(query, workdir, max_items=args.max, language=args.lang,
                              max_duration=args.max_duration,
                              cookies_from_browser=args.cookies_from_browser,
                              verbose=args.verbose))
    elif args.cmd == "tiktok":
        from .sources import tiktok
        _ingest(tiktok.fetch(args.urls, workdir, max_items=args.max, language=args.lang,
                             cookies_from_browser=args.cookies_from_browser,
                             verbose=args.verbose))
    elif args.cmd == "npr":
        from .sources import npr
        _ingest(npr.fetch(args.feed, workdir, max_items=args.max))
    elif args.cmd == "demo":
        from . import demo
        _ingest(demo.synthesize(workdir), topic="everyday")
    elif args.cmd == "daily":
        import datetime
        from . import topics
        from .sources import npr, youtube
        all_clips, summary = [], []
        for t in topics.TOPICS:
            items = []
            for q in t["queries"]:
                remaining = args.per_topic - len(items)
                if remaining <= 0:
                    break
                try:
                    if q["source"] == "youtube":
                        items += youtube.fetch(
                            q["query"], workdir, max_items=remaining,
                            max_duration=args.max_duration,
                            cookies_from_browser=args.cookies_from_browser,
                            verbose=args.verbose)
                    elif q["source"] == "npr":
                        items += npr.fetch(q["feed"], workdir, max_items=remaining)
                except Exception as e:  # a dead topic must not kill the build
                    print(f"  [{t['key']}] fetch failed: {e}", file=sys.stderr)
            clips = []
            for item in items:
                clips.extend(manifest.build_clips(item, topic=t["key"]))
            unrated = sum(1 for c in clips if not c["difficulty"])
            summary.append((t["key"], len(items), len(clips), unrated))
            all_clips.extend(clips)
        if not all_clips:
            print("Daily build fetched nothing — keeping the existing manifest.",
                  file=sys.stderr)
            sys.exit(1)
        generated = datetime.date.today().isoformat()
        path, total = manifest.write_daily_manifest(all_clips, topics.menu(), generated)
        print(f"\nDaily build {generated} — {total} clips: {path}")
        for key, n_items, n_clips, n_unrated in summary:
            note = "" if n_clips else "  (nothing today)"
            if n_unrated:
                note += f"  ({n_unrated} unrated — hidden from leveled feeds)"
            print(f"  {key:10s} {n_items} items -> {n_clips} clips{note}")
        dist = {}
        for c in all_clips:
            band = c["difficulty"] or "unrated"
            dist[band] = dist.get(band, 0) + 1
        print("Difficulty: " + (", ".join(
            f"{band}: {dist[band]}" for band in
            ("beginner", "intermediate", "advanced", "unrated") if band in dist)
            or "no clips"))
    elif args.cmd == "serve":
        import functools
        import http.server
        web = manifest.web_dir()
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=web)
        print("Serving on http://localhost:8000")
        http.server.ThreadingHTTPServer(("", 8000), handler).serve_forever()


if __name__ == "__main__":
    main()
