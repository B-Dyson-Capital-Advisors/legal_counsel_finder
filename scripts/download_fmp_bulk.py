#!/usr/bin/env python3
"""
Download company profiles from Financial Modeling Prep bulk API
This provides market cap data for stock screening/sorting
"""

import os
import sys
import requests
import pandas as pd
from pathlib import Path
from io import StringIO
import time

# Load .env file if exists (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class FMPBulkDownloader:
    """Download bulk company profile data from FMP API"""

    BASE_URL = "https://financialmodelingprep.com/stable"

    def __init__(self, api_key=None):
        """Initialize with API key from environment or Streamlit secrets"""
        self.api_key = api_key or os.getenv('FMP_API_KEY')

        # Try Streamlit secrets if available
        if not self.api_key:
            try:
                import streamlit as st
                self.api_key = st.secrets.get('FMP_API_KEY')
            except:
                pass

        if not self.api_key:
            raise ValueError("FMP_API_KEY not found in environment variables or Streamlit secrets")

        # Create data directories
        self.data_dir = Path(__file__).parent.parent / 'data' / 'fmp'
        self.data_dir.mkdir(parents=True, exist_ok=True)

        print(f"Data directory: {self.data_dir}")

    def download_profile_bulk(self):
        """
        Download bulk company profiles (all parts)
        URL: https://financialmodelingprep.com/stable/profile-bulk?part=N&apikey=...

        Returns: symbol, companyName, sector, industry, marketCap, etc.
        """
        print("\nDownloading company profiles bulk...")

        all_profiles = []
        part = 0
        max_retries = 3

        while True:
            url = f"{self.BASE_URL}/profile-bulk"
            params = {
                'part': part,
                'apikey': self.api_key
            }

            print(f"  Fetching part {part}...")

            retry_count = 0
            success = False

            while retry_count < max_retries and not success:
                try:
                    response = requests.get(url, params=params, timeout=120)

                    # 400 Bad Request means no more parts available
                    if response.status_code == 400:
                        print(f"    Part {part} returned 400 - no more data")
                        return all_profiles

                    # 429 means rate limit - wait and retry
                    if response.status_code == 429:
                        wait_time = 60 * (retry_count + 1)
                        print(f"    Rate limit hit. Waiting {wait_time}s...")
                        time.sleep(wait_time)
                        retry_count += 1
                        continue

                    response.raise_for_status()

                    # Parse CSV
                    df = pd.read_csv(StringIO(response.text))

                    if len(df) == 0:
                        print(f"    Part {part} returned 0 rows - stopping")
                        return all_profiles

                    all_profiles.append(df)
                    print(f"    SUCCESS: Got {len(df):,} profiles")

                    success = True

                except requests.exceptions.RequestException as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 5 * retry_count
                        print(f"    Error: {e}. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        print(f"    ERROR after {max_retries} retries: {e}")
                        return all_profiles

            if success:
                part += 1
                # Be nice to API - wait between requests
                if part < 10:
                    time.sleep(2)

        return all_profiles

    def save_profiles(self, profiles):
        """Save combined profiles to CSV"""
        if not profiles:
            print("\nNo profiles to save")
            return None

        combined_df = pd.concat(profiles, ignore_index=True)
        output_file = self.data_dir / 'profiles_bulk.csv'
        combined_df.to_csv(output_file, index=False)

        print(f"\nSUCCESS: Downloaded {len(combined_df):,} company profiles from {len(profiles)} parts")
        print(f"Saved to: {output_file}")

        return combined_df


def main():
    """Download company profile bulk data"""
    print("=" * 80)
    print("FINANCIAL MODELING PREP - BULK COMPANY PROFILES DOWNLOAD")
    print("=" * 80)

    try:
        downloader = FMPBulkDownloader()
        profiles = downloader.download_profile_bulk()
        df = downloader.save_profiles(profiles)

        if df is not None:
            print("\n" + "=" * 80)
            print("DOWNLOAD COMPLETE")
            print("=" * 80)
            print(f"\nTotal profiles: {len(df):,}")
            print(f"Profiles with marketCap > 0: {(df['marketCap'] > 0).sum():,}")
            print("\nThe Streamlit app will now use this data for market cap sorting.")
        else:
            print("\nERROR: No data downloaded")
            sys.exit(1)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
