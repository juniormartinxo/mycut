"""Explicit setup step: download the public Whisper model into the persistent cache."""
from faster_whisper.utils import download_model
from .config import MODEL
if __name__ == '__main__':
    print(download_model(MODEL))
