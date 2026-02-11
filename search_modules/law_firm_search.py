import pandas as pd
from .utils import search_paginated, extract_ticker_and_clean_name, filter_important_filings


def search_law_firm_for_companies(firm_name, start_date, end_date, progress_callback=None):
    """
    Search for companies represented by a law firm, including most recent lawyer

    Args:
        firm_name: Name of the law firm
        start_date: Start date for search
        end_date: End date for search
        progress_callback: Optional progress callback function

    Returns:
        DataFrame with companies, tickers, market cap, and most recent lawyer
    """

    # First, get the basic company results
    if progress_callback:
        progress_callback(f"Searching for companies represented by {firm_name}...")

    # Get raw filing data instead of processed results
    results, total = search_paginated(firm_name, start_date, end_date, max_total=10000)

    if not results:
        raise ValueError(f"No results found for law firm: {firm_name}")

    df = pd.DataFrame(results)

    if progress_callback:
        progress_callback(f"Total filings found: {len(df)}")

    df_filtered = filter_important_filings(df)

    if progress_callback:
        progress_callback(f"After filtering to relevant filing types: {len(df_filtered)}")

    if df_filtered.empty:
        raise ValueError(f"No relevant filings found for law firm: {firm_name}")

    df_filtered[['clean_company_name', 'ticker']] = df_filtered['company_name'].apply(
        lambda x: pd.Series(extract_ticker_and_clean_name(x))
    )

    df_filtered['filing_date'] = pd.to_datetime(df_filtered['filing_date'])

    # Keep all filings for now (we'll need them for lawyer extraction)
    df_sorted = df_filtered.sort_values('filing_date', ascending=False)

    # Get unique companies with their most recent filing (preserve CIK and accession data)
    df_unique = df_sorted.drop_duplicates(subset=['clean_company_name'], keep='first')

    if progress_callback:
        progress_callback(f"Unique companies: {len(df_unique)}")

    # Now enrich with market cap and stock loan data
    from .stock_reference import filter_and_enrich_tickers
    from .stock_loan import fetch_shortstock_data

    result_df = df_unique[['clean_company_name', 'ticker', 'filing_date']].copy()
    result_df.columns = ['Company', 'Ticker', 'Filing Date']

    result_df = result_df[result_df['Ticker'] != ""].copy()

    # Clean ticker
    result_df['Ticker_Clean'] = result_df['Ticker'].str.replace(' US Equity', '', regex=False).str.strip().str.upper()

    if progress_callback:
        progress_callback(f"Filtering to reference tickers and adding market cap...")

    # Filter by reference tickers and add market cap
    result_df = filter_and_enrich_tickers(result_df, ticker_column='Ticker_Clean')

    if result_df.empty:
        raise ValueError(f"No companies found with tickers in stock reference file")

    if progress_callback:
        progress_callback(f"Adding stock loan availability data...")

    # Fetch stock loan data
    try:
        stock_loan_df = fetch_shortstock_data()
        stock_loan_df['Symbol_Clean'] = stock_loan_df['Symbol'].str.strip().str.upper()

        result_df = result_df.merge(
            stock_loan_df[['Symbol_Clean', 'Rebate Rate (%)', 'Fee Rate (%)', 'Available']],
            left_on='Ticker_Clean',
            right_on='Symbol_Clean',
            how='left'
        )
        result_df = result_df.drop('Symbol_Clean', axis=1)
    except Exception as e:
        if progress_callback:
            progress_callback(f"Note: Could not fetch stock loan data ({str(e)})")

    # Add back " US Equity" suffix for Bloomberg format
    result_df['Ticker'] = result_df['Ticker_Clean'] + ' US Equity'

    # TODO: Lawyer extraction is disabled for now due to unreliability
    # The SEC search finds filings that mention the firm name, but those mentions
    # may not be in the proper format for lawyer extraction
    # Future enhancement: Use a different approach similar to company search (tab 1)

    # Format Filing Date
    result_df['Filing Date'] = pd.to_datetime(result_df['Filing Date']).dt.strftime('%Y-%m-%d')

    # Reorder columns: Company, Ticker, Market Cap, 52wk High/Low, Stock Loan columns, Filing Date
    final_columns = ['Company', 'Ticker', 'Market Cap']

    if '52wk High' in result_df.columns:
        final_columns.append('52wk High')
    if '52wk Low' in result_df.columns:
        final_columns.append('52wk Low')

    if 'Rebate Rate (%)' in result_df.columns:
        final_columns.extend(['Rebate Rate (%)', 'Fee Rate (%)', 'Available'])

    final_columns.append('Filing Date')

    # Drop internal columns (cik, adsh) before final output
    result_df = result_df[final_columns]

    if progress_callback:
        progress_callback(f"Search complete: {len(result_df)} companies")

    return result_df
