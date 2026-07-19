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
