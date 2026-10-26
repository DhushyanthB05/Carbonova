#!/usr/bin/env python3
"""
Fetch Great Britain electricity carbon-intensity data from the official
National Energy System Operator (NESO) Carbon Intensity API.

Official Documentation:
    https://carbon-intensity.github.io/api-definitions/

Selected Endpoint:
    GET https://api.carbonintensity.org.uk/intensity/{from}/{to}

This script downloads real historical national carbon intensity data,
splits large date ranges into smaller chunks (<= 14 days) to comply with
the API limits, extracts actual and forecast intensity without fabrication,
and outputs the results into a CSV file.
"""

import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import socket
import sys
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple, Any

API_BASE_URL = "https://api.carbonintensity.org.uk"
HISTORICAL_ARCHIVE_START = datetime(2017, 9, 26, 0, 0, tzinfo=timezone.utc)
CHUNK_DAYS = 14  # Safe window to stay well below the 31-day API query limit
DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 3


def parse_utc_timestamp(ts_str: str) -> datetime:
    """
    Parse an ISO 8601 date or datetime string into a timezone-aware UTC datetime.
    Supports formats like:
      - 2024-01-01
      - 2024-01-01T00:00Z
      - 2024-01-01T00:00:00Z
      - 2024-01-01T00:00:00+00:00
      - 2024-01-01 00:00:00
    """
    ts_str = ts_str.strip()
    if not ts_str:
        raise ValueError("Empty timestamp string provided.")

    iso_str = ts_str
    if iso_str.endswith("Z") or iso_str.endswith("z"):
        iso_str = iso_str[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(iso_str)
    except ValueError:
        try:
            dt = datetime.strptime(ts_str, "%Y-%m-%d")
        except ValueError as err:
            raise ValueError(
                f"Invalid date/datetime format '{ts_str}'. Expected ISO 8601 (e.g., 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MMZ')."
            ) from err

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt


def validate_date_range(start_dt: datetime, end_dt: datetime) -> None:
    """Validate requested range against API capabilities."""
    if end_dt <= start_dt:
        raise ValueError(
            f"End timestamp ({end_dt.isoformat()}) must be strictly after start timestamp ({start_dt.isoformat()})."
        )
    if start_dt < HISTORICAL_ARCHIVE_START:
        raise ValueError(
            f"Requested start date ({start_dt.strftime('%Y-%m-%d')}) precedes the official NESO historical "
            f"archive inception date ({HISTORICAL_ARCHIVE_START.strftime('%Y-%m-%d')})."
        )


def generate_chunks(start_dt: datetime, end_dt: datetime, chunk_days: int = CHUNK_DAYS) -> List[Tuple[datetime, datetime]]:
    """Split requested datetime range into smaller intervals compliant with API limits."""
    chunks = []
    curr = start_dt
    delta = timedelta(days=chunk_days)
    while curr < end_dt:
        next_dt = min(curr + delta, end_dt)
        chunks.append((curr, next_dt))
        curr = next_dt
    return chunks


def fetch_json(url: str, timeout: int = DEFAULT_TIMEOUT, max_retries: int = MAX_RETRIES) -> Optional[dict]:
    """Fetch JSON from the API with timeout, retry backoff, and robust error handling."""
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Carbonova-DataPipeline/1.0",
        },
    )
    last_err: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    raw_data = response.read().decode("utf-8")
                    if not raw_data or raw_data.strip() == "null":
                        return None
                    return json.loads(raw_data)
                else:
                    raise RuntimeError(f"Unexpected HTTP status {response.status} from {url}")
        except urllib.error.HTTPError as e:
            last_err = e
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                pass
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                backoff = 2 ** attempt
                print(f"  [Retry] HTTP {e.code} received. Retrying in {backoff}s (attempt {attempt}/{max_retries})...")
                time.sleep(backoff)
                continue
            raise RuntimeError(f"HTTP Error {e.code} for URL {url}: {err_body or e.reason}") from e
        except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
            last_err = e
            if attempt < max_retries:
                backoff = 2 ** attempt
                print(f"  [Retry] Network error ({e}). Retrying in {backoff}s (attempt {attempt}/{max_retries})...")
                time.sleep(backoff)
                continue
            raise RuntimeError(f"Network error after {max_retries} attempts for URL {url}: {e}") from e

    raise RuntimeError(f"Failed to fetch {url}: {last_err}")


