"""Central Gemini runtime for the adaptive IFSCA prep engine.

Gemini is the primary intelligence layer. Local deterministic logic remains
available as failure handling so the app stays usable if quota/network fails.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

from google import genai
from google.genai import errors, types


BACKEND_DIR = Path(__file__).resolve().parent
ENV_PATH = BACKEND_DIR / ".env"
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
DEFAULT_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "high").strip().upper() or "HIGH"
_GEMINI_CALL_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="gemini-call")
PROMPT_CONTRACT_VERSION = "gemini_exam_contract_v2"
