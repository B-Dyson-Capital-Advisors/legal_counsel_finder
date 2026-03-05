#!/usr/bin/env python3
"""
Process FMP bulk data and create screening-ready datasets
Combines EOD, profiles, and metrics for equity screening
"""

import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np

class MarketDataProcessor:
    """Process and combine FMP bulk data for screening"""

    def __init__(self):
        self.fmp_dir = Path(__file__).parent.parent / 'data' / 'fmp'
        self.output_dir = Path(__file__).parent.parent / 'data'

        print(f"Input directory: {self.fmp_dir}")
        print(f"Output directory: {self.output_dir}")

    def load_latest_eod(self):
        """Load the most recent EOD bulk file"""
        eod_files = sorted(self.fmp_dir.glob('eod_bulk_*.csv'))
        if not eod_files:
            raise FileNotFoundError("No EOD bulk files found")

        latest_file = eod_files[-1]
        print(f"\nLoading EOD data: {latest_file.name}")

        df = pd.read_csv(latest_file)
        print(f"    Loaded {len(df):,} stocks")

        return df

    def load_profiles(self):
        """Load company profiles"""
        profiles_file = self.fmp_dir / 'profiles_bulk.csv'
        if not profiles_file.exists():
            raise FileNotFoundError("profiles_bulk.csv not found")

        print(f"\nLoading company profiles...")
        df = pd.read_csv(profiles_file)
        print(f"    Loaded {len(df):,} profiles")

        return df

    def load_key_metrics(self):
        """Load the most recent key metrics"""
        metrics_files = sorted(self.fmp_dir.glob('key_metrics_*.csv'))
        if not metrics_files:
            print("   WARNING: No key metrics files found (optional)")
            return None

        latest_file = metrics_files[-1]
        print(f"\nLoading key metrics: {latest_file.name}")

        df = pd.read_csv(latest_file)
        print(f"    Loaded {len(df):,} metrics")

        return df

    def create_screening_dataset(self):
        """
        Combine all data sources into a single screening dataset

        Output columns:
        - symbol
        - companyName
        - sector
        - industry
        - price (latest close)
        - marketCap
        - volume
        - change
        - changePercent
        - ceo
        - employees
        - description
        - peRatio, pbRatio, dividendYield (if available)
        """
        print("\n" + "=" * 80)
        print("CREATING SCREENING DATASET")
        print("=" * 80)

        # Load data
        eod_df = self.load_latest_eod()
        profiles_df = self.load_profiles()
        metrics_df = self.load_key_metrics()

        # Merge EOD with Profiles
        print(f"\nMerging datasets...")

        # Start with EOD data (has latest prices)
        screening_df = eod_df[[
            'symbol', 'close', 'volume', 'change', 'changePercent'
        ]].copy()

        screening_df.rename(columns={'close': 'price'}, inplace=True)

        # Merge profiles
        if profiles_df is not None:
            profiles_subset = profiles_df[[
                'symbol', 'companyName', 'sector', 'industry', 'mktCap',
                'ceo', 'fullTimeEmployees', 'description', 'exchange', 'country'
            ]].copy()

            profiles_subset.rename(columns={
                'mktCap': 'marketCap',
                'fullTimeEmployees': 'employees'
            }, inplace=True)

            screening_df = screening_df.merge(
                profiles_subset, on='symbol', how='left'
            )

        # Merge key metrics
        if metrics_df is not None:
            metrics_subset = metrics_df[[
                'symbol', 'peRatio', 'pbRatio', 'dividendYield',
                'enterpriseValue', 'revenuePerShare'
            ]].copy()

            screening_df = screening_df.merge(
                metrics_subset, on='symbol', how='left'
            )

        print(f"    Combined {len(screening_df):,} stocks")

        # Calculate market cap from price * shares if not available
        if 'marketCap' not in screening_df.columns:
            print("   WARNING: marketCap not found, will need to calculate from price")

        # Clean and format
        print(f"\nCleaning data...")

        # Remove stocks with missing critical data
        initial_count = len(screening_df)
        screening_df = screening_df.dropna(subset=['symbol', 'price'])
        removed = initial_count - len(screening_df)
        if removed > 0:
            print(f"   INFO: Removed {removed:,} stocks with missing critical data")

        # Sort by market cap (largest first)
        if 'marketCap' in screening_df.columns:
            screening_df = screening_df.sort_values('marketCap', ascending=False)
            print(f"    Sorted by market cap")

        # Save full dataset
        output_file = self.output_dir / 'screening_data_full.csv'
        screening_df.to_csv(output_file, index=False)
        print(f"\nSaved full dataset: {output_file}")
        print(f"   {len(screening_df):,} stocks")

        # Create filtered datasets
        self.create_filtered_datasets(screening_df)

        return screening_df

    def create_filtered_datasets(self, df):
        """Create pre-filtered datasets for common screening criteria"""
        print(f"\nCreating filtered datasets...")

        if 'marketCap' not in df.columns:
            print("   WARNING: Skipping market cap filters (marketCap column not available)")
            return

        # Filter 1: Large cap (>$10B)
        large_cap = df[df['marketCap'] > 10_000_000_000].copy()
        output_file = self.output_dir / 'screening_data_large_cap.csv'
        large_cap.to_csv(output_file, index=False)
        print(f"    Large cap (>$10B): {len(large_cap):,} stocks -> {output_file.name}")

        # Filter 2: Mid cap ($2B-$10B)
        mid_cap = df[
            (df['marketCap'] >= 2_000_000_000) &
            (df['marketCap'] <= 10_000_000_000)
        ].copy()
        output_file = self.output_dir / 'screening_data_mid_cap.csv'
        mid_cap.to_csv(output_file, index=False)
        print(f"    Mid cap ($2B-$10B): {len(mid_cap):,} stocks -> {output_file.name}")

        # Filter 3: Small cap ($300M-$2B)
        small_cap = df[
            (df['marketCap'] >= 300_000_000) &
            (df['marketCap'] < 2_000_000_000)
        ].copy()
        output_file = self.output_dir / 'screening_data_small_cap.csv'
        small_cap.to_csv(output_file, index=False)
        print(f"    Small cap ($300M-$2B): {len(small_cap):,} stocks -> {output_file.name}")

        # Filter 4: US stocks only (if country available)
        if 'country' in df.columns:
            us_stocks = df[df['country'] == 'US'].copy()
            output_file = self.output_dir / 'screening_data_us_only.csv'
            us_stocks.to_csv(output_file, index=False)
            print(f"    US stocks only: {len(us_stocks):,} stocks -> {output_file.name}")

    def generate_summary_report(self, df):
        """Generate summary statistics"""
        print("\n" + "=" * 80)
        print("SUMMARY STATISTICS")
        print("=" * 80)

        print(f"\nTotal stocks: {len(df):,}")

        if 'marketCap' in df.columns:
            print(f"\nMarket Cap Distribution:")
            print(f"  Average: ${df['marketCap'].mean()/1e9:.2f}B")
            print(f"  Median:  ${df['marketCap'].median()/1e9:.2f}B")
            print(f"  Min:     ${df['marketCap'].min()/1e9:.2f}B")
            print(f"  Max:     ${df['marketCap'].max()/1e9:.2f}B")

        if 'sector' in df.columns:
            print(f"\nTop 5 Sectors:")
            top_sectors = df['sector'].value_counts().head(5)
            for sector, count in top_sectors.items():
                print(f"  {sector}: {count:,} stocks")

        if 'exchange' in df.columns:
            print(f"\nExchanges:")
            exchanges = df['exchange'].value_counts()
            for exchange, count in exchanges.items():
                print(f"  {exchange}: {count:,} stocks")


