# Onboarding + Curated Daily Feed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add topic/level onboarding to the web player and a `cliplingo daily` build command, connected only by a v2 `manifest.json` (topics meta + per-clip `topic`/`difficulty` tags) so the design ports directly to iOS.

**Architecture:** "Fat client" (Approach A from the spec): the daily build fetches clips for a fixed 8-topic menu, tags each clip with `topic` and an offline-computed `difficulty` band, and **replaces** `web/data/manifest.json`. The web app reads the manifest, shows onboarding (topic multi-select + one level) when no prefs are saved in `localStorage`, and filters the feed on-device. No backend, no per-user server work.

**Tech Stack:** Python 3.9+ stdlib (plus existing `yt-dlp` dep), stdlib `unittest` (first tests in the repo — zero new dependencies), vanilla JS/HTML/CSS in `web/`.

**Spec:** `docs/superpowers/specs/2026-07-19-onboarding-daily-feed-design.md`

## Global Constraints

- Branch: `claude/onboarding-daily-feed` (already checked out).
- **No new dependencies** — tests use stdlib `unittest`; difficulty scoring uses **no LLM**.
- Manifest schema is **v2, additive/backward-compatible**: old players that ignore `topics`/`topic`/`difficulty` keep working; a manifest without them makes the new player show all clips (current behavior).
- `localStorage` prefs key is exactly `"cliplingo.prefs"`, value `{"topics": ["key", ...], "level": "beginner"|"intermediate"|"advanced"}`.
- Difficulty bands are exactly the strings `"beginner"`, `"intermediate"`, `"advanced"`, or `null` (Python `None`) for unscorable clips. `null`-difficulty clips never appear in a leveled feed.
- Feed cap `N = 20`; adjacent-level fallback applied to the pool as a whole (not per-topic), nearest level first, lower level first on ties.
- Existing card rendering + IntersectionObserver playback in `web/app.js` stay untouched.
- Run Python via `uv run` (repo has `pyproject.toml`/`uv.lock`): tests are `uv run python -m unittest discover -s tests -v`, regression check is `uv run python -m compileall pipeline`.
- Non-goals (do NOT build): adaptive difficulty, accounts/backend, cron/CI scheduling, free-text topic entry, speech-to-text for NPR.

---

### Task 1: Commit pre-existing working-tree fixes

The branch has two uncommitted, unrelated fixes that predate this plan (live-stream skip in the YouTube fetcher; HTML-entity decoding in VTT parsing). Commit them as-is, separately, so feature commits stay clean.

**Files:**
- Modify: none (changes already in working tree: `pipeline/sources/youtube.py`, `pipeline/transcript.py`)

**Interfaces:**
- Consumes: nothing
- Produces: clean working tree for subsequent tasks

- [ ] **Step 1: Confirm the diff is only those two files**

Run: `git status --porcelain`
Expected output (exactly, plus possibly the plan/spec docs which are already committed):
```
 M pipeline/sources/youtube.py
 M pipeline/transcript.py
```
If anything else is modified, stop and report it instead of committing.

- [ ] **Step 2: Sanity-compile**

Run: `uv run python -m compileall -q pipeline`
Expected: exit 0, no output.

- [ ] **Step 3: Commit**

```bash
git add pipeline/sources/youtube.py pipeline/transcript.py
git commit -m "fix: skip live streams in youtube fetch and decode VTT entities"
```

---

### Task 2: Fixed topic menu (`pipeline/topics.py`)

**Files:**
- Create: `pipeline/topics.py`
- Test: `tests/test_topics.py` (also creates the `tests/` directory — first tests in the repo)

**Interfaces:**
- Consumes: nothing
- Produces:
  - `TOPICS: list[dict]` — each `{"key": str, "label": str, "queries": list[dict]}`; each query is `{"source": "youtube", "query": str}` or `{"source": "npr", "feed": str}` (feed keys must exist in `pipeline/sources/npr.py::FEEDS`: `news-now`, `up-first`, `fresh-air`).
  - `menu() -> list[dict]` — `[{"key": ..., "label": ...}]` in TOPICS order, for the manifest meta.

- [ ] **Step 1: Write the failing test**

Create `tests/test_topics.py`:

```python
"""Menu integrity: unique keys, non-empty labels/queries, well-formed query dicts."""
import unittest

from pipeline import topics


class TestTopics(unittest.TestCase):
    def test_eight_topics_with_unique_keys(self):
        keys = [t["key"] for t in topics.TOPICS]
        self.assertEqual(len(keys), 8)
        self.assertEqual(len(keys), len(set(keys)))

    def test_expected_menu_keys(self):
        self.assertEqual(
            [t["key"] for t in topics.TOPICS],
            ["everyday", "news", "science", "business",
             "travel", "food", "health", "culture"],
        )

    def test_labels_and_queries_non_empty(self):
        for t in topics.TOPICS:
            self.assertTrue(t["label"].strip(), t["key"])
            self.assertTrue(t["queries"], t["key"])

    def test_queries_well_formed(self):
        from pipeline.sources.npr import FEEDS
        for t in topics.TOPICS:
            for q in t["queries"]:
                self.assertIn(q["source"], ("youtube", "npr"), t["key"])
                if q["source"] == "youtube":
                    self.assertTrue(q["query"].strip(), t["key"])
                else:
                    self.assertIn(q["feed"], FEEDS, t["key"])

    def test_menu_returns_key_label_pairs(self):
        m = topics.menu()
        self.assertEqual(len(m), len(topics.TOPICS))
        for entry, t in zip(m, topics.TOPICS):
            self.assertEqual(entry, {"key": t["key"], "label": t["label"]})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_topics -v`
