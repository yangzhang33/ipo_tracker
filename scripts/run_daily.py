"""Daily pipeline entry point for IPO Tracker.

Runs all jobs in sequence:
  1. discover_candidates   — fetch IPO candidates from Nasdaq / NYSE
  2. sync_sec_filings      — pull SEC filings for issuers with a known CIK
  3. parse_offering_data   — extract offering / capitalization fields
  4. parse_lockups         — extract lock-up period data
  5. export_reports        — write three CSV files to data/exports/

Usage
-----
::

    python scripts/run_daily.py

Each step is wrapped in an independent try/except so a single failure does
not abort the remaining pipeline.  A summary is printed at the end.
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path

# ── Make sure the project root is on sys.path so ``app.*`` imports work
# regardless of where the script is invoked from.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.utils.logging import get_logger  # noqa: E402  (after path fixup)

logger = get_logger("run_daily")


# ── Step runner ────────────────────────────────────────────────────────────────

def _run_step(name: str, fn, **kwargs) -> dict | None:
    """
    Execute one pipeline step, log start/end, and catch any exception.

    Returns the result dict from ``fn`` on success, or None on failure.
    """
    logger.info("=" * 60)
    logger.info("STEP: %s — starting", name)
    logger.info("=" * 60)
    try:
        result = fn(**kwargs)
        logger.info("STEP: %s — done  %s", name, result)
        return result
    except Exception:
        logger.error("STEP: %s — FAILED\n%s", name, traceback.format_exc())
        return None


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    started_at = datetime.now()
    logger.info("run_daily START  %s", started_at.strftime("%Y-%m-%d %H:%M:%S"))

    # Lazy imports — each job is self-contained; import errors per-step are caught
    results: dict[str, dict | None] = {}

    # 1. Discover candidates
    try:
        from app.jobs.discover_candidates import discover_candidates
        results["discover_candidates"] = _run_step(
            "discover_candidates", discover_candidates
        )
    except ImportError as exc:
        logger.error("STEP: discover_candidates — import failed: %s", exc)
        results["discover_candidates"] = None

    # 2. Sync SEC filings
    try:
        from app.jobs.sync_sec_filings import sync_sec_filings
        results["sync_sec_filings"] = _run_step(
            "sync_sec_filings", sync_sec_filings
        )
    except ImportError as exc:
        logger.error("STEP: sync_sec_filings — import failed: %s", exc)
        results["sync_sec_filings"] = None

    # 3. Parse offering data
    try:
        from app.jobs.parse_offering_data import parse_offering_data
        results["parse_offering_data"] = _run_step(
            "parse_offering_data", parse_offering_data
        )
    except ImportError as exc:
        logger.error("STEP: parse_offering_data — import failed: %s", exc)
        results["parse_offering_data"] = None

    # 4. Parse lock-ups
    try:
        from app.jobs.parse_lockups import parse_lockups
        results["parse_lockups"] = _run_step(
            "parse_lockups", parse_lockups
        )
    except ImportError as exc:
        logger.error("STEP: parse_lockups — import failed: %s", exc)
        results["parse_lockups"] = None

    # 5. Export reports
    try:
        from app.jobs.export_reports import export_reports
        results["export_reports"] = _run_step(
            "export_reports", export_reports
        )
    except ImportError as exc:
        logger.error("STEP: export_reports — import failed: %s", exc)
        results["export_reports"] = None

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = (datetime.now() - started_at).total_seconds()
    failed_steps = [name for name, r in results.items() if r is None]

    logger.info("")
    logger.info("=" * 60)
    logger.info("run_daily SUMMARY  (%.1fs)", elapsed)
    logger.info("=" * 60)
    for name, result in results.items():
        status = "OK" if result is not None else "FAILED"
        logger.info("  %-25s %s  %s", name, status, result or "")

    if failed_steps:
        logger.warning("Failed steps: %s", ", ".join(failed_steps))
    else:
        logger.info("All steps completed successfully.")

    # Print export paths if available
    export_result = results.get("export_reports")
    if export_result and export_result.get("exported_files"):
        logger.info("")
        logger.info("Exported CSV files:")
        for path in export_result["exported_files"]:
            name = path.split("/")[-1]
            rows = export_result["row_counts"].get(name, "?")
            logger.info("  %s  (%s rows)", path, rows)


if __name__ == "__main__":
    main()
