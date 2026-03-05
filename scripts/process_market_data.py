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

        return df

    def create_stock_reference(self, profiles_df):
        """
        Create compact stock reference file for the app

        Filters to US stocks only (NYSE/NASDAQ) and keeps only essential columns
        This file is small enough to commit to git (~0.5 MB vs 91 MB profiles)
        """
        print("\n" + "=" * 80)
        print("CREATING STOCK REFERENCE (US STOCKS)")
        print("=" * 80)

        # Filter to US stocks only (same logic as app)
        us_stocks = profiles_df[
            (profiles_df['exchange'].isin(['NYSE', 'NASDAQ'])) &
            (profiles_df['isEtf'] == False) &
            (profiles_df['isAdr'] == False) &
            (profiles_df['isFund'] == False) &
            (profiles_df['isActivelyTrading'] == True)
        ].copy()

        print(f"\nFiltered to {len(us_stocks):,} US stocks (NYSE/NASDAQ)")

        # Keep only essential columns
        essential_columns = ['symbol', 'companyName', 'exchange', 'marketCap', 'sector', 'industry']
        reference_df = us_stocks[essential_columns].copy()

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
        print(f"  Columns: {', '.join(essential_columns)}")

        return reference_df

    def create_screening_dataset(self):
        """
        Create full screening dataset from profiles

        This is the complete dataset with all columns and all exchanges.
        Note: This file is large (79 MB) and gitignored - only for local/workflow use.
        """
        print("\n" + "=" * 80)
        print("CREATING FULL SCREENING DATASET")
        print("=" * 80)

        # Load profiles (has everything we need)
        profiles_df = self.load_profiles()

        # First create the compact US stock reference (committable to git)
        reference_df = self.create_stock_reference(profiles_df)

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
            'ipoDate': 'ipoDate',
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
