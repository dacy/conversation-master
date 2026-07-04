"""Offline demo source: synthesizes short spoken 'episodes' with espeak-ng.

This exists so the entire pipeline (segmentation → clip cutting → question
generation → web feed) can be exercised end-to-end without network access.
The synthesized audio stands in for a fetched YouTube/TikTok/NPR file, and
the known sentence timings stand in for a subtitle track.
"""
import os
import subprocess

from .models import Cue, SourceItem
from .segment import probe_duration

EPISODES = [
    {
        "title": "Ordering coffee",
        "language": "en",
        "voice": "en-us",
        "sentences": [
            "Good morning! What can I get started for you today?",
            "Hi, I would like a large coffee with oat milk, please.",
            "Sure thing. Would you like anything to eat with that?",
            "Actually, yes. Could I get one of those blueberry muffins?",
            "Of course. That will be seven dollars and fifty cents.",
            "Here you go. Oh, and could I have a receipt, please?",
            "Absolutely. Your order will be ready at the end of the counter.",
            "Thank you so much. Have a great day!",
        ],
    },
    {
        "title": "Asking for directions",
        "language": "en",
        "voice": "en-gb",
        "sentences": [
            "Excuse me, do you know how to get to the central library?",
            "Yes, it is about ten minutes away on foot.",
            "Walk straight down this street until you reach the traffic lights.",
            "Then turn left and you will see a large park on your right.",
            "The library is the big stone building just past the park entrance.",
            "That sounds easy enough. Is there a bus that goes there as well?",
            "The number twelve bus stops directly in front of the library.",
            "Perfect, thank you very much for your help!",
        ],
    },
    {
        "title": "Weekend plans",
        "language": "en",
        "voice": "en-us",
        "sentences": [
            "Hey, do you have any plans for the weekend?",
            "I was thinking about going hiking if the weather stays nice.",
            "That sounds fun. Which trail are you planning to take?",
            "Probably the one along the river, it has amazing views.",
            "Would you mind if I joined you? I need some exercise.",
            "Not at all, the more the merrier. Let's meet at nine.",
            "Should I bring anything, like snacks or water?",
            "Just water and good shoes. I will pack sandwiches for us both.",
        ],
    },
]

PAUSE_S = 0.45  # gap inserted between sentences


def synthesize(workdir):
    """Build demo SourceItems with real audio and accurate cue timings."""
    os.makedirs(workdir, exist_ok=True)
    items = []
    for ep in EPISODES:
        slug = ep["title"].lower().replace(" ", "-")
        parts = []
        for i, sentence in enumerate(ep["sentences"]):
            wav = os.path.join(workdir, f"{slug}-{i:02d}.wav")
            subprocess.run(
                ["espeak-ng", "-v", ep["voice"], "-s", "150", "-w", wav, sentence],
                check=True,
            )
            parts.append((wav, sentence))

        # concatenate with pauses, tracking cue timings from real durations
        cues, t = [], 0.0
        concat_list = os.path.join(workdir, f"{slug}-list.txt")
        silence = os.path.join(workdir, "silence.wav")
        if not os.path.exists(silence):
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                 "-i", f"anullsrc=r=22050:cl=mono", "-t", str(PAUSE_S), silence],
                check=True,
            )
        with open(concat_list, "w") as f:
            for wav, sentence in parts:
                dur = probe_duration(wav)
                cues.append(Cue(t, t + dur, sentence))
                f.write(f"file '{wav}'\nfile '{silence}'\n")
                t += dur + PAUSE_S

        full = os.path.join(workdir, f"{slug}.mp3")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
             "-i", concat_list, "-acodec", "libmp3lame", "-b:a", "96k", full],
            check=True,
        )
        items.append(SourceItem(
            source="demo", title=ep["title"],
            url="https://github.com/dacy/conversation-master",
            audio_path=full, language=ep["language"], cues=cues,
            uploader="synthesized demo",
        ))
    return items
