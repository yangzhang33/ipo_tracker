"""HTTP client utilities with caching, retry, and rate limiting."""

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

import ssl

import httpx
import truststore

# Inject macOS / Windows / Linux native trust store into Python's ssl module
# so httpx (and anything else using ssl) honours system-installed CAs.
truststore.inject_into_ssl()
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import settings
from .logging import get_logger

logger = get_logger(__name__)

# Module-level timestamp to enforce rate limiting across calls
_last_request_time: float = 0.0


def _cache_path(url: str, suffix: str) -> Path:
    """
    Return a stable file path in the cache directory for the given URL.

    The filename is a 24-character SHA-256 prefix of the URL so paths
    stay short and filesystem-safe.
    """
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:24]
    cache_dir = settings.CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{url_hash}{suffix}"


def _rate_limit() -> None:
    """Sleep if needed to respect HTTP_RATE_LIMIT_DELAY between requests."""
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    delay = settings.HTTP_RATE_LIMIT_DELAY
    if elapsed < delay:
        time.sleep(delay - elapsed)
    _last_request_time = time.monotonic()


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(settings.HTTP_MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    reraise=True,
)
def _fetch(url: str, headers: Optional[dict] = None) -> httpx.Response:
    """
    Execute an HTTP GET request with automatic retry on transient errors.

    Retries on: TimeoutException, NetworkError (e.g. connection reset).
    Does NOT retry on HTTP 4xx/5xx — those propagate immediately.
    """
    _rate_limit()
    logger.debug("GET %s", url)
    merged_headers = {"User-Agent": settings.SEC_USER_AGENT}
    if headers:
        merged_headers.update(headers)
    response = httpx.get(
        url,
        headers=merged_headers,
        timeout=settings.HTTP_TIMEOUT,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response


def get_text(
    url: str,
    headers: Optional[dict] = None,
    use_cache: bool = True,
) -> str:
    """
    Fetch a URL and return the response body as text.

    When use_cache=True, reads from data/raw/cache/ on cache hit and
    writes there on a fresh fetch.

    Args:
        url: Target URL.
        headers: Optional extra request headers.
        use_cache: Whether to read/write the local file cache.

    Returns:
        Response body as a UTF-8 string.

    Raises:
        httpx.HTTPStatusError: On non-2xx responses.
        httpx.TimeoutException: If all retries are exhausted.
    """
    cache_file = _cache_path(url, ".txt")

    if use_cache and cache_file.exists():
        logger.debug("Cache hit: %s", cache_file.name)
        return cache_file.read_text(encoding="utf-8")

    response = _fetch(url, headers=headers)
    text = response.text

    if use_cache:
        cache_file.write_text(text, encoding="utf-8")
        logger.debug("Cached to: %s", cache_file.name)

    return text


def get_json(
    url: str,
    headers: Optional[dict] = None,
    use_cache: bool = True,
) -> dict:
    """
    Fetch a URL and return the parsed JSON response.

    When use_cache=True, reads from data/raw/cache/ on cache hit and
    writes there on a fresh fetch.

    Args:
        url: Target URL (must return JSON).
        headers: Optional extra request headers.
        use_cache: Whether to read/write the local file cache.

    Returns:
        Parsed JSON as a dict.

    Raises:
        httpx.HTTPStatusError: On non-2xx responses.
        json.JSONDecodeError: If the response body is not valid JSON.
    """
    cache_file = _cache_path(url, ".json")

    if use_cache and cache_file.exists():
        logger.debug("Cache hit: %s", cache_file.name)
        return json.loads(cache_file.read_text(encoding="utf-8"))

    response = _fetch(url, headers=headers)
    data = response.json()

    if use_cache:
        cache_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.debug("Cached to: %s", cache_file.name)

    return data
