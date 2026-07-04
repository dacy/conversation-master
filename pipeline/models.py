from dataclasses import dataclass, field


@dataclass
class Cue:
    """One timed line of transcript."""
    start: float  # seconds
    end: float
    text: str


@dataclass
class SourceItem:
    """A full media item fetched from a source, before segmentation."""
    source: str          # "youtube" | "tiktok" | "npr" | "demo"
    title: str
    url: str             # attribution / original link
    audio_path: str      # local path to full audio
    language: str = "en"
    cues: list = field(default_factory=list)  # list[Cue]; empty when no transcript
    uploader: str = ""