Expected: FAIL/ERROR with `ModuleNotFoundError: No module named 'pipeline.topics'`

- [ ] **Step 3: Write the module**

Create `pipeline/topics.py`:

```python
"""Fixed topic menu for the daily build.

Each topic maps to the search queries the `daily` command runs. Queries are
tunable config, not code — adjust them freely without touching the pipeline.
"""

TOPICS = [
    {"key": "everyday", "label": "Everyday Conversation",
     "queries": [{"source": "youtube", "query": "easy english conversation"},
                 {"source": "youtube", "query": "daily english dialogue"}]},
    {"key": "news", "label": "News & Current Events",
     "queries": [{"source": "npr", "feed": "news-now"},
                 {"source": "youtube", "query": "english news for learners"}]},
    {"key": "science", "label": "Science & Technology",
     "queries": [{"source": "youtube", "query": "science explained simply"},
                 {"source": "youtube", "query": "how things work"}]},
    {"key": "business", "label": "Business & Work",
     "queries": [{"source": "youtube", "query": "business english conversation"}]},
    {"key": "travel", "label": "Travel",
     "queries": [{"source": "youtube", "query": "travel english"},
                 {"source": "youtube", "query": "airport hotel conversation english"}]},
    {"key": "food", "label": "Food & Cooking",
     "queries": [{"source": "youtube", "query": "cooking recipe english easy"}]},
    {"key": "health", "label": "Health & Fitness",
     "queries": [{"source": "youtube", "query": "health tips english"},
                 {"source": "youtube", "query": "fitness explained"}]},
    {"key": "culture", "label": "Culture & Entertainment",
     "queries": [{"source": "youtube", "query": "movie review english"},
                 {"source": "youtube", "query": "pop culture explained"}]},
]


def menu():
    """The [{key, label}] list embedded in the daily manifest meta."""
    return [{"key": t["key"], "label": t["label"]} for t in TOPICS]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_topics -v`
Expected: `OK` (5 tests pass)

- [ ] **Step 5: Commit**

```bash
git add pipeline/topics.py tests/test_topics.py
git commit -m "feat: fixed topic menu for the daily build"
```

---

### Task 3: Offline difficulty heuristic (`pipeline/difficulty.py`)

**Files:**
- Create: `pipeline/difficulty.py`
- Test: `tests/test_difficulty.py`

**Interfaces:**
- Consumes: nothing
- Produces: `score(transcript, duration) -> "beginner" | "intermediate" | "advanced" | None`
  - `transcript: str | None`, `duration: float` seconds.
  - Returns `None` for missing/empty transcript, non-positive duration, or fewer than `MIN_WORDS` words.
  - Deterministic pure function; all tunable thresholds are module-level constants.

- [ ] **Step 1: Write the failing test**

Create `tests/test_difficulty.py`:

