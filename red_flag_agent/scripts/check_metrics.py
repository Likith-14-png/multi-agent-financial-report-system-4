import sys
from pathlib import Path

# Ensure project root is on sys.path when running this script from /scripts
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
resp = client.get('/metrics')
print('status_code:', resp.status_code)
print('content-type:', resp.headers.get('content-type'))
text = resp.text
print('body_preview:\n', text[:2000])
