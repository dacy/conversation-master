# ClipLingo — learn a language by scrolling real clips

Prototype for a language-learning experience built on short segments of real
online media: you scroll a TikTok-style vertical feed, each card plays a
10–35 second audio clip, you answer a quick comprehension question, then
scroll to the next one.

The prototype answers the core feasibility question: **can we automatically
fetch material from YouTube, TikTok, and NPR and turn it into quiz-able
short segments?** Short answer: yes — details per source below.

## Quick start

Needs `ffmpeg` on PATH (`apt install ffmpeg` / `brew install ffmpeg`), plus
`espeak-ng` if you want the offline demo mode.

With [uv](https://docs.astral.sh/uv/) (recommended — manages the virtualenv for you):

```bash
uv sync                # creates .venv and installs everything

# 1. Build a feed. Offline demo (synthesized speech, no network needed):
uv run cliplingo demo

# ...or fetch real material:
uv run cliplingo youtube "easy english conversation practice" --max 3
uv run cliplingo youtube https://www.youtube.com/watch?v=VIDEO_ID
uv run cliplingo tiktok https://www.tiktok.com/@somecreator/video/123456789
uv run cliplingo npr news-now --max 1   # keys: news-now, up-first, fresh-air, or any RSS URL

# 2. Serve the player:
uv run cliplingo serve
# open http://localhost:8000, tap "Start listening", scroll
```

With plain pip instead: `pip install -e .`, then the same commands via
`cliplingo ...` or `python -m pipeline ...`.

Fetch commands **append** to the same feed (`web/data/manifest.json`), so you
can mix sources. The demo mode needs `espeak-ng` installed.

## Daily curated build

```bash
uv run cliplingo daily [--per-topic N] [--max-duration S] [--cookies-from-browser chrome]
```

Fetches fresh clips for every topic in the fixed menu (`pipeline/topics.py`),
tags each clip with its topic and an offline difficulty band
(beginner/intermediate/advanced — see `pipeline/difficulty.py`), and
**replaces** `web/data/manifest.json` — unlike the fetch commands above,
which append. On first launch the player shows an onboarding step (pick
topics and level, saved to `localStorage`) and filters the feed on-device,
the same contract an iOS client would use. The gear icon (top right)
reopens onboarding. Scheduling (cron/CI) is intentionally not wired up yet.

As with the other commands, the same works via `python -m pipeline daily ...`
without `uv run`.

## How it works

```
source fetcher ──► full audio + transcript cues ──► segmenter ──► clips + questions ──► manifest.json ──► web feed
 (yt-dlp / RSS)        (VTT subtitles)              (ffmpeg)        (cloze MCQ)                        (scroll player)
```

- **Fetching** (`pipeline/sources/`): YouTube via yt-dlp search or URLs,
  downloading audio plus manual/auto subtitles. TikTok via yt-dlp with video
  or profile URLs (yt-dlp has no TikTok search). NPR via its public podcast
  RSS feeds, which expose direct mp3 enclosures — no API key needed.
- **Segmentation** (`pipeline/segment.py`): when a transcript exists, subtitle
  cues are grouped into 10–35s chunks that end on sentence boundaries. Without
  a transcript, ffmpeg `silencedetect` finds pauses to cut at.
- **Questions** (`pipeline/questions.py`): offline cloze (fill-in-the-blank)
  multiple choice generated from the segment's own transcript, with
  distractors drawn from sibling segments. This is deliberately simple; an
  LLM call could slot in here for real comprehension questions.
- **Player** (`web/`): dependency-free HTML/JS. Vertical scroll-snap feed; an
  IntersectionObserver auto-plays the visible card's clip and pauses the rest.
  Cards without a transcript become "listen and repeat" cards instead of quizzes.

## Feasibility findings (2026-07)

| Source | Fetch | Transcript | Quiz | Notes |
|---|---|---|---|---|
| YouTube | ✅ yt-dlp (search or URL) | ✅ auto/manual captions | ✅ | Best source: captions make transcript-aligned clips + questions automatic. Datacenter IPs sometimes hit bot checks; `--cookies-from-browser` fixes it. |
| NPR | ✅ public podcast RSS, direct mp3 | ❌ not in feed | ⚠️ | Trivial to fetch, very reliable. Needs a speech-to-text pass (e.g. whisper) to unlock quizzes; otherwise listen-and-shadow cards. |
| TikTok | ⚠️ yt-dlp, URL only | ❌ rarely | ⚠️ | Works for known video/profile URLs; no search API, and scraping discovery is brittle and ToS-fraught. Treat as "curated URLs" source. |

Caveats worth knowing before this becomes a product:

- **This sandbox couldn't test live fetching** — its network policy blocks
  youtube.com/tiktok.com/npr.org (only package registries are allowed), which
  is why the offline demo mode exists. The fetchers use standard, widely-used
  mechanisms (yt-dlp, RSS) and should work on a normal connection; run the
  commands above on your machine to confirm.
- **Rights**: downloading and re-serving clips is fine for a personal
  prototype, but a public product needs licensed content, embeds, or
  user-supplied URLs. NPR's RSS terms allow personal, noncommercial use.
- **Question quality**: cloze-from-transcript is a placeholder. The obvious
  next step is an LLM generating real comprehension questions per segment.

## Repo layout

```
pipeline/            Python package (no framework, stdlib + yt-dlp)
  sources/           youtube.py, tiktok.py, npr.py
  transcript.py      VTT parsing (handles yt-dlp auto-sub duplication)
  segment.py         cue grouping + silence detection + ffmpeg cutting
  questions.py       cloze question generation
  manifest.py        clip cutting + manifest.json assembly
  demo.py            offline espeak-ng demo source
web/                 static player (index.html, app.js, style.css)
web/data/            generated clips + manifest (gitignored)
```
