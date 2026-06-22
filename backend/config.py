import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Flask
FLASK_DEBUG: bool = os.environ.get("FLASK_DEBUG", "0").strip() == "1"
FLASK_PORT: int = int(os.environ.get("FLASK_PORT", "5050"))

# CORS
CORS_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

# Storage（路徑維持原本位置，避免破壞現有資料）
UPLOAD_DIR: str = str(BASE_DIR / "uploads" / "runs")
DB_PATH: str = str(BASE_DIR / "eda_platform.db")
LOG_DIR: str = str(BASE_DIR / "logs")
REPORT_DIR: str = str(BASE_DIR / "reports")

# AI Provider
AI_PROVIDER: str = os.environ.get("AI_PROVIDER", "anthropic").strip().lower()
ANTHROPIC_MODEL: str = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
MAX_TOKENS: int = int(os.environ.get("MAX_TOKENS", "1024"))

# Pipeline
FIXED_PIPELINE: list[str] = ["lint", "simulate", "synthesize", "dependency"]
VALID_STEPS: set[str] = set(FIXED_PIPELINE)
USE_FIXED_PIPELINE: bool = os.environ.get("USE_FIXED_PIPELINE", "true").strip().lower() in {
    "1", "true", "yes", "y"
}

# Optional runtime mode
USE_MOCK_AI: bool = os.environ.get("USE_MOCK_AI", "0").strip().lower() in {"1", "true", "yes", "y"}
