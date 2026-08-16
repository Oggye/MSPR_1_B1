import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVER_ROOT = ROOT / "platform" / "server"

for path in (ROOT, SERVER_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

# Importing the API dependency module must never require a live PostgreSQL
# server during the isolated IA test suite.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