def print_pre_download_summary(start_dt: datetime, end_dt: datetime, chunks: List[Tuple[datetime, datetime]]) -> None:
    """
    Explain the selected endpoint, historical data semantics, and validation
    before starting the download execution.
    """
    print("=" * 76)
    print("UK Carbon Intensity Data Fetcher (Official NESO Carbon Intensity API)")
    print("=" * 76)
    print(f"Selected Endpoint : GET {API_BASE_URL}/intensity/{{from}}/{{to}}")
    print(f"Documentation     : https://carbon-intensity.github.io/api-definitions/")
    print(f"Historical Coverage: National GB half-hourly settlement periods (archive from 2017-09-26)")
    print("-" * 76)
    print("Data Extraction & Integrity Rules:")
    print("  1. 'carbon_intensity_gco2_per_kwh': Populated strictly with 'intensity.actual'")
    print("     recorded by NESO post-settlement. Missing values are left empty (no synthesis/interpolation).")
    print("  2. 'forecast_gco2_per_kwh': Populated strictly with 'intensity.forecast'")
    print("     if present in the official API response; otherwise left empty (never invented).")
    print("  3. 'region': Set to 'GB-national'.")
    print("  4. 'source_type': Set to 'recorded' for historical records.")
    print("  5. 'timestamp_utc': UTC timestamp marking the start of each 30-minute settlement period.")
    print("-" * 76)
    print(f"Requested Window  : {start_dt.strftime('%Y-%m-%dT%H:%MZ')} -> {end_dt.strftime('%Y-%m-%dT%H:%MZ')}")
    print(f"Request Strategy  : Split into {len(chunks)} chunk(s) of <= {CHUNK_DAYS} days each.")
    print("=" * 76)


def fetch_uk_carbon_intensity(start: str, end: str, out_path: str) -> None:
    """Download historical carbon intensity data and save to CSV."""
    start_dt = parse_utc_timestamp(start)
    end_dt = parse_utc_timestamp(end)

    validate_date_range(start_dt, end_dt)

    chunks = generate_chunks(start_dt, end_dt, CHUNK_DAYS)
    print_pre_download_summary(start_dt, end_dt, chunks)

    records: Dict[str, Dict[str, Any]] = {}
    missing_actual_count = 0

    print("\nStarting downloads...")
    for idx, (c_start, c_end) in enumerate(chunks, 1):
        from_str = c_start.strftime("%Y-%m-%dT%H:%MZ")
        to_str = c_end.strftime("%Y-%m-%dT%H:%MZ")
        url = f"{API_BASE_URL}/intensity/{from_str}/{to_str}"

        print(f"[{idx}/{len(chunks)}] Fetching {from_str} to {to_str}...")
        resp = fetch_json(url)

        if not resp or "data" not in resp or not resp["data"]:
            print(f"  -> No data returned for chunk {from_str} to {to_str}.")
            continue

        chunk_items = resp["data"]
        accepted_in_chunk = 0

        for item in chunk_items:
            item_from_str = item.get("from")
            item_to_str = item.get("to")
            if not item_from_str or not item_to_str:
                continue

            item_from_dt = parse_utc_timestamp(item_from_str)
            item_to_dt = parse_utc_timestamp(item_to_str)

            # Strictly include intervals belonging to the requested period [start_dt, end_dt]
            if item_from_dt < start_dt or item_to_dt > end_dt:
                continue

            # Deduplicate by start timestamp across chunk boundaries
            if item_from_str in records:
                continue

            intensity_obj = item.get("intensity") or {}
            actual_val = intensity_obj.get("actual")
            forecast_val = intensity_obj.get("forecast")

            actual_str = "" if actual_val is None else str(actual_val)
            forecast_str = "" if forecast_val is None else str(forecast_val)

            records[item_from_str] = {
                "timestamp_utc": item_from_str,
                "region": "GB-national",
                "carbon_intensity_gco2_per_kwh": actual_str,
                "source_type": "recorded",
                "forecast_gco2_per_kwh": forecast_str,
            }
            accepted_in_chunk += 1

        print(f"  -> Retrieved {len(chunk_items)} raw intervals, accepted {accepted_in_chunk} within window.")

    # Count total rows and missing actual values
    total_rows = len(records)
    missing_actual_count = sum(1 for r in records.values() if r["carbon_intensity_gco2_per_kwh"] == "")

    # Ensure output directory exists
    destination = Path(out_path)
    if destination.parent:
        destination.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "timestamp_utc",
        "region",
        "carbon_intensity_gco2_per_kwh",
        "source_type",
        "forecast_gco2_per_kwh",
    ]

    with open(destination, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for ts in sorted(records.keys()):
            writer.writerow(records[ts])

    print("\n" + "=" * 76)
    print("Download Summary:")
    print(f"  Output CSV File        : {destination.resolve()}")
    print(f"  Rows downloaded        : {total_rows}")
    print(f"  Missing actual values  : {missing_actual_count}")
    print("=" * 76)


def main():
    parser = argparse.ArgumentParser(
        description="Download real historical UK Carbon Intensity data from official NESO API."
    )
    parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="Start UTC datetime/date (ISO 8601, e.g., '2024-01-01T00:00Z' or '2024-01-01')",
    )
    parser.add_argument(
        "--end",
        type=str,
        required=True,
        help="End UTC datetime/date (ISO 8601, e.g., '2024-01-08T00:00Z' or '2024-01-08')",
    )
    parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Path to output CSV file (e.g., 'data/uk_carbon_intensity_2024.csv')",
    )

    args = parser.parse_args()

    try:
        fetch_uk_carbon_intensity(args.start, args.end, args.out)
    except Exception as e:
        print(f"\n[Error] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
