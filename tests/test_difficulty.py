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
