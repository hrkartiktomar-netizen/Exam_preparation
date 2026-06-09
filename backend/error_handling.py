"""ERROR HANDLING FRAMEWORK - All pillars per PROJECT_REFACTOR_PLAN.xml specifications.

Per Context7 docs for Python: Use custom exceptions, explicit error handling, graceful
degradation with cached fallback. This ensures system resilience across all pillars.

Principle: FAIL SAFELY > CRASH
"""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any, Callable, TypeVar, cast

from fastapi import HTTPException

T = TypeVar("T")


# ============================================================================
# ERROR HANDLING: CUSTOM EXCEPTIONS
# ============================================================================


class GeminiAPIError(Exception):
    """Base class for Gemini API errors."""

    pass


class GeminiRateLimitError(GeminiAPIError):
    """429 Too Many Requests - exponential backoff + retry."""

    pass


class GeminiAuthError(GeminiAPIError):
    """401/403 Authentication/Authorization - rotate API key."""

    pass


class GeminiServerError(GeminiAPIError):
    """500+ Server error - retry_after_60s."""

    pass


class DatabaseError(Exception):
    """Database operation failed (timeout, lock, FK violation)."""

    pass


class TimeoutError(Exception):
    """Operation exceeded time budget (essay grading, mock generation)."""

    pass


# ============================================================================
# ERROR HANDLING: RETRY STRATEGIES
# ============================================================================


class RetryStrategy(str, Enum):
    """Retry strategies per error type."""

    EXPONENTIAL_BACKOFF = "exponential_backoff"  # 429 rate limit
    KEY_ROTATION = "key_rotation"  # 401/403 auth
    RETRY_AFTER = "retry_after"  # 500+ server error
    CACHED_FALLBACK = "cached_fallback"  # All keys exhausted
    NO_RETRY = "no_retry"  # Client error


def get_retry_strategy(error_code: int | str, error_type: str) -> RetryStrategy:
    """Determine retry strategy based on error code and type.

    Per PROJECT_REFACTOR_PLAN.xml error handling checklist.
    """
    if isinstance(error_code, str):
        error_code = int(error_code) if error_code.isdigit() else 0

    if error_type == "gemini_api":
        if error_code == 429:
            return RetryStrategy.EXPONENTIAL_BACKOFF
        elif error_code in (401, 403):
            return RetryStrategy.KEY_ROTATION
        elif error_code >= 500:
            return RetryStrategy.RETRY_AFTER
        else:
            return RetryStrategy.NO_RETRY
    elif error_type == "database":
        if "locked" in str(error_code).lower():
            return RetryStrategy.RETRY_AFTER
        else:
            return RetryStrategy.NO_RETRY
    else:
        return RetryStrategy.NO_RETRY


