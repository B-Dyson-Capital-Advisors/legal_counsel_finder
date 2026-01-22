import pandas as pd
from .utils import (
    search_paginated,
    determine_optimal_date_range,
    filter_important_filings,
    deduplicate_companies,
    extract_ticker_and_clean_name
)


def search_law_firm_for_companies(firm_name, progress_callback=None):
    """Search for companies represented by a law firm"""

    if progress_callback:
        progress_callback(f"Searching law firm: {firm_name}")

    start_date, end_date, date_range_desc = determine_optimal_date_range(firm_name, progress_callback)

    if progress_callback:
        progress_callback(f"Final search: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({date_range_desc})")

    results, total = search_paginated(firm_name, start_date, end_date, max_total=1000)

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

    df_unique = deduplicate_companies(df_filtered)

    if progress_callback:
        progress_callback(f"Unique companies: {len(df_unique)}")

    df_unique = df_unique.sort_values('filing_date', ascending=False)

    result_df = df_unique[['clean_company_name', 'ticker', 'filing_date']].copy()
    result_df.columns = ['Company', 'Ticker', 'Filing Date']

    result_df = result_df[result_df['Ticker'] != ""].copy()

    result_df['Ticker'] = result_df['Ticker'].apply(lambda x: f"{x} US Equity")

    result_df['Filing Date'] = result_df['Filing Date'].dt.strftime('%Y-%m-%d')

    if progress_callback:
        progress_callback(f"Search complete: {len(result_df)} companies with tickers")

    return result_df
