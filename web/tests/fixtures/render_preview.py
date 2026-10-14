"""Browser fixtures call the real renderer without a TCP server or provider calls."""
import base64
import io
import json
from pathlib import Path
import sys
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'backend'))
from mycut import visuals

body = json.load(sys.stdin)
image = Image.open(io.BytesIO(base64.b64decode(body['_test_image']))) if body.get('_test_image') else None
canvas = visuals.Composition(body['scene'], {'visual_style': body.get('visual_style'), 'accent': body['accent']}, 360, image)
output = io.BytesIO()
canvas.frame(caption=body['scene'].get('narration', '')[:115]).save(output, format='PNG')
sys.stdout.buffer.write(output.getvalue())
