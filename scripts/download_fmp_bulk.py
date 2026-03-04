#!/usr/bin/env python3
"""
Download bulk data from Financial Modeling Prep API
Supports: EOD prices, company profiles, financials, ratios, key metrics
"""

import os
import sys
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import time

# Load .env file if exists (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, will use environment variables directly

class FMPBulkDownloader:
    """Download bulk data from Financial Modeling Prep API"""

    BASE_URL = "https://financialmodelingprep.com/api"

    def __init__(self, api_key=None):
        """Initialize with API key from environment or parameter"""
        self.api_key = api_key or os.getenv('FMP_API_KEY')
        if not self.api_key:
            raise ValueError("FMP_API_KEY not found in environment variables")

        # Create data directories
        self.data_dir = Path(__file__).parent.parent / 'data' / 'fmp'
        self.data_dir.mkdir(parents=True, exist_ok=True)

        print(f"📁 Data directory: {self.data_dir}")

    def download_eod_bulk(self, date=None):
        """
        Download bulk EOD prices for all stocks
        Rate limit: Once every 10 seconds

        Returns CSV with: symbol, date, open, high, low, close, adjClose, volume,
                         change, changePercent, vwap
        """
        if date is None:
            # Default to yesterday (market data available after close)
            date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        print(f"\n📊 Downloading EOD bulk data for {date}...")

        url = f"{self.BASE_URL}/v4/batch-request-end-of-day-prices"
        params = {
            'date': date,
            'apikey': self.api_key
        }

        response = requests.get(url, params=params, timeout=120)
        response.raise_for_status()

        # Save raw CSV
        output_file = self.data_dir / f'eod_bulk_{date}.csv'
        output_file.write_text(response.text)

        # Load and display summary
        df = pd.read_csv(output_file)
        print(f"   ✅ Downloaded {len(df):,} stocks")
        print(f"   💾 Saved to: {output_file}")

        return df

    def download_profile_bulk(self):
        """
        Download bulk company profiles
        Rate limit: Once every 60 seconds

        Returns: symbol, companyName, sector, industry, marketCap, ceo,
                description, employees, etc.
        """
        print(f"\n🏢 Downloading company profiles bulk...")

        url = f"{self.BASE_URL}/v4/profile/all"
        params = {'apikey': self.api_key}

        response = requests.get(url, params=params, timeout=120)
        response.raise_for_status()

        data = response.json()
        df = pd.DataFrame(data)

        # Save as CSV
        output_file = self.data_dir / 'profiles_bulk.csv'
        df.to_csv(output_file, index=False)

        print(f"   ✅ Downloaded {len(df):,} company profiles")
        print(f"   💾 Saved to: {output_file}")

        return df

    def download_financial_ratios_bulk(self, year=None, period='annual'):
        """
        Download bulk financial ratios
        Rate limit: Once every 10 seconds

        Args:
            year: Year (default: current year)
            period: 'annual' or 'quarter'
        """
        if year is None:
            year = datetime.now().year

        print(f"\n📈 Downloading financial ratios bulk ({period} {year})...")

        url = f"{self.BASE_URL}/v4/ratios"
        params = {
            'year': year,
            'period': period,
            'apikey': self.api_key
        }

        response = requests.get(url, params=params, timeout=120)
        response.raise_for_status()

        data = response.json()
        df = pd.DataFrame(data)

        # Save as CSV
        output_file = self.data_dir / f'ratios_{period}_{year}.csv'
        df.to_csv(output_file, index=False)

        print(f"   ✅ Downloaded {len(df):,} company ratios")
        print(f"   💾 Saved to: {output_file}")

        return df

    def download_key_metrics_bulk(self, year=None, period='annual'):
        """
        Download bulk key metrics
        Rate limit: Once every 10 seconds

        Returns: marketCap, enterpriseValue, peRatio, pbRatio, dividendYield, etc.
        """
        if year is None:
            year = datetime.now().year

        print(f"\n📊 Downloading key metrics bulk ({period} {year})...")

        url = f"{self.BASE_URL}/v4/key-metrics"
        params = {
            'year': year,
            'period': period,
            'apikey': self.api_key
        }

        response = requests.get(url, params=params, timeout=120)
        response.raise_for_status()

        data = response.json()
        df = pd.DataFrame(data)

        # Save as CSV
        output_file = self.data_dir / f'key_metrics_{period}_{year}.csv'
        df.to_csv(output_file, index=False)

        print(f"   ✅ Downloaded {len(df):,} company metrics")
        print(f"   💾 Saved to: {output_file}")

        return df

    def download_income_statement_bulk(self, year=None, period='annual'):
        """
        Download bulk income statements
        Rate limit: Once every 10 seconds
        """
        if year is None:
            year = datetime.now().year

        print(f"\n💰 Downloading income statements bulk ({period} {year})...")

        url = f"{self.BASE_URL}/v4/income-statement"
        params = {
            'year': year,
            'period': period,
            'apikey': self.api_key
        }

        response = requests.get(url, params=params, timeout=120)
        response.raise_for_status()

        data = response.json()
        df = pd.DataFrame(data)

        # Save as CSV
        output_file = self.data_dir / f'income_statement_{period}_{year}.csv'
        df.to_csv(output_file, index=False)

        print(f"   ✅ Downloaded {len(df):,} income statements")
        print(f"   💾 Saved to: {output_file}")

        return df


def main():
    """Download all bulk data with proper rate limiting"""
    print("=" * 80)
    print("FINANCIAL MODELING PREP - BULK DATA DOWNLOADER")
    print("=" * 80)

    try:
        downloader = FMPBulkDownloader()

        # 1. Download EOD data (most important for market cap)
        downloader.download_eod_bulk()
        print("\n⏳ Waiting 10 seconds (rate limit)...")
        time.sleep(10)

        # 2. Download company profiles (fundamentals)
        downloader.download_profile_bulk()
        print("\n⏳ Waiting 60 seconds (rate limit for profiles)...")
        time.sleep(60)

        # 3. Download key metrics (includes market cap, P/E, etc.)
        downloader.download_key_metrics_bulk()
        print("\n⏳ Waiting 10 seconds (rate limit)...")
        time.sleep(10)

        # 4. Download financial ratios
        downloader.download_financial_ratios_bulk()
        print("\n⏳ Waiting 10 seconds (rate limit)...")
        time.sleep(10)

        # 5. Download income statements
        downloader.download_income_statement_bulk()

        print("\n" + "=" * 80)
        print("✅ ALL BULK DATA DOWNLOADED SUCCESSFULLY!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
