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


def _ingest(items):
    if not items:
        print("No items fetched — nothing to do.", file=sys.stderr)
        sys.exit(1)
    all_clips = []
    for item in items:
        clips = manifest.build_clips(item)
        mode = "transcript-aligned" if item.cues else "silence-based, no quiz"
        print(f"  {item.title!r}: {len(clips)} clips ({mode})")
        all_clips.extend(clips)
    path, total = manifest.append_manifest(all_clips)
    print(f"Manifest now has {total} clips: {path}")
    print("Run `python -m pipeline serve` and open http://localhost:8000")


def main():
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

    npr = sub.add_parser("npr", help="fetch from an NPR/podcast RSS feed")
    npr.add_argument("feed", help="feed key (news-now, up-first, fresh-air) or RSS URL")
    npr.add_argument("--max", type=int, default=1)

    sub.add_parser("demo", help="build offline demo feed with synthesized speech")
    sub.add_parser("serve", help="serve the web player on :8000")

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
        _ingest(demo.synthesize(workdir))
    elif args.cmd == "serve":
        import functools
        import http.server
        web = manifest.web_dir()
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=web)
        print("Serving on http://localhost:8000")
        http.server.ThreadingHTTPServer(("", 8000), handler).serve_forever()


if __name__ == "__main__":
    main()
