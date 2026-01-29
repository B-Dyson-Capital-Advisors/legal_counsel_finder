from ftplib import FTP
import pandas as pd
from io import BytesIO

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
        
        # Keep only columns 0-8
        df = df.iloc[:, 0:9]
        
        # Rename columns with clear percentage indicators
        df.columns = ['Symbol', 'Currency', 'Name', 'CON', 'ISIN',
                      'Rebate Rate (%)', 'Fee Rate (%)', 'Available', 'FIGI']
        
        # Drop unnecessary columns
        df = df.drop(columns=['CON', 'ISIN', 'FIGI'])
        
        # Convert numeric columns
        df['Rebate Rate (%)'] = pd.to_numeric(df['Rebate Rate (%)'], errors='coerce')
        df['Fee Rate (%)'] = pd.to_numeric(df['Fee Rate (%)'], errors='coerce')
        df['Available'] = pd.to_numeric(df['Available'], errors='coerce')
        
        # Format rates to 2 decimal places
        df['Rebate Rate (%)'] = df['Rebate Rate (%)'].round(2)
        df['Fee Rate (%)'] = df['Fee Rate (%)'].round(2)
        
        # Format Available with comma separators (keep as numeric for sorting/filtering)
        df['Available'] = df['Available'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
        
        # Add Date and Time columns at the end
        df['Date'] = date
        df['Time'] = time
        
        return df
        
    except Exception as e:
        raise Exception(f"Error fetching stock loan data: {e}")