```python
"""Crafted transcripts -> expected bands, plus None/edge and monotonicity checks."""
import unittest

from pipeline import difficulty

BANDS = ["beginner", "intermediate", "advanced"]

# All short/common words -> minimal lexical load.
SIMPLE = "hi we go to the shop now and we get milk and eggs "
# Everyday sentence with a couple of medium words -> moderate lexical load.
MODERATE = "today we will visit the market and buy some fresh bread for dinner "
# Long/dense vocabulary -> maximal lexical load.
DENSE = ("international negotiations regarding infrastructure development "
         "accelerated significantly throughout complicated parliamentary procedures ")


def repeat_to_wpm(sentence, wpm, duration):
    """Repeat `sentence` so that `words / duration * 60` ~= wpm."""
    words = sentence.split()
    target = max(1, round(wpm * duration / 60))
    reps = (target // len(words)) + 1
    return " ".join((words * reps)[:target])


class TestScore(unittest.TestCase):
    def test_slow_simple_is_beginner(self):
        text = repeat_to_wpm(SIMPLE, wpm=70, duration=30)
        self.assertEqual(difficulty.score(text, 30), "beginner")

    def test_moderate_pace_is_intermediate(self):
        text = repeat_to_wpm(MODERATE, wpm=140, duration=30)
        self.assertEqual(difficulty.score(text, 30), "intermediate")

    def test_fast_dense_is_advanced(self):
        text = repeat_to_wpm(DENSE, wpm=220, duration=30)
        self.assertEqual(difficulty.score(text, 30), "advanced")

    def test_unscorable_inputs_return_none(self):
        self.assertIsNone(difficulty.score(None, 10))
        self.assertIsNone(difficulty.score("", 10))
        self.assertIsNone(difficulty.score("hello there world", 10))  # < MIN_WORDS
        self.assertIsNone(difficulty.score("plenty of words here to score fine", 0))
        self.assertIsNone(difficulty.score("plenty of words here to score fine", -3))

    def test_faster_speech_never_scores_easier(self):
        """Monotonicity: same text at higher wpm -> band index >= lower wpm's."""
        for sentence in (SIMPLE, MODERATE, DENSE):
            previous = -1
            for wpm in (60, 100, 140, 180, 220, 260):
                text = repeat_to_wpm(sentence, wpm=wpm, duration=30)
                band = difficulty.score(text, 30)
                self.assertIsNotNone(band)
                self.assertGreaterEqual(BANDS.index(band), previous)
                previous = BANDS.index(band)

    def test_denser_vocabulary_never_scores_easier(self):
        """Monotonicity: at fixed wpm, SIMPLE <= MODERATE <= DENSE — and the
        lexical signal must actually change a band at some sampled wpm."""
        strictly_harder = False
        for wpm in (80, 130, 160, 200):
            bands = [BANDS.index(difficulty.score(repeat_to_wpm(s, wpm, 30), 30))
                     for s in (SIMPLE, MODERATE, DENSE)]
            self.assertEqual(bands, sorted(bands))
            strictly_harder = strictly_harder or bands[2] > bands[0]
        self.assertTrue(strictly_harder,
                        "lexical load never changed a band at any sampled wpm")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_difficulty -v`
Expected: FAIL/ERROR with `ModuleNotFoundError: No module named 'pipeline.difficulty'`

- [ ] **Step 3: Write the module**

Create `pipeline/difficulty.py`:

```python
"""Offline difficulty scoring: 3 bands from speech rate + lexical load.

Pure function of (transcript, duration) — deterministic, no LLM, no I/O.
Speech rate (words per minute) is the primary signal; lexical load (mean
word length + share of 7+ character words) is secondary. The combined 0-1
score is bucketed into beginner / intermediate / advanced.
"""
import re

# ---- tunable thresholds (anchor: native conversational speech ~150 wpm) ----
MIN_WORDS = 5            # refuse to score below this many words
SLOW_WPM = 90.0          # at or below -> rate score 0
FAST_WPM = 190.0         # at or above -> rate score 1
SHORT_MEAN_LEN = 3.5     # mean word length at or below -> length score 0
LONG_MEAN_LEN = 6.0      # mean word length at or above -> length score 1
LONG_WORD_CHARS = 7      # a word this long counts as "long"
LONG_SHARE_FULL = 0.35   # this share of long words -> share score 1
RATE_WEIGHT = 0.7        # speech rate is the primary signal
LEX_WEIGHT = 0.3
BEGINNER_MAX = 0.35      # combined score below this -> beginner
INTERMEDIATE_MAX = 0.65  # below this -> intermediate; else advanced

_WORD = re.compile(r"[A-Za-zÀ-ÿ']+")


def _clamp01(x):
    return max(0.0, min(1.0, x))


def score(transcript, duration):
    """Band for one clip, or None when there is too little signal to score."""
    if not transcript or not duration or duration <= 0:
        return None
    words = _WORD.findall(transcript)
    if len(words) < MIN_WORDS:
        return None

    wpm = len(words) / duration * 60.0
    rate = _clamp01((wpm - SLOW_WPM) / (FAST_WPM - SLOW_WPM))

    mean_len = sum(len(w) for w in words) / len(words)
    length = _clamp01((mean_len - SHORT_MEAN_LEN) / (LONG_MEAN_LEN - SHORT_MEAN_LEN))
    long_share = sum(1 for w in words if len(w) >= LONG_WORD_CHARS) / len(words)
    share = _clamp01(long_share / LONG_SHARE_FULL)
    lex = 0.6 * length + 0.4 * share

    combined = RATE_WEIGHT * rate + LEX_WEIGHT * lex
    if combined < BEGINNER_MAX:
        return "beginner"
    if combined < INTERMEDIATE_MAX:
        return "intermediate"
    return "advanced"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_difficulty -v`
Expected: `OK` (6 tests pass). If a band assertion fails, adjust the crafted transcript or the threshold constants (they are explicitly tunable) — but keep `test_unscorable_inputs_return_none` and both monotonicity tests passing untouched.

- [ ] **Step 5: Commit**

```bash
git add pipeline/difficulty.py tests/test_difficulty.py
git commit -m "feat: offline 3-band difficulty heuristic"
```

---

### Task 4: Manifest v2 — clip tagging + daily replace (`pipeline/manifest.py`)

