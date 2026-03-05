#!/usr/bin/env python3
"""
Process FMP bulk data and create screening-ready datasets
Uses company profiles which already contain price, marketCap, and volume data
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import numpy as np
import sys

class MarketDataProcessor:
    """Process FMP bulk data for screening"""

    def __init__(self):
        self.fmp_dir = Path(__file__).parent.parent / 'data' / 'fmp'
        self.output_dir = Path(__file__).parent.parent / 'data'

        print(f"Input directory: {self.fmp_dir}")
        print(f"Output directory: {self.output_dir}")

    def load_profiles(self):
        """Load company profiles with market data"""
        profiles_file = self.fmp_dir / 'profiles_bulk.csv'
        if not profiles_file.exists():
            raise FileNotFoundError(f"profiles_bulk.csv not found at {profiles_file}")

        print(f"\nLoading company profiles...")
        df = pd.read_csv(profiles_file)
        print(f"  Loaded {len(df):,} profiles")

        # Apply filters: currency=USD, country=US
        initial_count = len(df)
        df = df[
            (df['currency'] == 'USD') &
            (df['country'] == 'US')
        ].copy()
        filtered_count = len(df)
        print(f"  Filtered to USD + US: {filtered_count:,} (removed {initial_count - filtered_count:,})")

        return df

    def load_key_metrics_ttm(self):
        """Load key metrics TTM bulk data"""
        key_metrics_file = self.fmp_dir / 'key_metrics_ttm_bulk.csv'
        if not key_metrics_file.exists():
            print(f"\nWARNING: key_metrics_ttm_bulk.csv not found at {key_metrics_file}")
            return None

        print(f"\nLoading key metrics TTM...")
        df = pd.read_csv(key_metrics_file)
        print(f"  Loaded {len(df):,} key metrics")

        # Filter for enterpriseValueTTM > 100MM
        if 'enterpriseValueTTM' in df.columns:
            df['enterpriseValueTTM'] = pd.to_numeric(df['enterpriseValueTTM'], errors='coerce')
            initial_count = len(df)
            df = df[df['enterpriseValueTTM'] > 100_000_000].copy()
            filtered_count = len(df)
            print(f"  Filtered enterpriseValueTTM > 100MM: {filtered_count:,} (removed {initial_count - filtered_count:,})")
        else:
            print(f"  WARNING: enterpriseValueTTM column not found")

        return df

    def create_stock_reference(self, profiles_df, key_metrics_df=None):
        """
        Create compact stock reference file for the app

        Merges profiles + key metrics, filters to US stocks (NYSE/NASDAQ)
        Keeps only required columns: marketCap, ceo, ipoDate, enterpriseValueTTM
        This file is small enough to commit to git
        """
        print("\n" + "=" * 80)
        print("CREATING STOCK REFERENCE (US STOCKS)")
        print("=" * 80)

        # Start with profiles (already filtered to currency=USD, country=US)
        print(f"\nStarting with {len(profiles_df):,} profiles (USD, US)")

        # Merge with key metrics if available
        if key_metrics_df is not None:
            print(f"Merging with {len(key_metrics_df):,} key metrics...")

            # Keep only enterpriseValueTTM from key metrics
            key_metrics_columns = ['symbol', 'enterpriseValueTTM']
            if 'enterpriseValueTTM' in key_metrics_df.columns:
                merged_df = profiles_df.merge(
                    key_metrics_df[key_metrics_columns],
                    on='symbol',
                    how='inner'  # Only keep stocks with both profile + key metrics
                )
                print(f"  After merge: {len(merged_df):,} stocks (have both profile + key metrics)")
            else:
                print("  WARNING: enterpriseValueTTM not found in key metrics")
                merged_df = profiles_df.copy()
        else:
            print("  Skipping key metrics merge (data not available)")
            merged_df = profiles_df.copy()

        # Filter to US stocks only (NYSE/NASDAQ, no ETF/ADR/fund, actively trading)
        us_stocks = merged_df[
            (merged_df['exchange'].isin(['NYSE', 'NASDAQ'])) &
            (merged_df['isEtf'] == False) &
            (merged_df['isAdr'] == False) &
            (merged_df['isFund'] == False) &
            (merged_df['isActivelyTrading'] == True)
        ].copy()

        print(f"Filtered to {len(us_stocks):,} US stocks (NYSE/NASDAQ, no ETF/ADR/fund)")

        # Keep only required columns
        required_columns = ['symbol', 'companyName', 'exchange', 'marketCap', 'price', 'ceo']
        if 'enterpriseValueTTM' in us_stocks.columns:
            required_columns.append('enterpriseValueTTM')

        # Check which columns exist
        available_columns = [col for col in required_columns if col in us_stocks.columns]
        reference_df = us_stocks[available_columns].copy()

        # Clean data
        reference_df['marketCap'] = pd.to_numeric(reference_df['marketCap'], errors='coerce')
        reference_df = reference_df[reference_df['marketCap'] > 0]
        reference_df = reference_df.dropna(subset=['symbol', 'companyName'])
        reference_df = reference_df.drop_duplicates(subset=['symbol'], keep='first')

        # Sort by market cap descending
        reference_df = reference_df.sort_values('marketCap', ascending=False)

        # Save compact reference file (small enough to commit to git)
        output_file = self.output_dir / 'stock_reference_fmp.csv'
        reference_df.to_csv(output_file, index=False)

        file_size_mb = output_file.stat().st_size / 1e6
        print(f"\n  SUCCESS: {output_file}")
        print(f"  Stocks: {len(reference_df):,}")
        print(f"  Size: {file_size_mb:.1f} MB")
        print(f"  Columns: {', '.join(available_columns)}")

        return reference_df

    def create_screening_dataset(self):
        """
        Create full screening dataset from profiles + key metrics

        This is the complete dataset with all columns and all exchanges.
        Note: This file is large (79 MB) and gitignored - only for local/workflow use.
        """
        print("\n" + "=" * 80)
        print("CREATING FULL SCREENING DATASET")
        print("=" * 80)

        # Load profiles (with USD/US filters)
        profiles_df = self.load_profiles()

        # Load key metrics TTM
        key_metrics_df = self.load_key_metrics_ttm()

        # First create the compact US stock reference (committable to git)
        # This merges profiles + key metrics and filters to NYSE/NASDAQ
        reference_df = self.create_stock_reference(profiles_df, key_metrics_df)

        # Now create full screening dataset (all stocks, all columns)
        print("\n" + "=" * 80)
        print("CREATING FULL SCREENING DATASET (ALL EXCHANGES)")
        print("=" * 80)

        # Map profile columns to screening columns
        column_mapping = {
            'symbol': 'symbol',
            'companyName': 'companyName',
            'sector': 'sector',
            'industry': 'industry',
            'price': 'price',
            'marketCap': 'marketCap',
            'volume': 'volume',
            'change': 'change',
            'changePercentage': 'changePercent',
            'ceo': 'ceo',
            'employees': 'employees',
            'description': 'description',
            'website': 'website',
            'exchange': 'exchange',
            'country': 'country',
            'city': 'city',
            'state': 'state',
            'zip': 'zip',
            'dcfDiff': 'dcfDiff',
            'dcf': 'dcf',
            'image': 'image',
            'defaultImage': 'defaultImage',
            'isEtf': 'isEtf',
            'isActivelyTrading': 'isActivelyTrading',
            'isAdr': 'isAdr',
            'isFund': 'isFund'
        }

        # Select only columns that exist
        available_columns = {k: v for k, v in column_mapping.items() if k in profiles_df.columns}
        screening_df = profiles_df[list(available_columns.keys())].copy()
        screening_df.rename(columns=available_columns, inplace=True)

        # Convert numeric columns
        numeric_columns = ['price', 'marketCap', 'volume', 'change', 'changePercent']
        for col in numeric_columns:
            if col in screening_df.columns:
                screening_df[col] = pd.to_numeric(screening_df[col], errors='coerce')

        # Filter out invalid stocks
        initial_count = len(screening_df)
        screening_df = screening_df[screening_df['symbol'].notna()]
        screening_df = screening_df[screening_df['companyName'].notna()]
        screening_df = screening_df[screening_df['marketCap'] > 0]
        screening_df = screening_df[screening_df['price'] > 0]

        removed_count = initial_count - len(screening_df)
        print(f"\n  Removed {removed_count:,} invalid entries")
        print(f"  Kept {len(screening_df):,} valid stocks")

        # Sort by market cap descending
        screening_df = screening_df.sort_values('marketCap', ascending=False)

        # Save full dataset (gitignored - too large)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        output_file = self.output_dir / f'screening_dataset_{timestamp}.csv'
        screening_df.to_csv(output_file, index=False)

        latest_file = self.output_dir / 'screening_dataset_latest.csv'
        screening_df.to_csv(latest_file, index=False)

        file_size_mb = output_file.stat().st_size / 1e6
        print(f"\n  SUCCESS: {output_file}")
        print(f"  Stocks: {len(screening_df):,}")
        print(f"  Size: {file_size_mb:.1f} MB (gitignored)")
        print(f"  Latest: {latest_file}")

        # Show summary stats
        print(f"\n" + "=" * 80)
        print("DATASET SUMMARY")
        print("=" * 80)
        print(f"Total stocks: {len(screening_df):,}")
        print(f"US stocks (committable): {len(reference_df):,} (0.5 MB)")
        print(f"Avg market cap: ${screening_df['marketCap'].mean():,.0f}")
        print(f"Median market cap: ${screening_df['marketCap'].median():,.0f}")
        print(f"Largest market cap: ${screening_df['marketCap'].max():,.0f} ({screening_df.iloc[0]['symbol']})")

        if 'sector' in screening_df.columns:
            print(f"\nTop sectors:")
            sector_counts = screening_df['sector'].value_counts().head(5)
            for sector, count in sector_counts.items():
                print(f"  {sector}: {count:,}")

        return screening_df


def main():
    """Process FMP bulk data into screening datasets"""
    print("=" * 80)
    print("FMP BULK DATA PROCESSOR")
    print("=" * 80)

    try:
        processor = MarketDataProcessor()
        df = processor.create_screening_dataset()

        print("\n" + "=" * 80)
        print("PROCESSING COMPLETE")
        print("=" * 80)
        print("\nGenerated files:")
        print("  - data/stock_reference_fmp.csv (committable, 0.5 MB)")
        print("  - data/screening_dataset_*.csv (gitignored, large)")

    except FileNotFoundError as e:
        print(f"\nWARNING: {e}")
        print("The profiles bulk data needs to be downloaded first.")
        print("Run: python scripts/download_fmp_bulk.py")
        sys.exit(1)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
