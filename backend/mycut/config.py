import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get('MYCUT_DATA_DIR', ROOT / '.data')).resolve()
MODEL = os.environ.get('MYCUT_WHISPER_MODEL', 'large-v3')
MODEL_DIR = os.environ.get('MYCUT_WHISPER_DIR')
UPLOAD_LIMIT = 100 * 1024 * 1024


def configure():
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / 'projects').mkdir(exist_ok=True)
