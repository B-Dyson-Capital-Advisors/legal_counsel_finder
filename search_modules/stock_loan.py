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
    Fetch stock loan data and merge with reference file to add market cap
    Only returns stocks that appear in the reference file
    """
    try:
        # Fetch stock loan data
        stock_loan_df = fetch_shortstock_data()

        # Load reference data
        reference_df = load_stock_reference()

        if reference_df is None:
            # If no reference file, return stock loan data as-is
            return stock_loan_df

        # Clean symbols for matching
        stock_loan_df['Symbol_Clean'] = stock_loan_df['Symbol'].str.strip().str.upper()

        # Filter to only include stocks in reference file and add market cap
        enriched_df = stock_loan_df.merge(
            reference_df[['Symbol', 'Market Cap']],
            left_on='Symbol_Clean',
            right_on='Symbol',
            how='inner',  # Only keep stocks in reference file
            suffixes=('', '_ref')
        )

        # Drop temporary/duplicate columns
        enriched_df = enriched_df.drop(['Symbol_Clean', 'Symbol_ref'], axis=1, errors='ignore')

        # Reorder columns: Date, Time, Symbol, Currency, Name, Market Cap, Stock Loan Data
        column_order = ['Date', 'Time', 'Symbol', 'Currency', 'Name', 'Market Cap',
                       'Rebate Rate (%)', 'Fee Rate (%)', 'Available']
        enriched_df = enriched_df[column_order]

        return enriched_df

    except Exception as e:
        raise Exception(f"Error fetching stock loan data with market cap: {e}")
