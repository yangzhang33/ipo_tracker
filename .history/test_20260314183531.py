from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from app.jobs.export_reports import export_reports


def print_file_preview(path: Path, title: str, max_rows: int = 5) -> None:
    print(f"\n{'=' * 80}")
    print(title)
    print(f"Path: {path}")
    print(f"{'=' * 80}")

    if not path.exists():
        print("File does not exist.")
        return

    size = path.stat().st_size
    print(f"File size: {size} bytes")

    if size == 0:
        print("File is empty.")
        return

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

    watch_names = ["PayPay", "Silver Bow", "Reddit"]
    text_cols = [c for c in df.columns if df[c].dtype == "object"]

    if text_cols:
        mask = pd.Series(False, index=df.index)
        for col in text_cols:
            for name in watch_names:
                mask = mask | df[col].fillna("").str.contains(name, case=False, regex=False)

        matched = df[mask]
        print("\nRows matching PayPay / Silver Bow / Reddit:")
        if matched.empty:
            print("No matches found.")
        else:
            print(matched.to_string(index=False))
    else:
        print("\nNo text columns available for company-name matching.")


def main() -> None:
    print("=" * 80)
    print("STEP 10 EXPORT TEST")
    print("=" * 80)

    try:
        result = export_reports()
        print("\nexport_reports() returned:")
        print(result)
    except Exception as exc:
        print("\nexport_reports() failed:")
        raise

    export_dir = Path("data/exports")
    print(f"\nChecking export directory: {export_dir.resolve()}")

    expected_files = [
        export_dir / "upcoming_ipos.csv",
        export_dir / "recent_ipos.csv",
        export_dir / "upcoming_unlocks.csv",
    ]

    print("\nDirectory listing:")
    if export_dir.exists():
        for item in sorted(export_dir.iterdir()):
            if item.is_file():
                print(f"- {item.name} ({item.stat().st_size} bytes)")
            else:
                print(f"- {item.name}/")
    else:
        print("Export directory does not exist.")

    print_file_preview(expected_files[0], "UPCOMING IPOS")
    print_file_preview(expected_files[1], "RECENT IPOS")
    print_file_preview(expected_files[2], "UPCOMING UNLOCKS")

    print(f"\n{'=' * 80}")
    print("DONE")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()