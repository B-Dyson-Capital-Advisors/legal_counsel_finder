import pandas as pd
import streamlit as st
from pathlib import Path

@st.cache_data(ttl=3600, show_spinner=False)
def load_stock_reference():
    """Load stock reference file with market cap data"""
    try:
        # Look for the most recent reference file in data folder
        data_dir = Path(__file__).parent.parent / "data"

        if not data_dir.exists():
            return None

        # Find the most recent .xlsx file matching pattern
        reference_files = list(data_dir.glob("stock_loan_reference_*.xlsx"))

        if not reference_files:
            return None

        # Use the most recent file
        reference_file = max(reference_files, key=lambda p: p.stat().st_mtime)

        # Load the Excel file
        df = pd.read_excel(reference_file)

        # Rename columns to standard names
        df.columns = ['Symbol', 'Date', 'Time', 'Security Type', 'Market Cap']

        # Clean up Symbol column (remove whitespace, uppercase)
        df['Symbol'] = df['Symbol'].astype(str).str.strip().str.upper()

        # Convert Market Cap to numeric
        df['Market Cap'] = pd.to_numeric(df['Market Cap'], errors='coerce')

        # Keep only relevant columns
        df = df[['Symbol', 'Security Type', 'Market Cap']]

        # Remove duplicates (keep first occurrence)
        df = df.drop_duplicates(subset=['Symbol'], keep='first')

        return df

    except Exception as e:
        print(f"Error loading stock reference: {e}")
        return None


def filter_and_enrich_tickers(df, ticker_column='Ticker'):
    """
    Filter DataFrame to only include tickers in reference file and add market cap

    Args:
        df: DataFrame with ticker column
        ticker_column: Name of the ticker column (default 'Ticker')

    Returns:
        DataFrame filtered and enriched with market cap
    """
    reference_df = load_stock_reference()

    if reference_df is None:
        # If no reference file, return original df
        return df

    # Clean up ticker column
    df[ticker_column] = df[ticker_column].astype(str).str.strip().str.upper()

    # Merge with reference to filter and add market cap
    enriched_df = df.merge(
        reference_df[['Symbol', 'Market Cap']],
        left_on=ticker_column,
        right_on='Symbol',
        how='inner'  # Only keep tickers in reference file
    )

    # Drop the extra Symbol column
    if 'Symbol' in enriched_df.columns and ticker_column != 'Symbol':
        enriched_df = enriched_df.drop('Symbol', axis=1)

    return enriched_df


def get_reference_tickers():
    """Get set of valid tickers from reference file"""
    reference_df = load_stock_reference()

    if reference_df is None:
        return set()

    return set(reference_df['Symbol'].tolist())
