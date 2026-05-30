import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
REPORTS_DIR = BASE_DIR / "reports"
DATASETS_DIR = BASE_DIR / "datasets"
REPORTS_DIR.mkdir(exist_ok=True)

CLANG_PATH = os.environ.get("CLANG_PATH", "clang")
CLANGPP_PATH = os.environ.get("CLANGPP_PATH", "clang++")
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR}/ub_detector.db")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
MAX_SOURCE_SIZE = 200_000  # bytes
COMPILE_TIMEOUT = 60        # seconds
OPT_LEVELS = ["O0", "O1", "O2", "O3", "Os"]
