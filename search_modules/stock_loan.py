from ftplib import FTP
import pandas as pd
from io import BytesIO
from .stock_reference import load_stock_reference

def fetch_shortstock_data():
    """Fetch short interest data from Interactive Brokers FTP and return as DataFrame"""
    try:
        # Connect to FTP
        ftp = FTP('ftp2.interactivebrokers.com')
        ftp.login(user='shortstock', passwd='')

        # Download usa.txt to memory (not to disk)
        buffer = BytesIO()
        ftp.retrbinary('RETR usa.txt', buffer.write)
        ftp.quit()

        # Read from buffer into pandas
        buffer.seek(0)
        df = pd.read_csv(buffer,
                         sep='|',
                         header=None,
                         engine='python',
                         names=list(range(15)),
                         skipinitialspace=True,
                         na_values=[''])

        # Extract Date and Time from first row
        date = df.iloc[0, 1]
        time = df.iloc[0, 2]

        # Remove BOF/EOF and header rows
        df = df[~df[0].astype(str).str.contains('#BOF|#EOF|#SYM', na=False)]
        df = df.reset_index(drop=True)

        # Keep only the columns we need: 0 (Symbol), 1 (Currency), 2 (Name), 5 (Rebate), 6 (Fee), 7 (Available)
        # Skip columns 3 (CON), 4 (ISIN/FIGI) - as requested, exclude CON, FIGI, ISIN
        df = df.iloc[:, [0, 1, 2, 5, 6, 7]]

        # Rename columns
        df.columns = ['Symbol', 'Currency', 'Name', 'Rebate Rate (%)', 'Fee Rate (%)', 'Available']

        # Add Date and Time
        df.insert(0, 'Date', date)
        df.insert(1, 'Time', time)

        # Convert numeric columns
        df['Rebate Rate (%)'] = pd.to_numeric(df['Rebate Rate (%)'], errors='coerce')
        df['Fee Rate (%)'] = pd.to_numeric(df['Fee Rate (%)'], errors='coerce')
        df['Available'] = pd.to_numeric(df['Available'], errors='coerce')

        return df

    except Exception as e:
        raise Exception(f"Error fetching stock loan data: {e}")


def fetch_shortstock_with_market_cap():
    """
    NEW FLOW: Start with FMP data, filter US stocks, then join with IB short interest

    1. Load US stock reference (NYSE/NASDAQ only, pre-filtered)
    2. Join with Interactive Brokers FTP short interest data

    Returns: Filtered US stocks with market cap + short interest data
    """
    try:
        # Step 1: Load pre-filtered US stock reference
        us_stocks = load_stock_reference()

        if us_stocks is None:
            # Fallback to old flow if FMP data not available
            stock_loan_df = fetch_shortstock_data()
            return stock_loan_df

        # Step 2: Fetch IB short interest data
        stock_loan_df = fetch_shortstock_data()

        # Clean IB symbols for matching
        stock_loan_df['Symbol_Clean'] = stock_loan_df['Symbol'].str.strip().str.upper()

        # Step 4: Join - only keep US stocks that have short interest data
        enriched_df = us_stocks.merge(
            stock_loan_df,
            left_on='Symbol',
            right_on='Symbol_Clean',
            how='inner',  # Only stocks in both datasets
            suffixes=('_fmp', '_ib')
        )

        # Drop duplicate/temporary columns
        enriched_df = enriched_df.drop(['Symbol_Clean', 'Symbol_ib'], axis=1, errors='ignore')

        # Use FMP company name, drop IB name
        if 'Name' in enriched_df.columns:
            enriched_df = enriched_df.drop('Name', axis=1)

        # Rename Symbol_fmp back to Symbol
        if 'Symbol_fmp' in enriched_df.columns:
            enriched_df = enriched_df.rename(columns={'Symbol_fmp': 'Symbol'})

        # Reorder columns: Date, Time, Symbol, Company, Exchange, Market Cap, CEO, IPO Date, Enterprise Value, Stock Loan Data
        column_order = [
            'Date', 'Time', 'Symbol', 'Company Name', 'Exchange', 'Market Cap',
            'CEO', 'IPO Date', 'Enterprise Value TTM',
            'Sector', 'Industry', 'Currency',
            'Rebate Rate (%)', 'Fee Rate (%)', 'Available'
        ]

        # Only include columns that exist
        column_order = [col for col in column_order if col in enriched_df.columns]
        enriched_df = enriched_df[column_order]

        return enriched_df

    except Exception as e:
        raise Exception(f"Error fetching stock loan data with market cap: {e}")
