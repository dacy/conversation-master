class FFmpegNotFoundError(RuntimeError):
    """ffmpeg is required to extract/cut audio but was not found on PATH."""
