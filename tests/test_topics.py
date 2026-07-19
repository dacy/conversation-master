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
