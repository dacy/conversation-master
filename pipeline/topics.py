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
