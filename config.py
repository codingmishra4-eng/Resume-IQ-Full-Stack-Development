"""
ResumeIQ — central configuration.

All tunable settings live here so the rest of the app reads a single, documented
source of truth. Environment variables (loaded from a `.env` file if present)
override the defaults, which keeps secrets like API keys out of the code.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env once at import time; existing real environment variables win.
load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent          # project root
DATA_DIR = BASE_DIR / "data"                        # SQLite lives here
GENERATED_DIR = BASE_DIR / os.getenv("GENERATED_DIR", "generated_resumes")
UPLOAD_DIR = BASE_DIR / "data" / "uploads"

# Make sure the writable folders exist (idempotent).
for _dir in (DATA_DIR, GENERATED_DIR, UPLOAD_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging — never log resume content, only file names, counts and app events.
# ---------------------------------------------------------------------------

os.makedirs(BASE_DIR / "logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(BASE_DIR / "logs" / "resumeiq.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def get_logger(name: str) -> logging.Logger:
    """Return an app-configured logger (helper so modules don't repeat setup)."""
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Upload guards
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "10"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


# ---------------------------------------------------------------------------
# ATS scoring model
# ---------------------------------------------------------------------------
# The weights below are a documented heuristic model — they are configurable so
# the weighting scheme can be tuned without touching engine code. The score is
# an *estimated* ATS-compatibility score, not an official vendor score.

@dataclass
class ScoreWeights:
    """Relative weight of each scoring category (must total ~1.0)."""

    readability: float = 0.20        # text extraction quality
    structure: float = 0.20          # recognised sections & hierarchy
    completeness: float = 0.15       # expected content sections present
    keywords: float = 0.20           # vocabulary coverage / action verbs
    formatting: float = 0.15         # bullets, dates, symbols, layout risk
    contact: float = 0.10            # parseable contact information

    def normalized(self) -> dict[str, float]:
        """Return weights rescaled to sum to 1.0 (defensive against edits)."""
        total = sum(vars(self).values()) or 1.0
        return {k: v / total for k, v in vars(self).items()}


DEFAULT_WEIGHTS = ScoreWeights()

# Minimum upload / analysis guards
MIN_WORDS_FOR_ANALYSIS = 60          # below this we call the document "too sparse"

# ---------------------------------------------------------------------------
# OpenAI (optional AI layer)
# ---------------------------------------------------------------------------

@dataclass
class AIConfig:
    """OpenAI settings. Everything is read from the environment."""

    api_key: str | None = field(default_factory=lambda: os.getenv("OPENAI_API_KEY") or None)
    model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    base_url: str | None = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL") or None)
    temperature: float = 0.4
    max_tokens: int = 900
    timeout_seconds: int = 45

    @property
    def available(self) -> bool:
        """True only when an API key was supplied via the environment."""
        return bool(self.api_key)


# ---------------------------------------------------------------------------
# App metadata
# ---------------------------------------------------------------------------

APP_NAME = "ResumeIQ"
APP_VERSION = "1.0.0"
APP_TAGLINE = "AI-powered resume analyzer, ATS checker & resume builder"
ROLE_CHOICES = ["Student", "Fresher", "Experienced", "Career Switcher"]
