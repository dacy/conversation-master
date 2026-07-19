# Design — Onboarding + curated daily feed

**Date:** 2026-07-19
**Status:** Approved (product half); technical half pending spec review
**Prototype:** ClipLingo (language-learning scroll feed)

## Goal

Add an onboarding step where a user picks (a) topics of interest from a **fixed
menu** and (b) a single **difficulty level**. A **daily batch job** fetches fresh
content for the whole topic menu; each app then filters that content locally to
show a curated daily feed matching the user's picks.

Ultimate target is an **iOS app**. The web prototype must model the flow so it
ports cleanly. Chosen architecture (**Approach A — "fat client"**): one daily
manifest is the entire contract between build and app; every app downloads it and
filters on-device. **No server-side per-user work.**

## Non-goals (YAGNI)

- Adaptive difficulty / per-user performance tracking
- User accounts or any server/backend logic
- Scheduling infrastructure (we ship the `daily` command; cron/CI wiring is later)
- In-app free-text topic entry (deliberately replaced by the fixed menu)
- Speech-to-text for transcript-less sources (NPR stays "unrated" for now)

## Architecture & data flow

```
DAILY BUILD   (cliplingo daily — run manually / scheduled later)
  for each topic in TOPICS (fixed menu):
      fetch fresh clips via existing youtube/npr fetchers
        (same safeguards: skip live streams, max-duration, prefer captioned)
      segment -> generate questions -> score difficulty
      tag each clip with { topic, difficulty }
  REPLACE web/data/manifest.json with today's clips + meta (build date, topic menu)

APP   (web now; iOS later — identical logic)
  on launch:
    fetch manifest.json
    if no saved prefs -> show onboarding (topic menu built FROM manifest.topics)
        user picks topics (multi) + one level -> save to localStorage
    build feed = clips where topic in prefs.topics AND difficulty == prefs.level
        (adjacent-level fallback for a topic that is thin today)
        -> shuffle -> cap ~20
  gear/"Edit" affordance reopens onboarding
```

The manifest is the only interface between build and app. This is exactly what
iOS will do: download JSON + mp3s, filter on-device, keep prefs on-device.

## Fixed topic menu

Source of truth: `pipeline/topics.py`. Each topic maps to search queries the daily
job runs. Queries are tunable config, not code.

| key | label | example queries / source |
|---|---|---|
| everyday | Everyday Conversation | yt: "easy english conversation", "daily english dialogue" |
| news | News & Current Events | NPR news-now; yt: "english news for learners" |
| science | Science & Technology | yt: "science explained simply", "how things work" |
| business | Business & Work | yt: "business english conversation" |
| travel | Travel | yt: "travel english", "airport hotel conversation" |
| food | Food & Cooking | yt: "cooking recipe english easy" |
| health | Health & Fitness | yt: "health tips english", "fitness explained" |
| culture | Culture & Entertainment | yt: "movie review english", "pop culture explained" |

## Difficulty heuristic (offline, 3 bands)

Computed per clip from its transcript + timing; **no LLM**. Pure function in
`pipeline/difficulty.py`, deterministic and unit-testable.

Signals:
- **Speech rate (primary):** `words / clip_seconds` → words-per-minute. Slower = easier.
- **Lexical load (secondary):** mean word length + share of long words (7+ chars).

Combine into a single 0–1 score, then bucket:
- **beginner** (~A1–A2): slow, simple words
- **intermediate** (~B1–B2)
- **advanced** (~C1–C2): fast and/or dense vocabulary

Threshold constants live at the top of the module for tuning against real fetched
clips + the demo set. Starting anchors (to be tuned): native conversational speech
≈ 150 wpm; learner content is typically slower. Clips with no transcript (or too
few words to score) return `None` → `difficulty: null` in the manifest.

`null`/unrated clips do **not** appear in a leveled feed. (NPR needs a
speech-to-text pass before it can participate — consistent with the handoff.)

## Manifest schema (v2, additive/backward-compatible)

```json
{
  "generated": "2026-07-19",
  "topics": [
    { "key": "everyday", "label": "Everyday Conversation" },
    { "key": "science",  "label": "Science & Technology" }
  ],
  "clips": [
    {
      "id": "youtube-...-00",
      "source": "youtube",
      "title": "...", "uploader": "...", "url": "...",
      "language": "en",
      "audio": "data/clips/...mp3",
      "duration": 15.6,
      "transcript": "...",
      "question": { "type": "cloze", "prompt": "...", "options": ["..."], "answer_index": 2 },
      "topic": "science",
      "difficulty": "intermediate"
    }
  ]
}
```