**Files:**
- Modify: `pipeline/manifest.py`
- Test: `tests/test_manifest.py`

**Interfaces:**
- Consumes: `difficulty.score(transcript, duration)` from Task 3.
- Produces:
  - `build_clips(item, out_dir=None, max_clips_per_item=8, topic=None)` — unchanged behavior plus every clip dict gains `"topic": topic` and `"difficulty": difficulty.score(text, end - start)`.
  - `write_daily_manifest(clips, topics_menu, generated, data_dir=None) -> (path, count)` — **replaces** `manifest.json` with `{"generated", "topics", "clips"}`.
  - `append_manifest(clips, data_dir=None)` — unchanged signature; now preserves existing `generated`/`topics` meta instead of dropping it.

- [ ] **Step 1: Write the failing test**

Create `tests/test_manifest.py`:

```python
"""write_daily_manifest replaces; append_manifest merges and keeps meta."""
import json
import os
import tempfile
import unittest

from pipeline import manifest


def clip(cid, topic="everyday", difficulty="beginner"):
    return {"id": cid, "source": "demo", "title": cid, "uploader": "", "url": "",
            "language": "en", "audio": f"data/clips/{cid}.mp3", "duration": 10.0,
            "transcript": "hello", "question": None,
            "topic": topic, "difficulty": difficulty}


MENU = [{"key": "everyday", "label": "Everyday Conversation"}]


class TestWriteDailyManifest(unittest.TestCase):
    def test_writes_meta_and_clips(self):
        with tempfile.TemporaryDirectory() as d:
            path, count = manifest.write_daily_manifest(
                [clip("a"), clip("b")], MENU, "2026-07-19", data_dir=d)
            self.assertEqual(count, 2)
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
            self.assertEqual(doc["generated"], "2026-07-19")
            self.assertEqual(doc["topics"], MENU)
            self.assertEqual([c["id"] for c in doc["clips"]], ["a", "b"])

    def test_replaces_previous_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            manifest.write_daily_manifest([clip("old")], MENU, "2026-07-18", data_dir=d)
            path, count = manifest.write_daily_manifest(
                [clip("new")], MENU, "2026-07-19", data_dir=d)
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
            self.assertEqual(count, 1)
            self.assertEqual([c["id"] for c in doc["clips"]], ["new"])
            self.assertEqual(doc["generated"], "2026-07-19")


class TestAppendManifest(unittest.TestCase):
    def test_appends_and_dedupes(self):
        with tempfile.TemporaryDirectory() as d:
            manifest.append_manifest([clip("a")], data_dir=d)
            path, count = manifest.append_manifest([clip("a"), clip("b")], data_dir=d)
            self.assertEqual(count, 2)
            with open(path, encoding="utf-8") as f:
                ids = {c["id"] for c in json.load(f)["clips"]}
            self.assertEqual(ids, {"a", "b"})

    def test_preserves_daily_meta(self):
        with tempfile.TemporaryDirectory() as d:
            manifest.write_daily_manifest([clip("a")], MENU, "2026-07-19", data_dir=d)
            path, _ = manifest.append_manifest([clip("b")], data_dir=d)
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
            self.assertEqual(doc["generated"], "2026-07-19")
            self.assertEqual(doc["topics"], MENU)
            self.assertEqual(len(doc["clips"]), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_manifest -v`
Expected: `AttributeError: module 'pipeline.manifest' has no attribute 'write_daily_manifest'` (the two append tests may pass; the meta-preservation one fails).

- [ ] **Step 3: Modify `pipeline/manifest.py`**

Change the import line near the top:

```python
from . import difficulty, questions, segment
```

Change the `build_clips` signature and the clip dict (currently `manifest.py:29-61`):

```python
def build_clips(item, out_dir=None, max_clips_per_item=8, topic=None):
    """Segment one SourceItem into clips; returns manifest clip dicts."""
```

and inside the loop, append two keys to the dict passed to `clips.append({...})`, after `"question": q,`:

```python
            "topic": topic,
            "difficulty": difficulty.score(text, end - start),
```

Replace `append_manifest` (currently `manifest.py:64-79`) with both writers:

```python
def append_manifest(clips, data_dir=None):
    """Merge clips into web/data/manifest.json (deduped by id), keeping any
    daily meta (generated/topics) already present."""
    data_dir = data_dir or WEB_DATA
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "manifest.json")
    doc = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    by_id = {c["id"]: c for c in doc.get("clips", [])}
    for c in clips:
        by_id[c["id"]] = c
    doc["clips"] = list(by_id.values())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return path, len(doc["clips"])


def write_daily_manifest(clips, topics_menu, generated, data_dir=None):
    """Replace manifest.json with today's build: meta + fresh clip list.

    This is the entire contract between the daily build and every app
    (web now, iOS later): {generated, topics, clips}.
    """
    data_dir = data_dir or WEB_DATA
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "manifest.json")
    doc = {"generated": generated, "topics": topics_menu, "clips": clips}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return path, len(clips)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m unittest tests.test_manifest -v`