async def retry_with_exponential_backoff(
    func: Callable[..., Any],
    *args,
    base_wait_seconds: int = 60,
    max_retries: int = 3,
    **kwargs,
) -> Any:
    """Retry async function with exponential backoff (2^attempt × base_wait).

    Per PROJECT_REFACTOR_PLAN.xml: 429 rate limit → exponential_backoff, retry_max_3_times
    """
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except GeminiRateLimitError as e:
            if attempt < max_retries - 1:
                wait_seconds = base_wait_seconds * (2 ** attempt)
                print(
                    f"⏳ Rate limited. Retrying in {wait_seconds}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(wait_seconds)
            else:
                print(f"❌ Rate limit: all {max_retries} retries exhausted")
                raise RuntimeError("Gemini rate limit exceeded after retries") from e


async def retry_with_fixed_delay(
    func: Callable[..., Any],
    *args,
    wait_seconds: int = 60,
    max_retries: int = 3,
    **kwargs,
) -> Any:
    """Retry async function with fixed delay (for 500+ server errors).

    Per PROJECT_REFACTOR_PLAN.xml: 500+ server error → retry_after_60s, max_3_times
    """
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except GeminiServerError as e:
            if attempt < max_retries - 1:
                print(
                    f"⏳ Server error. Retrying in {wait_seconds}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(wait_seconds)
            else:
                print(f"❌ Server error: all {max_retries} retries exhausted")
                raise RuntimeError("Gemini server error: max retries exceeded") from e


async def retry_database_with_timeout(
    func: Callable[..., Any],
    *args,
    max_retries: int = 3,
    timeout_seconds: int = 30,
    **kwargs,
) -> Any:
    """Retry database function with timeout and busy_timeout handling.

    Per Context7 docs for SQLite: PRAGMA busy_timeout = 30000 should handle locks,
    but we add explicit retry logic for safety.
    """
    for attempt in range(max_retries):
        try:
            # Wrap with timeout
            return await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                wait_seconds = 5 * (attempt + 1)
                print(
                    f"⏳ Database timeout. Retrying in {wait_seconds}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(wait_seconds)
            else:
                raise DatabaseError(
                    f"Database operation timed out after {max_retries} retries"
                ) from None
        except DatabaseError as e:
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                wait_seconds = 5 * (attempt + 1)
                print(f"⏳ Database locked. Retrying in {wait_seconds}s")
                await asyncio.sleep(wait_seconds)
            else:
                raise


# ============================================================================
# ERROR HANDLING: GRACEFUL DEGRADATION
# ============================================================================


class CachedFallback:
    """Fallback mechanism when all primary methods fail.

    Per PROJECT_REFACTOR_PLAN.xml: IF all_keys_exhausted THEN use_cached_local_questions_only
    """

    @staticmethod
    def get_cached_questions(topic: str, count: int = 10) -> list[dict[str, Any]] | None:
        """Get cached questions if Gemini completely fails."""
        # TODO: Implement caching layer (Redis, SQLite cache table)
        # For now, return None to signal: no cached fallback available
        return None

    @staticmethod
    def get_cached_amendments(limit: int = 10) -> list[dict[str, Any]] | None:
        """Get cached amendments if polling fails."""
        return None


# ============================================================================
# ERROR HANDLING: HTTP EXCEPTION MAPPING
# ============================================================================


def map_to_http_exception(error: Exception) -> HTTPException:
    """Map internal exceptions to appropriate HTTP status codes.

    Per Context7 docs for FastAPI: Use descriptive status codes + error detail.
    """
    if isinstance(error, GeminiRateLimitError):
        return HTTPException(
            status_code=503,
            detail="Gemini API temporarily rate-limited. Please retry in a moment.",
        )
    elif isinstance(error, GeminiAuthError):
        return HTTPException(
            status_code=503,
            detail="Gemini authentication failed. System administrator notified.",
        )
    elif isinstance(error, GeminiServerError):
        return HTTPException(
            status_code=503,
            detail="Gemini service temporarily unavailable. Please retry shortly.",
        )
    elif isinstance(error, DatabaseError):
        return HTTPException(
            status_code=503,
            detail="Database operation failed. Please retry.",
        )
    elif isinstance(error, asyncio.TimeoutError):
        return HTTPException(
            status_code=504,
            detail="Request timed out. Please try again.",
        )
    elif isinstance(error, ValueError):
        return HTTPException(
            status_code=422,
            detail=f"Invalid input: {str(error)}",
        )
    else:
        return HTTPException(
            status_code=500,
            detail="Internal server error. Please contact support.",
        )


# ============================================================================
# ERROR HANDLING: PER-PILLAR FRAMEWORK
# ============================================================================


class PillarErrorHandler:
    """Error handling per pillar per PROJECT_REFACTOR_PLAN.xml."""

    @staticmethod
    async def handle_gemini_error(
        error: Exception,
        operation: str,
        fallback_data: Any = None,
    ) -> Any:
        """
        Handle Gemini API errors per PROJECT_REFACTOR_PLAN.xml specifications.

        Decision tree:
        - IF 429 (rate limit) → exponential_backoff(base=60s, multiplier=2)
        - ELIF 401/403 (auth) → use_next_key_from_rotation
        - ELIF 500+ (server error) → retry_after_60s_max_3_times
        - ELIF all_keys_exhausted → use_cached_local_questions_only + log_warning
        """
        error_msg = str(error)

        if isinstance(error, GeminiRateLimitError):
            print(f"⚠️ Gemini rate limit on {operation}")
            # Caller will handle retry logic
            raise

        elif isinstance(error, GeminiAuthError):
            print(f"⚠️ Gemini auth failed on {operation} - rotating key")
            # Caller should use next API key
            raise

        elif isinstance(error, GeminiServerError):
            print(f"⚠️ Gemini server error on {operation}")
            # Caller will retry
            raise

        else:
            # Try cached fallback
            if fallback_data is not None:
                print(f"⚠️ Falling back to cached data for {operation}")
                return fallback_data

            raise RuntimeError(f"Gemini error on {operation}: {error_msg}") from error

    @staticmethod
    async def handle_database_error(error: Exception, operation: str) -> None:
        """
        Handle database errors per PROJECT_REFACTOR_PLAN.xml specifications.

        Errors:
        - IF database_locked → wait 30s, retry (PRAGMA busy_timeout should handle)
        - ELIF referential_integrity_violation → log error, return 422
        - ELIF transaction_rollback_needed → rollback and retry
        """
        error_msg = str(error)

        if "locked" in error_msg.lower():
            print(f"⚠️ Database locked on {operation} - PRAGMA busy_timeout handling")
            raise DatabaseError(f"Database locked: {error_msg}") from error

        elif "foreign key" in error_msg.lower():
            print(f"⚠️ Referential integrity violation on {operation}")
            raise ValueError(f"Invalid data: referential integrity violation") from error

        else:
            print(f"⚠️ Database error on {operation}: {error_msg}")
            raise DatabaseError(f"Database operation failed: {error_msg}") from error

    @staticmethod
    async def handle_timeout_error(
        operation: str,
        timeout_seconds: int,
        fallback: Any = None,
    ) -> Any:
        """
        Handle timeout errors per PROJECT_REFACTOR_PLAN.xml specifications.

        Operations:
        - essay_grading: timeout > 5s → return 500 with retry guidance
        - mock_generation: timeout > 30s → abort and return error
        - amendment_polling: timeout → log and retry next day
        """
        if operation == "essay_grading" and timeout_seconds > 5:
            print(f"⚠️ Essay grading timeout ({timeout_seconds}s)")
            raise asyncio.TimeoutError(
                f"Essay grading exceeded {timeout_seconds}s timeout"
            )

        elif operation == "mock_generation" and timeout_seconds > 30:
            print(f"⚠️ Mock generation timeout ({timeout_seconds}s)")
            raise asyncio.TimeoutError(
                f"Mock generation exceeded {timeout_seconds}s timeout"
            )

        elif operation == "amendment_polling":
            print(f"⚠️ Amendment polling timeout - retry next day")
            # Don't raise; let next scheduled poll retry
            return fallback

        raise asyncio.TimeoutError(f"{operation} timed out after {timeout_seconds}s")
