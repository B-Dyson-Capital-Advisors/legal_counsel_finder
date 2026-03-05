import pandas as pd
import streamlit as st
from pathlib import Path

@st.cache_data(ttl=3600, show_spinner=False)
def load_stock_reference():
    """
    Load US stock reference (NYSE/NASDAQ only) with market cap from FMP data

    Loads from compact stock_reference_fmp.csv (0.5 MB, committed to git)
    Pre-filtered to US stocks only:
    - Exchange: NYSE or NASDAQ only
    - No ETFs, ADRs, or funds
    - Actively trading only
    """
    try:
        # First try to load from compact FMP reference file (committed to git)
        fmp_reference = Path(__file__).parent.parent / "data" / "stock_reference_fmp.csv"

        if fmp_reference.exists():
            # Load pre-filtered, compact reference (US stocks, NYSE/NASDAQ)
            df = pd.read_csv(fmp_reference)

            # Standardize column names (handle both old and new formats)
            # New format: symbol, companyName, exchange, marketCap, price, ceo, enterpriseValueTTM
            # Old format: symbol, companyName, exchange, marketCap, sector, industry
            column_renames = {
                'symbol': 'Symbol',
                'companyName': 'Company Name',
                'exchange': 'Exchange',
                'marketCap': 'Market Cap',
                'price': 'Price',
                'sector': 'Sector',
                'industry': 'Industry',
                'ceo': 'CEO',
                'enterpriseValueTTM': 'Enterprise Value TTM'
            }

            # Only rename columns that exist
            existing_renames = {k: v for k, v in column_renames.items() if k in df.columns}
            df = df.rename(columns=existing_renames)

            # Clean up Symbol column
            df['Symbol'] = df['Symbol'].astype(str).str.strip().str.upper()

            # Convert numeric columns
            if 'Market Cap' in df.columns:
                df['Market Cap'] = pd.to_numeric(df['Market Cap'], errors='coerce')
                # Remove rows with missing or zero market cap
                df = df[df['Market Cap'] > 0]

            if 'Enterprise Value TTM' in df.columns:
                df['Enterprise Value TTM'] = pd.to_numeric(df['Enterprise Value TTM'], errors='coerce')

            # Remove duplicates (keep first occurrence)
            df = df.drop_duplicates(subset=['Symbol'], keep='first')

            return df

        # Fallback to old Excel file format if FMP data not available
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
    Filter DataFrame to only US tickers (NYSE/NASDAQ) and add company info

    Args:
        df: DataFrame with ticker column
        ticker_column: Name of the ticker column (default 'Ticker')

    Returns:
        DataFrame filtered and enriched with:
        - Market Cap
        - Company Name
        - Exchange
        - Sector
        - Industry
    """
    reference_df = load_stock_reference()

    if reference_df is None:
        # If no reference file, return original df
        return df

    # Clean up ticker column
    df[ticker_column] = df[ticker_column].astype(str).str.strip().str.upper()

    # Determine which columns to merge (all available FMP columns)
    merge_columns = ['Symbol', 'Market Cap']

    # Add all available FMP columns
    if 'Company Name' in reference_df.columns:
        merge_columns.append('Company Name')
    if 'Exchange' in reference_df.columns:
        merge_columns.append('Exchange')
    if 'Price' in reference_df.columns:
        merge_columns.append('Price')
    if 'Sector' in reference_df.columns:
        merge_columns.append('Sector')
    if 'Industry' in reference_df.columns:
        merge_columns.append('Industry')
    if 'CEO' in reference_df.columns:
        merge_columns.append('CEO')
    if 'Enterprise Value TTM' in reference_df.columns:
        merge_columns.append('Enterprise Value TTM')

    # Legacy 52wk columns (if available)
    if '52wk High' in reference_df.columns:
        merge_columns.append('52wk High')
    if '52wk Low' in reference_df.columns:
        merge_columns.append('52wk Low')

    # Merge with reference to filter and add FMP data
    enriched_df = df.merge(
        reference_df[merge_columns],
        left_on=ticker_column,
        right_on='Symbol',
        how='inner'  # Only keep US tickers (NYSE/NASDAQ)
    )

    # Drop the extra Symbol column
    if 'Symbol' in enriched_df.columns and ticker_column != 'Symbol':
        enriched_df = enriched_df.drop('Symbol', axis=1)

    return enriched_df
