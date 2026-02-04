import pandas as pd
import streamlit as st
from .utils import (
    search_paginated,
    filter_important_filings,
    deduplicate_companies,
    extract_ticker_and_clean_name
)
from .stock_reference import filter_and_enrich_tickers
from .stock_loan import fetch_shortstock_data


def search_lawyer_for_companies(lawyer_name, start_date, end_date, progress_callback=None):
    """Search for companies represented by a lawyer"""

    if progress_callback:
        progress_callback(f"Searching lawyer: {lawyer_name}")
        if hasattr(start_date, 'strftime'):
            start_str = start_date.strftime('%Y-%m-%d')
        else:
            start_str = str(start_date)
        if hasattr(end_date, 'strftime'):
            end_str = end_date.strftime('%Y-%m-%d')
        else:
            end_str = str(end_date)
        progress_callback(f"Date range: {start_str} to {end_str}")

    results, total = search_paginated(lawyer_name, start_date, end_date, max_total=10000)

    if not results:
        raise ValueError(f"No results found for lawyer: {lawyer_name}")

    df = pd.DataFrame(results)

    if progress_callback:
        progress_callback(f"Total filings found: {len(df)}")

    df_filtered = filter_important_filings(df)

    if progress_callback:
        progress_callback(f"After filtering to relevant filing types: {len(df_filtered)}")

    if df_filtered.empty:
        raise ValueError(f"No relevant filings found for lawyer: {lawyer_name}")

    df_filtered[['clean_company_name', 'ticker']] = df_filtered['company_name'].apply(
        lambda x: pd.Series(extract_ticker_and_clean_name(x))
    )

    df_filtered['filing_date'] = pd.to_datetime(df_filtered['filing_date'])

    df_unique = deduplicate_companies(df_filtered)

    if progress_callback:
        progress_callback(f"Unique companies: {len(df_unique)}")

    df_unique = df_unique.sort_values('filing_date', ascending=False)

    result_df = df_unique[['clean_company_name', 'ticker', 'filing_date']].copy()
    result_df.columns = ['Company', 'Ticker', 'Filing Date']

    result_df = result_df[result_df['Ticker'] != ""].copy()

    # Clean ticker (remove " US Equity" suffix if present for filtering)
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
        # Clean symbols for matching
        stock_loan_df['Symbol_Clean'] = stock_loan_df['Symbol'].str.strip().str.upper()

        # Merge stock loan data
        result_df = result_df.merge(
            stock_loan_df[['Symbol_Clean', 'Rebate Rate (%)', 'Fee Rate (%)', 'Available']],
            left_on='Ticker_Clean',
            right_on='Symbol_Clean',
            how='left'
        )
        # Drop extra column
        result_df = result_df.drop('Symbol_Clean', axis=1)

    except Exception as e:
        if progress_callback:
            progress_callback(f"Note: Could not fetch stock loan data ({str(e)})")

    # Add back " US Equity" suffix for Bloomberg format
    result_df['Ticker'] = result_df['Ticker_Clean'] + ' US Equity'

    # Drop temporary column
    result_df = result_df.drop('Ticker_Clean', axis=1)

    # Format Filing Date
    result_df['Filing Date'] = pd.to_datetime(result_df['Filing Date']).dt.strftime('%Y-%m-%d')

    # Reorder columns: Company, Ticker, Market Cap, Stock Loan columns, Filing Date
    final_columns = ['Company', 'Ticker', 'Market Cap']
    if 'Rebate Rate (%)' in result_df.columns:
        final_columns.extend(['Rebate Rate (%)', 'Fee Rate (%)', 'Available'])
    final_columns.append('Filing Date')

    result_df = result_df[final_columns]

    if progress_callback:
        progress_callback(f"Search complete: {len(result_df)} companies")

    return result_df
