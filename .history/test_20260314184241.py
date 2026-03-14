from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
EXPORT_DIR = PROJECT_ROOT / "data" / "exports"
DB_PATH = PROJECT_ROOT / "data" / "ipo_tracker.db"


def print_header(title: str) -> None:
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def run_command(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    result = subprocess.run(
        cmd,
        cwd=str(cwd or PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def find_db_file() -> Path | None:
    candidates = list(PROJECT_ROOT.rglob("ipo_tracker.db"))
    if not candidates:
        return None
    # 优先 data/ipo_tracker.db
    for c in candidates:
        if c == DB_PATH:
            return c
    return candidates[0]


def query_scalar(db_file: Path, sql: str) -> int | str | None:
    conn = sqlite3.connect(str(db_file))
    try:
        cur = conn.cursor()
        cur.execute(sql)
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def preview_csv(path: Path, title: str, max_rows: int = 5) -> None:
    print_header(title)
    print(f"Path: {path}")

    if not path.exists():
        print("File does not exist.")
        return

    print(f"Size: {path.stat().st_size} bytes")

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        print(f"Failed to read CSV: {exc}")
        return

    print(f"Shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")

    if df.empty:
        print("CSV has headers but no rows.")
        return

    print("\nHead:")
    print(df.head(max_rows).to_string(index=False))

    watch = ["PayPay", "Silver Bow", "Reddit"]
    matched = pd.DataFrame()

    for col in df.columns:
        series = df[col]
        # pandas object / string 列才做匹配
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            mask = False
            for name in watch:
                current = series.fillna("").astype(str).str.contains(name, case=False, regex=False)
                mask = current if mask is False else (mask | current)
            found = df[mask]
            if not found.empty:
                matched = pd.concat([matched, found], ignore_index=True)

    if matched.empty:
        print("\nNo rows matched PayPay / Silver Bow / Reddit.")
    else:
        matched = matched.drop_duplicates()
        print("\nRows matched PayPay / Silver Bow / Reddit:")
        print(matched.to_string(index=False))


def main() -> None:
    print_header("STEP 11 TEST - RUN_DAILY")

    run_daily_path = PROJECT_ROOT / "scripts" / "run_daily.py"
    if not run_daily_path.exists():
        print(f"Missing file: {run_daily_path}")
        sys.exit(1)

    print(f"Project root: {PROJECT_ROOT}")
    print(f"run_daily path: {run_daily_path}")

    db_file = find_db_file()
    if db_file:
        print(f"Detected DB file: {db_file}")
    else:
        print("No ipo_tracker.db found before run.")

    print_header("RUNNING scripts/run_daily.py")
    code, stdout, stderr = run_command([sys.executable, str(run_daily_path)], cwd=PROJECT_ROOT)

    print("Return code:", code)
    print("\nSTDOUT:\n")
    print(stdout if stdout.strip() else "[empty]")

    print("\nSTDERR:\n")
    print(stderr if stderr.strip() else "[empty]")

    if code != 0:
        print_header("RUN_DAILY FAILED")
        sys.exit(code)

    db_file = find_db_file()
    print_header("DATABASE CHECK")
    if not db_file or not db_file.exists():
        print("Database file not found after run.")
    else:
        print(f"Using DB file: {db_file}")
        checks = {
            "filings_count": "select count(*) from filings;",
            "offerings_count": "select count(*) from offerings;",
            "lockups_count": "select count(*) from lockups;",
        }
        for name, sql in checks.items():
            try:
                value = query_scalar(db_file, sql)
                print(f"{name}: {value}")
            except Exception as exc:
                print(f"{name}: ERROR - {exc}")

    print_header("EXPORT DIRECTORY LISTING")
    if not EXPORT_DIR.exists():
        print(f"Missing export dir: {EXPORT_DIR}")
    else:
        for item in sorted(EXPORT_DIR.iterdir()):
            if item.is_file():
                print(f"- {item.name} ({item.stat().st_size} bytes)")
            else:
                print(f"- {item.name}/")

    preview_csv(EXPORT_DIR / "upcoming_ipos.csv", "UPCOMING IPOS")
    preview_csv(EXPORT_DIR / "recent_ipos.csv", "RECENT IPOS")
    preview_csv(EXPORT_DIR / "upcoming_unlocks.csv", "UPCOMING UNLOCKS")

    print_header("STEP 11 TEST DONE")


if __name__ == "__main__":
    main()