#!/usr/bin/env python3
"""
git-weekly-automation — Shared utilities

Functions used across multiple scripts. Import from sibling scripts via:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from common import load_config, get_git_user_email
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
CONFIG_FILE = PROJECT_DIR / "config.json"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Load project configuration from config.json."""
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def resolve_api_key() -> Optional[str]:
    """Resolve API key with priority: env var > config file."""
    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        return env_key
    config = load_config()
    return config.get("api_key")


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------

def get_git_user_email() -> str:
    """
    Get the global git user email from git config.
    Returns empty string if not set or git is unavailable.
    """
    try:
        result = subprocess.run(
            ["git", "config", "--global", "user.email"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            email = result.stdout.strip()
            if email:
                return email
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return ""


# ---------------------------------------------------------------------------
# ISO week helpers
# ---------------------------------------------------------------------------

def validate_iso_week(week: int) -> int:
    """
    Validate and clamp an ISO week number to 1–53.
    Exits with an error message if out of range.
    """
    if week < 1 or week > 53:
        print(f"[!] Invalid ISO week number: {week}. Must be between 1 and 53.", file=sys.stderr)
        sys.exit(1)
    return week
