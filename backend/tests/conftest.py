"""Set the test database before any application module is imported."""

from __future__ import annotations

import os
import uuid

os.environ.setdefault("MONGO_URI", "mongodb://127.0.0.1:27020/?replicaSet=rs0")
os.environ["MONGO_DB"] = f"hris_test_{uuid.uuid4().hex[:10]}"
os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use")
