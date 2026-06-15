import os
import re
import pathlib

# Resolve a local DATABASE_URL before importing the app:
#  1. honor an explicitly provided env var (CI / docker),
#  2. else derive from the project .env (force localhost, drop asyncpg ssl query),
#  3. else fall back to the docker-compose default.
def _local_db_url() -> str:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    env = pathlib.Path(__file__).resolve().parents[2] / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                v = line.split("=", 1)[1].strip().strip('"')
                v = re.sub(r"@[^/]+/", "@localhost:5432/", v)
                return v.split("?")[0]
    return "postgresql+asyncpg://narrative:narrative@localhost:5432/narrative"


os.environ["DATABASE_URL"] = _local_db_url()
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ["APP_ENV"] = "test"
os.environ.setdefault("SECRET_KEY", "test-secret")
