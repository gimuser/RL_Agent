#!/usr/bin/env python3
"""Download train/test files from a Kaggle dataset using kagglehub.

This script installs missing Python dependencies automatically and downloads the
latest version of the dataset from Kaggle. It can optionally infer common
train/test filenames when they are not provided explicitly.

Usage:
  python download_kaggle_dataset.py
  python download_kaggle_dataset.py --dataset avijitjana101/microsoft-soc-dataset
  python download_kaggle_dataset.py --train-file train.csv --test-file test.csv
  python download_kaggle_dataset.py --output-dir ../data
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

REQUIRED_PACKAGE = "kagglehub[pandas-datasets]"
KAGGLE_CLI_PACKAGE = "kaggle"
DEFAULT_DATASET = "avijitjana101/microsoft-soc-dataset"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
TRAIN_CANDIDATES = [
    "train.csv",
    "training.csv",
    "train_data.csv",
    "trainset.csv",
    "train_set.csv",
    "x_train.csv",
    "train-data.csv",
]
TEST_CANDIDATES = [
    "test.csv",
    "testing.csv",
    "test_data.csv",
    "testset.csv",
    "test_set.csv",
    "x_test.csv",
    "test-data.csv",
]


def install_package(package: str) -> None:
    print(f"Installing {package}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])


def ensure_package_installed(package_name: str, import_name: str | None = None) -> None:
    import_name = import_name or package_name.split("[", 1)[0]
    if importlib.util.find_spec(import_name) is None:
        install_package(package_name)


def has_kaggle_credentials() -> bool:
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return True

    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    return kaggle_json.exists()


def list_dataset_files(dataset_slug: str) -> list[str] | None:
    ensure_package_installed(KAGGLE_CLI_PACKAGE)
    command = [sys.executable, "-m", "kaggle", "datasets", "files", "-d", dataset_slug, "--json"]
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        print("Warning: could not list files using Kaggle CLI.")
        print(result.stderr.strip())
        return None

    try:
        file_data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Warning: unexpected JSON output from Kaggle CLI.")
        return None

    if not isinstance(file_data, list):
        return None

    return [item.get("name", "") for item in file_data if isinstance(item, dict)]


def normalize_candidates(files: Iterable[str]) -> list[str]:
    return [f.strip() for f in files if f and f.strip()]


def match_file_name(files: Iterable[str], patterns: Iterable[str]) -> str | None:
    files = list(files)
    lower_to_original = {file_name.lower(): file_name for file_name in files}

    for pattern in patterns:
        pattern_lower = pattern.lower()
        if pattern_lower in lower_to_original:
            return lower_to_original[pattern_lower]

    for pattern in patterns:
        pattern_lower = pattern.lower()
        for file_name in files:
            if pattern_lower in file_name.lower():
                return file_name

    return None


def load_dataset_file(dataset_slug: str, file_path: str) -> "pandas.DataFrame":
    import kagglehub
    from kagglehub import KaggleDatasetAdapter

    print(f"Loading {file_path} from {dataset_slug}...")
    return kagglehub.load_dataset(
        KaggleDatasetAdapter.PANDAS,
        dataset_slug,
        file_path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Kaggle dataset train/test CSV files using kagglehub.")
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="Kaggle dataset slug, e.g. avijitjana101/microsoft-soc-dataset")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Local output directory for downloaded CSV files")
    parser.add_argument("--train-file", default=None, help="Exact train file name inside the Kaggle dataset")
    parser.add_argument("--test-file", default=None, help="Exact test file name inside the Kaggle dataset")
    parser.add_argument("--no-auto-list", action="store_true", help="Disable automatic Kaggle file listing; use only candidate filenames")
    return parser.parse_args()


def resolve_file_path(dataset_slug: str, requested_file: str | None, candidates: Iterable[str], discovered_files: list[str] | None, description: str) -> str:
    if requested_file:
        return requested_file

    candidate = None
    if discovered_files:
        candidate = match_file_name(discovered_files, candidates)
        if candidate:
            print(f"Detected {description} file: {candidate}")

    if candidate is None:
        candidate = match_file_name(candidates, candidates)
        if candidate:
            print(f"Trying default {description} file: {candidate}")

    if candidate is None:
        raise RuntimeError(
            f"Could not detect a {description} file automatically. "
            "Please pass --train-file and --test-file explicitly."
        )

    return candidate


def save_dataframe(df, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"Saved {path}")


def main() -> int:
    args = parse_args()

    if not has_kaggle_credentials():
        print("Kaggle credentials not found.")
        print("Set KAGGLE_USERNAME and KAGGLE_KEY environment variables, or create ~/.kaggle/kaggle.json.")
        return 1

    ensure_package_installed(REQUIRED_PACKAGE)

    available_files = None
    if not args.no_auto_list:
        available_files = list_dataset_files(args.dataset)
        if available_files:
            print("Dataset files discovered:")
            for file_name in available_files:
                print("  -", file_name)

    train_file = resolve_file_path(args.dataset, args.train_file, TRAIN_CANDIDATES, available_files, "train")
    test_file = resolve_file_path(args.dataset, args.test_file, TEST_CANDIDATES, available_files, "test")

    try:
        train_df = load_dataset_file(args.dataset, train_file)
    except Exception as exc:
        print(f"Failed to load train file '{train_file}': {exc}")
        return 2

    try:
        test_df = load_dataset_file(args.dataset, test_file)
    except Exception as exc:
        print(f"Failed to load test file '{test_file}': {exc}")
        return 3

    output_dir = Path(args.output_dir).expanduser().resolve()
    save_dataframe(train_df, output_dir / Path(train_file).name)
    save_dataframe(test_df, output_dir / Path(test_file).name)

    print("\nTrain sample:\n", train_df.head().to_string(index=False))
    print("\nTest sample:\n", test_df.head().to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