Expected: `OK` (4 tests pass)

Run the whole suite too: `uv run python -m unittest discover -s tests -v`
Expected: `OK` (all tests from Tasks 2-4 pass)

- [ ] **Step 5: Commit**

```bash
git add pipeline/manifest.py tests/test_manifest.py
git commit -m "feat: tag clips with topic/difficulty and add daily manifest writer"
```

---

### Task 5: `daily` subcommand + tagged demo (`pipeline/__main__.py`)

**Files:**
- Modify: `pipeline/__main__.py`

**Interfaces:**
- Consumes: `topics.TOPICS` / `topics.menu()` (Task 2), `manifest.build_clips(item, topic=...)` and `manifest.write_daily_manifest(clips, topics_menu, generated)` (Task 4), existing `youtube.fetch(query, workdir, max_items=, max_duration=, cookies_from_browser=, verbose=)` and `npr.fetch(feed, workdir, max_items=)`.
- Produces: `python -m pipeline daily [--per-topic N] [--max-duration S] [--cookies-from-browser B] [--verbose]`; `python -m pipeline demo` now emits clips tagged `topic="everyday"` + computed difficulty. `youtube`/`tiktok`/`npr`/`serve` unchanged.

- [ ] **Step 1: Modify `_ingest` to pass a topic through**

In `pipeline/__main__.py`, change `_ingest` (currently lines 19-31):

```python
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
```

and change the demo branch (currently lines 81-83) so onboarding is demoable offline:

```python
    elif args.cmd == "demo":
        from . import demo
        _ingest(demo.synthesize(workdir), topic="everyday")
```

- [ ] **Step 2: Add the `daily` subparser**

After the `demo`/`serve` subparsers (currently lines 60-61), add:

```python
    daily = sub.add_parser("daily", help="build today's manifest across the fixed topic menu")
    daily.add_argument("--per-topic", type=int, default=3, metavar="N",
                       help="source items to fetch per topic (default 3)")
    daily.add_argument("--max-duration", type=int, default=900, metavar="SECONDS",
                       help="skip videos longer than this (default 900)")
    daily.add_argument("--cookies-from-browser", metavar="BROWSER",
                       help="use browser cookies to pass YouTube bot checks (chrome, firefox, safari, edge)")
    daily.add_argument("--verbose", "-v", action="store_true", help="show full yt-dlp output")
```

- [ ] **Step 3: Add the `daily` handler**

Add a branch before `elif args.cmd == "serve":`:

```python
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
            summary.append((t["key"], len(items), len(clips)))
            all_clips.extend(clips)
        generated = datetime.date.today().isoformat()
        path, total = manifest.write_daily_manifest(all_clips, topics.menu(), generated)
        print(f"\nDaily build {generated} — {total} clips: {path}")
        for key, n_items, n_clips in summary:
            note = "" if n_clips else "  (nothing today)"
            print(f"  {key:10s} {n_items} items -> {n_clips} clips{note}")
        dist = {}
        for c in all_clips:
            band = c["difficulty"] or "unrated"
            dist[band] = dist.get(band, 0) + 1
        print("Difficulty: " + (", ".join(
            f"{band}: {dist[band]}" for band in
            ("beginner", "intermediate", "advanced", "unrated") if band in dist)
            or "no clips"))
```

- [ ] **Step 4: Verify — compile, help text, offline demo E2E**

Run: `uv run python -m compileall -q pipeline`
Expected: exit 0.

Run: `uv run python -m pipeline daily --help`
Expected: usage shows `--per-topic`, `--max-duration`, `--cookies-from-browser`, `--verbose`.

Run: `uv run python -m pipeline demo`
Expected: prints 3 episodes with clip counts, then `Manifest now has N clips: .../web/data/manifest.json` (espeak-ng and ffmpeg are installed).

Run: `uv run python -c "
import json; doc = json.load(open('web/data/manifest.json'))
demo = [c for c in doc['clips'] if c['source'] == 'demo']
assert demo, 'no demo clips'
assert all(c['topic'] == 'everyday' for c in demo), 'demo clips not tagged everyday'
bands = {c['difficulty'] for c in demo}
assert bands <= {'beginner', 'intermediate', 'advanced', None}, bands
assert bands - {None}, 'no demo clip got a difficulty band'
print('demo clips tagged OK:', sorted(b for b in bands if b))"`
Expected: `demo clips tagged OK: [...]` with at least one band.

Note: do NOT run the full network `daily` build here — it hits YouTube for 8 topics. Task 7 covers a live smoke run.

- [ ] **Step 5: Run the full test suite**

