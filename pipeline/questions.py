"""Generate simple listening-comprehension questions from segment transcripts.

Prototype approach: cloze (fill-in-the-blank) multiple choice built from the
segment's own text, with distractors drawn from sibling segments. No LLM
required, fully offline. A production version could swap in an LLM here for
real comprehension questions.
"""
import random
import re

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "that", "this", "these",
    "those", "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "can", "could", "should",
    "shall", "may", "might", "must", "of", "in", "on", "at", "to", "for",
    "with", "from", "by", "about", "into", "over", "after", "before", "under",
    "again", "there", "here", "when", "where", "why", "how", "what", "which",
    "who", "whom", "it", "its", "he", "she", "they", "them", "his", "her",
    "their", "we", "our", "you", "your", "i", "me", "my", "not", "no", "yes",
    "so", "just", "very", "really", "some", "any", "all", "more", "most",
    "other", "than", "too", "also", "because", "as", "up", "down", "out",
    "off", "like", "get", "got", "going", "gonna", "know", "well", "okay",
    "right", "yeah", "um", "uh", "oh", "dont", "im", "its", "thats", "youre",
}

_WORD = re.compile(r"[A-Za-zÀ-ÿ']{4,}")


def content_words(text):
    words = []
    for w in _WORD.findall(text):
        if w.lower().strip("'") not in STOPWORDS:
            words.append(w)
    return words


def make_cloze(text, distractor_pool, rng=None):
    """Build a cloze question for `text`, or None if it has no usable word.

    distractor_pool: content words from other segments, used as wrong options.
    """
    rng = rng or random.Random(hash(text) & 0xFFFFFFFF)  # deterministic per text
    candidates = content_words(text)
    if not candidates:
        return None
    # prefer longer words: usually more meaningful, easier to distinguish
    answer = max(candidates, key=len)

    pool = sorted({w for w in distractor_pool
                   if w.lower() != answer.lower() and abs(len(w) - len(answer)) <= 3})
    if len(pool) < 3:
        return None
    distractors = rng.sample(pool, 3)

    blanked = re.sub(re.escape(answer), "_____", text, count=1)
    options = distractors + [answer]
    rng.shuffle(options)
    return {
        "type": "cloze",
        "prompt": blanked,
        "options": options,
        "answer_index": options.index(answer),
    }
