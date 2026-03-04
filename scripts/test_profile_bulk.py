#!/usr/bin/env python3
"""
Test downloading company profiles from FMP bulk API
"""

import os
import requests
import pandas as pd
from pathlib import Path
from io import StringIO
import time

# API configuration
API_KEY = os.getenv('FMP_API_KEY', 'vasOaaAE5NBMgGt2HgRN7zhyJOe9P3ND')
BASE_URL = "https://financialmodelingprep.com/stable"

# Setup paths
data_dir = Path(__file__).parent.parent / 'data' / 'fmp'
data_dir.mkdir(parents=True, exist_ok=True)

print("=" * 80)
print("Testing FMP Bulk Company Profiles Download")
print("=" * 80)
print(f"Data directory: {data_dir}")
print()

# Download profile bulk data
all_profiles = []
part = 0

while True:
    url = f"{BASE_URL}/profile-bulk"
    params = {
        'part': part,
        'apikey': API_KEY
    }

    print(f"Fetching part {part}...")

    try:
        response = requests.get(url, params=params, timeout=120)

        # 400 means no more parts
        if response.status_code == 400:
            print(f"  Part {part} returned 400 - no more data available")
            break

        # 429 means rate limit
        if response.status_code == 429:
            print(f"  Rate limit hit. Waiting 60 seconds...")
            time.sleep(60)
            continue

        response.raise_for_status()

        # Parse CSV
        df = pd.read_csv(StringIO(response.text))

        if len(df) == 0:
            print(f"  Part {part} returned 0 rows - stopping")
            break

        all_profiles.append(df)
        print(f"  SUCCESS: Got {len(df):,} profiles from part {part}")

        part += 1

        # Be nice to API - wait between requests
        if part < 10:  # Don't wait after last expected part
            print(f"  Waiting 2 seconds before next request...")
            time.sleep(2)

    except Exception as e:
        print(f"  ERROR on part {part}: {e}")
        break

# Combine and save
if all_profiles:
    combined_df = pd.concat(all_profiles, ignore_index=True)
    output_file = data_dir / 'profiles_bulk.csv'
    combined_df.to_csv(output_file, index=False)

    print()
    print("=" * 80)
    print(f"SUCCESS: Downloaded {len(combined_df):,} company profiles from {len(all_profiles)} parts")
    print(f"Saved to: {output_file}")
    print("=" * 80)

    # Show sample
    print("\nSample data:")
    print(combined_df.head())
    print("\nColumns:", list(combined_df.columns))

else:
    print("\nERROR: No data downloaded")
    exit(1)