Run: `uv run python -m unittest discover -s tests -v`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add pipeline/__main__.py
git commit -m "feat: cliplingo daily build command; demo clips tagged for onboarding"
```

Do not commit `web/data/` changes from the demo run (check whether the repo tracks `web/data/manifest.json` — if `git status` shows it modified, leave it out of this commit and restore it at the end of Task 7 with `git checkout -- web/data` only if the user's original manifest should be kept; otherwise leave the fresh demo manifest for browser verification).

---

### Task 6: Web onboarding + filtered feed (`web/`)

**Files:**
- Modify: `web/index.html`, `web/app.js`, `web/style.css`

**Interfaces:**
- Consumes: manifest v2 (`generated`, `topics: [{key,label}]`, clips with `topic`/`difficulty`) from Task 4/5.
- Produces: `localStorage["cliplingo.prefs"] = {"topics": [...], "level": "..."}`; `filterClips(clips, prefs)` implementing the spec's 5-rule feed composition; gear button reopening onboarding; empty-state message. Backward-compatible: a manifest with no topics meta and no per-clip topics shows all clips with no onboarding and no gear.

- [ ] **Step 1: Add onboarding markup to `web/index.html`**

Insert between the `#start-overlay` block and `<main id="feed">` (after line 17):

```html
<div id="onboarding" hidden>
  <div class="onboarding-card">
    <h2>Build your daily feed</h2>
    <p class="onboarding-hint">Pick one or more topics and your level.</p>
    <h3>Topics</h3>
    <div id="topic-chips" class="chips"></div>
    <h3>Level</h3>
    <div id="level-cards" class="level-cards"></div>
    <button id="prefs-save" disabled>Start my feed</button>
  </div>
</div>
<button id="edit-prefs" hidden aria-label="edit topics and level" title="Edit topics &amp; level">⚙</button>
```

And inside `<main id="feed">` change line 18 to include the empty state:

```html
<main id="feed" aria-label="clip feed">
  <p id="empty-state" hidden>Nothing matches your picks today.<br>Try more topics or a different level.</p>
</main>
```

- [ ] **Step 2: Rework the load flow in `web/app.js`**

Keep `buildCard`, `observeCards`, `shuffle`, and the start-button handler exactly as they are. Replace the header block (lines 4-23: the consts + `loadFeed`) with:

```js
const feed = document.getElementById("feed");
const template = document.getElementById("card-template");
const overlay = document.getElementById("start-overlay");
const onboarding = document.getElementById("onboarding");
const topicChipsEl = document.getElementById("topic-chips");
const levelCardsEl = document.getElementById("level-cards");
const saveBtn = document.getElementById("prefs-save");
const gearBtn = document.getElementById("edit-prefs");
const emptyState = document.getElementById("empty-state");
let started = false;
let allClips = [];
let menuTopics = [];

const PREFS_KEY = "cliplingo.prefs";
const LEVELS = ["beginner", "intermediate", "advanced"];
const LEVEL_HINTS = {
  beginner: "Slow & simple",
  intermediate: "Everyday pace",
  advanced: "Fast & rich",
};
const FEED_CAP = 20;

async function loadFeed() {
  let manifest;
  try {
    const res = await fetch("data/manifest.json");
    manifest = await res.json();
  } catch {
    overlay.querySelector("p").textContent =
      "No feed found. Run `python -m pipeline demo` first, then refresh.";
    document.getElementById("start-btn").hidden = true;
    return;
  }
  allClips = manifest.clips || [];
  menuTopics = topicMenu(manifest);
  if (!menuTopics.length) {
    renderFeed(shuffle(allClips)); // legacy manifest: show everything
    return;
  }
  gearBtn.hidden = false;
  const prefs = loadPrefs();
  if (!prefs) {
    showOnboarding(menuTopics, { topics: [], level: null });
  } else {
    renderFeed(filterClips(allClips, prefs));
  }
}

/* Menu from manifest meta; fall back to topics present on clips. */
function topicMenu(manifest) {
  if (Array.isArray(manifest.topics) && manifest.topics.length) return manifest.topics;
  const keys = [...new Set((manifest.clips || []).map((c) => c.topic).filter(Boolean))];
  return keys.map((key) => ({ key, label: key[0].toUpperCase() + key.slice(1) }));
}

function loadPrefs() {
  try {
    const p = JSON.parse(localStorage.getItem(PREFS_KEY));
    if (p && Array.isArray(p.topics) && p.topics.length && LEVELS.includes(p.level)) return p;
  } catch {}
  return null;
}

/* Feed composition (spec): candidates -> primary level pool -> top up from
 * adjacent levels nearest-first (lower level first on ties) until the cap ->
 * shuffle -> cap. Unrated (null difficulty) clips never enter a leveled feed. */
function filterClips(clips, prefs) {
  const levelIdx = LEVELS.indexOf(prefs.level);
  const candidates = clips.filter(
    (c) => prefs.topics.includes(c.topic) && LEVELS.includes(c.difficulty)
  );
  const picked = candidates.filter((c) => c.difficulty === prefs.level);
  if (picked.length < FEED_CAP) {
    const fallbackOrder = LEVELS.map((lvl, i) => ({ lvl, dist: Math.abs(i - levelIdx), i }))
      .filter((o) => o.dist > 0)
      .sort((a, b) => a.dist - b.dist || a.i - b.i)
      .map((o) => o.lvl);
    for (const lvl of fallbackOrder) {
      for (const c of candidates) {
        if (picked.length >= FEED_CAP) break;
        if (c.difficulty === lvl) picked.push(c);
      }
    }
  }
  return shuffle(picked).slice(0, FEED_CAP);
}

function renderFeed(clips) {
  feed.querySelectorAll(".card").forEach((c) => c.remove());
  emptyState.hidden = clips.length > 0;
  clips.forEach((clip) => feed.appendChild(buildCard(clip)));
  observeCards();
  if (started) {
    const first = feed.querySelector(".card audio");
    if (first) first.play().catch(() => {});
  }
}

function showOnboarding(topics, current) {
  const selected = new Set(current.topics);
  let level = current.level;

  topicChipsEl.replaceChildren();
  topics.forEach((t) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip" + (selected.has(t.key) ? " selected" : "");
    chip.textContent = t.label;
    chip.addEventListener("click", () => {
      selected.has(t.key) ? selected.delete(t.key) : selected.add(t.key);
      chip.classList.toggle("selected", selected.has(t.key));
      updateSave();
    });
    topicChipsEl.appendChild(chip);
  });

  levelCardsEl.replaceChildren();
  LEVELS.forEach((lvl) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "level-card" + (lvl === level ? " selected" : "");
    card.innerHTML = `<strong>${lvl[0].toUpperCase() + lvl.slice(1)}</strong><span>${LEVEL_HINTS[lvl]}</span>`;
    card.addEventListener("click", () => {
      level = lvl;
      [...levelCardsEl.children].forEach((el) => el.classList.remove("selected"));
      card.classList.add("selected");
      updateSave();
    });
    levelCardsEl.appendChild(card);
  });

  function updateSave() {
    saveBtn.disabled = !(selected.size > 0 && level);
  }
  updateSave();

  saveBtn.onclick = () => {
    const prefs = { topics: [...selected], level };
    localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
    onboarding.hidden = true;
    renderFeed(filterClips(allClips, prefs));
  };
  onboarding.hidden = false;
}

gearBtn.addEventListener("click", () => {
  showOnboarding(menuTopics, loadPrefs() || { topics: [], level: null });
});
```

