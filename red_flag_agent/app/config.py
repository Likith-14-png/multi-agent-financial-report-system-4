import os
from pathlib import Path
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent
ROOT_DIR = BASE_DIR.parent

for env_file in [APP_DIR / ".env", BASE_DIR / ".env", ROOT_DIR / ".env"]:
    if env_file.is_file():
        load_dotenv(dotenv_path=env_file)

load_dotenv()

CHROMA_DIR = os.getenv("CHROMA_DB_PATH", os.getenv("CHROMA_DIR", str(BASE_DIR / "chroma_db")))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")
DEFAULT_COLLECTION_NAME = os.getenv("DEFAULT_COLLECTION_NAME", "default_collection")
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "5"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
GEMINI_BACKOFF_BASE = float(os.getenv("GEMINI_BACKOFF_BASE", "0.5"))
GEMINI_BACKOFF_MAX = float(os.getenv("GEMINI_BACKOFF_MAX", "8.0"))