def main():
    """Main processing pipeline"""
    print("=" * 80)
    print("FMP BULK DATA PROCESSOR")
    print("=" * 80)

    try:
        processor = MarketDataProcessor()
        df = processor.create_screening_dataset()
        processor.generate_summary_report(df)

        print("\n" + "=" * 80)
        print(" PROCESSING COMPLETE!")
        print("=" * 80)
        print("\nOutput files in data/ directory:")
        print("   - screening_data_full.csv (all stocks)")
        print("   - screening_data_large_cap.csv (>$10B)")
        print("   - screening_data_mid_cap.csv ($2B-$10B)")
        print("   - screening_data_small_cap.csv ($300M-$2B)")
        print("   - screening_data_us_only.csv (US only)")

    except FileNotFoundError as e:
        error_msg = str(e)
        if "EOD bulk files" in error_msg:
            print(f"\nWARNING: {e}")
            print("\nINFO: EOD files are optional for screening datasets.")
            print("   The app only needs profiles_bulk.csv (already downloaded).")
            print("\nSkipping screening dataset creation - not required for app.")
            return  # Exit gracefully
        else:
            print(f"\n Error: {e}")
            raise
    except Exception as e:
        print(f"\n Error: {e}")
        raise


if __name__ == "__main__":
    main()
