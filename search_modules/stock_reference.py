import pandas as pd
import streamlit as st
from pathlib import Path

@st.cache_data(ttl=3600, show_spinner=False)
def load_stock_reference():
    """Load stock reference file with market cap and 52-week high/low data"""
    try:
        # Look for the most recent reference file in data folder
        data_dir = Path(__file__).parent.parent / "data"

        if not data_dir.exists():
            return None

        # Find the most recent .xlsx file matching pattern
        reference_files = list(data_dir.glob("stock_loan_reference_*.xlsx"))

        if not reference_files:
            return None

        # Use the most recent file (by modification time)
        reference_file = max(reference_files, key=lambda p: p.stat().st_mtime)

        # Load the Excel file
        df = pd.read_excel(reference_file)

        # Expected columns: ticker, market cap, 52wk high, 52wk low
        # Rename columns to standard names based on number of columns
        if len(df.columns) == 4:
            # New format: ticker, market cap, 52wk high, 52wk low
            df.columns = ['Symbol', 'Market Cap', '52wk High', '52wk Low']
        elif len(df.columns) == 5:
            # Old format: Symbol, Date, Time, Security Type, Market Cap
            df.columns = ['Symbol', 'Date', 'Time', 'Security Type', 'Market Cap']
            # Keep only relevant columns for backward compatibility
            df = df[['Symbol', 'Market Cap']]
        else:
            # Try to handle automatically
            df.columns = ['Symbol', 'Market Cap', '52wk High', '52wk Low'][:len(df.columns)]

        # Clean up Symbol column (remove whitespace, uppercase)
        df['Symbol'] = df['Symbol'].astype(str).str.strip().str.upper()

        # Convert numeric columns
        df['Market Cap'] = pd.to_numeric(df['Market Cap'], errors='coerce')
        if '52wk High' in df.columns:
            df['52wk High'] = pd.to_numeric(df['52wk High'], errors='coerce')
        if '52wk Low' in df.columns:
            df['52wk Low'] = pd.to_numeric(df['52wk Low'], errors='coerce')

        # Remove duplicates (keep first occurrence)
        df = df.drop_duplicates(subset=['Symbol'], keep='first')

        return df

    except Exception as e:
        print(f"Error loading stock reference: {e}")
        return None


def filter_and_enrich_tickers(df, ticker_column='Ticker'):
    """
    Filter DataFrame to only include tickers in reference file and add market cap, 52wk high/low

    Args:
        df: DataFrame with ticker column
        ticker_column: Name of the ticker column (default 'Ticker')

    Returns:
        DataFrame filtered and enriched with market cap, 52wk high, 52wk low
    """
    reference_df = load_stock_reference()

    if reference_df is None:
        # If no reference file, return original df
        return df

    # Clean up ticker column
    df[ticker_column] = df[ticker_column].astype(str).str.strip().str.upper()

    # Determine which columns to merge (adapt to available columns in reference)
    merge_columns = ['Symbol', 'Market Cap']
    if '52wk High' in reference_df.columns:
        merge_columns.append('52wk High')
    if '52wk Low' in reference_df.columns:
        merge_columns.append('52wk Low')

    # Merge with reference to filter and add market cap + 52wk data
    enriched_df = df.merge(
        reference_df[merge_columns],
        left_on=ticker_column,
        right_on='Symbol',
        how='inner'  # Only keep tickers in reference file
    )

    # Drop the extra Symbol column
    if 'Symbol' in enriched_df.columns and ticker_column != 'Symbol':
        enriched_df = enriched_df.drop('Symbol', axis=1)

    return enriched_df