(Prefs referencing topics not in today's menu are harmless: `filterClips` intersects against clip topics, and onboarding pre-selects only chips that exist.)

- [ ] **Step 3: Add styles to `web/style.css`**

Append:

```css
/* ---- onboarding ---- */
#onboarding {
  position: fixed; inset: 0; z-index: 9;
  display: flex; align-items: center; justify-content: center;
  background: radial-gradient(circle at 50% 30%, #1b2233, var(--bg) 70%);
  overflow-y: auto;
}
#onboarding[hidden] { display: none; }
.onboarding-card { max-width: 440px; width: 100%; padding: 2rem 1.4rem; }
.onboarding-card h2 { font-size: 1.6rem; }
.onboarding-hint { color: var(--muted); margin: .4rem 0 1.4rem; }
.onboarding-card h3 {
  font-size: .8rem; text-transform: uppercase; letter-spacing: 1px;
  color: var(--muted); margin: 1.2rem 0 .6rem;
}
.chips { display: flex; flex-wrap: wrap; gap: .5rem; }
.chip {
  padding: .55rem 1rem; border-radius: 999px; border: 1px solid #2c3550;
  background: var(--card); color: var(--text); font-size: .9rem; cursor: pointer;
}
.chip.selected { border-color: var(--accent); background: #1b2a4a; color: #cfe0ff; }
.level-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: .6rem; }
.level-card {
  padding: .9rem .5rem; border-radius: 12px; border: 1px solid #2c3550;
  background: var(--card); color: var(--text); cursor: pointer;
  display: flex; flex-direction: column; gap: .3rem; align-items: center;
}
.level-card span { font-size: .75rem; color: var(--muted); }
.level-card.selected { border-color: var(--accent); background: #1b2a4a; }
#prefs-save {
  margin-top: 1.6rem; width: 100%; font-size: 1.05rem; padding: .9rem;
  border: none; border-radius: 999px; background: var(--accent); color: white;
  cursor: pointer;
}
#prefs-save:disabled { opacity: .4; cursor: default; }

/* ---- gear + empty state ---- */
#edit-prefs {
  position: fixed; top: max(.8rem, env(safe-area-inset-top)); right: .9rem; z-index: 5;
  width: 42px; height: 42px; border-radius: 50%; border: 1px solid #2c3550;
  background: rgba(22, 26, 35, .8); color: var(--muted); font-size: 1.2rem; cursor: pointer;
}
#empty-state {
  height: 100dvh; display: flex; align-items: center; justify-content: center;
  text-align: center; color: var(--muted); line-height: 1.6; padding: 1.2rem;
}
#empty-state[hidden] { display: none; }
```

- [ ] **Step 4: Manual browser verification (offline E2E)**

Run: `uv run python -m pipeline serve` (background) and open `http://localhost:8000` in the browser pane.

Verify, in order (the demo manifest from Task 5 Step 4 must be in `web/data/`):
1. Clear prefs first: run `localStorage.removeItem("cliplingo.prefs")` in the console, reload.
2. Start overlay shows; click "Start listening" → onboarding overlay appears with 1 chip ("Everyday Conversation" — demo manifest has one topic) and 3 level cards; "Start my feed" disabled.
3. Select the topic + a level that exists in the demo data (check the difficulty distribution printed by Task 5's tag check) → button enables → click → feed of demo cards renders and first card plays.
4. Adjacent-level fallback: via the gear, pick a level that has no demo clips (the Task 5 Step 4 check printed which bands exist; the ~150 wpm demo audio typically leaves at least one band empty). Confirm the feed still shows clips from the nearest band rather than the empty state. If all three bands happen to exist in the demo data, instead verify fallback in the console: `filterClips(allClips.map(c => ({...c, difficulty: "advanced"})), {topics: ["everyday"], level: "beginner"})` must return a non-empty array (advanced clips backfilling a beginner feed).
5. Empty state: in the console run `filterClips([], {topics: ["everyday"], level: "beginner"})` → `[]`; then `renderFeed([])` → the "Nothing matches your picks today" message is visible. Reload to restore the real feed.
6. Gear button (top right) reopens onboarding with current picks pre-selected; changing selection rebuilds the feed.
7. Reload the page → no onboarding (prefs persisted), feed renders directly.
8. Backward-compat: in the console, `topicMenu({clips: [{id: "x"}]})` returns `[]` (a legacy manifest with no topics meta and untagged clips takes the show-everything path with no onboarding and no gear).
9. Console shows no errors.

- [ ] **Step 5: Run the Python suite (unchanged, regression)**

Run: `uv run python -m unittest discover -s tests -v && uv run python -m compileall -q pipeline`
Expected: `OK`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add web/index.html web/app.js web/style.css
git commit -m "feat: onboarding overlay and curated on-device feed filtering"
```

---

### Task 7: End-to-end wrap-up

**Files:**
- Modify: `README.md` (usage), possibly `web/data/manifest.json` (decide whether to commit the demo build)

**Interfaces:**
- Consumes: everything above.
- Produces: documented `daily` command; final green suite; branch ready for review.

- [ ] **Step 1: Document the new command and onboarding**

In `README.md`, find the usage/commands section (where `youtube`/`npr`/`demo`/`serve` are described) and add:

```markdown
### Daily curated build

    cliplingo daily [--per-topic N] [--max-duration S] [--cookies-from-browser chrome]

Fetches fresh clips for every topic in the fixed menu (`pipeline/topics.py`),
tags each clip with its topic and an offline difficulty band
(beginner/intermediate/advanced — see `pipeline/difficulty.py`), and REPLACES
`web/data/manifest.json`. On first launch the player shows an onboarding step
(pick topics + level, saved to localStorage) and filters the feed on-device —
the same contract an iOS client would use. The gear button (top right) reopens
onboarding. Scheduling (cron/CI) is intentionally not wired up yet.
```

Adjust wording/placement to match the README's existing style.

- [ ] **Step 2: Decide the state of `web/data/`**

If the repo tracks `web/data/manifest.json`: commit the fresh demo-built manifest (it makes the checked-in player work offline and exercises onboarding). If `web/data/` is gitignored, skip.

Run: `git status --porcelain web/data/` and act accordingly.

- [ ] **Step 3: Optional live smoke test of `daily` (network)**

Only if the network/YouTube cooperates — this is a smoke test, not a gate:

Run: `uv run python -m pipeline daily --per-topic 1 --max-duration 300`
Expected: per-topic summary lines (some topics may report "nothing today" — that is acceptable per spec), a difficulty distribution line, and a replaced manifest. If YouTube bot-checks block everything, note it and move on; the offline demo E2E already validated the flow.

If you ran this, rebuild the demo manifest afterwards so the committed/served state is deterministic: `uv run python -m pipeline demo` (note: demo appends to the daily manifest and preserves its meta — for a clean state, delete `web/data/manifest.json` first, then run demo).

- [ ] **Step 4: Final verification**

Run: `uv run python -m unittest discover -s tests -v && uv run python -m compileall -q pipeline`
Expected: all tests `OK`, compileall exit 0.

Run: `git status` — working tree clean except intentional changes.

- [ ] **Step 5: Commit**

```bash
git add README.md web/data/manifest.json  # second path only if tracked/intended
git commit -m "docs: document the daily curated build"
```

- [ ] **Step 6: Finish the branch**

Use the superpowers:finishing-a-development-branch skill to decide merge/PR/next steps with the user.