Old players tolerate the new fields; a player seeing no `topics`/`topic`/`difficulty`
falls back to showing all clips (current behavior).

## Component changes

### Pipeline
- **`pipeline/topics.py`** (new): `TOPICS` list of `{key, label, queries}` where each
  query carries its source (youtube/npr) + args. `menu()` returns `[{key,label}]`
  for the manifest meta.
- **`pipeline/difficulty.py`** (new): `score(transcript, duration) -> "beginner" |
  "intermediate" | "advanced" | None`. Tunable threshold constants at top.
- **`pipeline/manifest.py`**: `build_clips(item, topic=None, ...)` sets
  `clip["topic"]` and `clip["difficulty"] = difficulty.score(text, dur)`. Add
  `write_daily_manifest(clips, topics_menu, generated)` that **replaces** the
  manifest and writes meta. Keep `append_manifest` for ad-hoc per-source commands.
- **`pipeline/__main__.py`**: new `daily` subcommand
  (`daily [--per-topic N] [--max-duration S] [--cookies-from-browser B]`) that
  iterates `TOPICS`, fetches fresh, tags, and writes a fresh manifest; prints a
  per-topic summary + difficulty distribution. Existing `youtube`/`tiktok`/`npr`/
  `demo`/`serve` unchanged except `demo` also tags clips (topic `everyday` +
  computed difficulty) so onboarding is demoable offline.

### Player (`web/`)
- **`index.html`**: onboarding overlay markup (or a mount point built in JS).
- **`app.js`**: on load, fetch manifest; if `localStorage["cliplingo.prefs"]`
  missing, render onboarding from `manifest.topics` (topic chips multi-select +
  three difficulty cards single-select + Start button disabled until ≥1 topic and a
  level). Save `{topics:[key...], level}`. Build feed via a `filterClips(clips, prefs)`
  function: match any selected topic AND `difficulty == level`, with adjacent-level
  backfill per topic when thin; shuffle; cap ~20. Gear/Edit control clears/edits
  prefs and reopens onboarding. Empty-state message when nothing matches. Existing
  card rendering + IntersectionObserver playback untouched.
- **`style.css`**: styles for chips, difficulty cards, gear button, empty state.

## Feed composition rules

Single explicit algorithm (cap `N = 20`):

1. Candidates = clips whose `topic` is in `prefs.topics` and whose `difficulty`
   is not `null`.
2. Primary pool = candidates with `difficulty == prefs.level`.
3. If the primary pool has fewer than `N` clips, top it up with candidates from the
   adjacent level(s) — nearest first (from `intermediate`, order is beginner then
   advanced; from an end level, the single neighbor) — until reaching `N` or
   exhausting candidates.
4. Shuffle the resulting list; keep the first `N`.
5. If the list is empty (e.g. stale/empty build or picks with no matching content),
   show the empty-state message instead of a feed.

Note: fallback is applied to the pool as a whole (not per-topic), which keeps the
rule unambiguous; a topic with no clips at the chosen level still contributes via
its adjacent-level clips during top-up.

## Error / edge handling

- Missing/failed manifest fetch → existing "no feed" message (already handled).
- Manifest with no `topics` meta → onboarding falls back to any clip topics present,
  or (if none) shows all clips without onboarding.
- A daily topic that returns nothing (network/bot-check) → that topic simply has no
  clips today; the build logs it and continues (no hard failure).
- Prefs referencing a topic no longer in today's menu → ignored during filtering.

## Testing

First automated tests in the repo (handoff noted none). Use **stdlib `unittest`**
(zero new dependencies):
- `tests/test_difficulty.py`: crafted transcripts → expected bands (slow+simple →
  beginner; fast+dense → advanced; empty/short → None); monotonicity sanity.
- `tests/test_topics.py`: menu integrity (unique keys, non-empty label + queries).
- Offline E2E: `cliplingo demo` yields a tagged manifest (topic + difficulty); the
  onboarding → filtered-feed path works in the browser with no network.
- Manual browser verification: onboarding renders from manifest, selecting
  topics+level yields a correctly filtered feed, gear reopens onboarding.
- Regression: `python -m compileall pipeline` stays clean.

## iOS mapping (why this ports cleanly)

- Host `manifest.json` + `clips/` as static files (object storage / CDN).
- The app bundles the same filter logic; on launch/refresh it downloads today's
  manifest and filters by prefs stored in `UserDefaults`.
- Prefs never leave the device; there is no backend. Matches "each app manages its
  own download."

## Open items to confirm at spec review

- The 8 topics + their starter queries (approved in principle; queries tunable).
- Daily feed cap (~20) and adjacent-level fallback behavior.
- Difficulty threshold anchors (will be tuned empirically during implementation).
