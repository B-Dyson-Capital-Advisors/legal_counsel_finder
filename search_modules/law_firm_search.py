import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from .utils import search_paginated, extract_ticker_and_clean_name, filter_important_filings


def find_lawyer_for_company_from_firm(company_info, firm_name, api_key, start_date, end_date):
    """
    Find which lawyer from a specific firm represented a company

    Args:
        company_info: Dict with 'ticker', 'cik', 'company_name'
        firm_name: Law firm name to filter for
        api_key: OpenAI API key
        start_date: Start date for search
        end_date: End date for search

    Returns:
        Lawyer name or "None found"
    """
    try:
        from .company_search import search_company_for_lawyers, normalize_firm_name

        ticker = company_info.get('ticker')
        cik = company_info.get('cik')
        company_name = company_info.get('company_name')

        if not ticker or not cik:
            return "None found"

        # Search for all lawyers for this company
        lawyers_df = search_company_for_lawyers(
            company_identifier=ticker,
            start_date=start_date,
            end_date=end_date,
            api_key=api_key,
            progress_callback=None,
            cik=cik,
            company_name=company_name
        )

        if lawyers_df.empty:
            return "None found"

        # Normalize firm names for comparison
        normalized_target_firm = normalize_firm_name(firm_name).lower()

        # Filter to only lawyers from the specified firm
        firm_lawyers = []
        for _, row in lawyers_df.iterrows():
            row_firm = normalize_firm_name(row['Law Firm']).lower()

            # Fuzzy match - check if target firm is in row firm or vice versa
            if normalized_target_firm in row_firm or row_firm in normalized_target_firm:
                lawyer = row['Lawyer']
                if lawyer and lawyer != '(Firm only - no lawyer name listed)':
                    firm_lawyers.append(lawyer)

        if firm_lawyers:
            # Return first lawyer found (most recent from the search)
            return firm_lawyers[0]
        else:
            return "None found"

    except Exception as e:
        # Don't fail the whole search if one company fails
        return "None found"


def search_law_firm_for_companies(firm_name, start_date, end_date, progress_callback=None, include_lawyers=False, api_key=None):
    """
    Search for companies represented by a law firm.

    Args:
        firm_name: Name of the law firm
        start_date: Start date for search
        end_date: End date for search
        progress_callback: Optional progress callback function
        include_lawyers: If True, add a "Lawyer" column with representing lawyer names (SLOW)
        api_key: OpenAI API key (required if include_lawyers=True)

    Returns:
        DataFrame with companies, tickers, market cap, stock loan data, and optionally lawyer names
    """

    if progress_callback:
        progress_callback(f"Searching for companies represented by {firm_name}...")

    # Get raw filing data
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

    # Get unique companies (most recent filing)
    df_sorted = df_filtered.sort_values('filing_date', ascending=False)
    df_unique = df_sorted.drop_duplicates(subset=['clean_company_name'], keep='first')

    if progress_callback:
        progress_callback(f"Unique companies: {len(df_unique)}")

    # Store CIK for lawyer lookup
    df_unique['cik_stored'] = df_unique['cik']

    # Create result dataframe
    result_df = df_unique[['clean_company_name', 'ticker', 'filing_date', 'cik_stored']].copy()
    result_df.columns = ['Company', 'Ticker', 'Filing Date', 'CIK']

    result_df = result_df[result_df['Ticker'] != ""].copy()

    # Clean ticker
    result_df['Ticker_Clean'] = result_df['Ticker'].str.replace(' US Equity', '', regex=False).str.strip().str.upper()

    if progress_callback:
        progress_callback(f"Filtering to reference tickers and adding market cap...")

    # Filter by reference tickers and add market cap
    from .stock_reference import filter_and_enrich_tickers
    result_df = filter_and_enrich_tickers(result_df, ticker_column='Ticker_Clean')

    if result_df.empty:
        raise ValueError(f"No companies found with tickers in stock reference file")

    # Filter for companies with market cap > $500M
    if 'Market Cap' in result_df.columns:
        initial_count = len(result_df)
        result_df = result_df[result_df['Market Cap'] > 500000000].copy()
        if progress_callback:
            progress_callback(f"Filtered to {len(result_df)} companies with market cap > $500M (from {initial_count})")

    if result_df.empty:
        raise ValueError(f"No companies found with market cap above $500M")

    if progress_callback:
        progress_callback(f"Adding stock loan availability data...")

    # Fetch stock loan data
    try:
        from .stock_loan import fetch_shortstock_data
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

    # Add lawyer names if requested (SLOW - processes each company)
    if include_lawyers and api_key:
        if progress_callback:
            progress_callback(f"Finding lawyers for each company (this may take a few minutes)...")

        # Prepare company info for parallel processing
        companies_info = []
        for _, row in result_df.iterrows():
            companies_info.append({
                'ticker': row['Ticker_Clean'],
                'cik': row['CIK'],
                'company_name': row['Company']
            })

        # Process companies in parallel (3 at a time to not overwhelm)
        lawyers = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_company = {
                executor.submit(
                    find_lawyer_for_company_from_firm,
                    company_info,
                    firm_name,
                    api_key,
                    start_date,
                    end_date
                ): company_info
                for company_info in companies_info
            }

            completed = 0
            for future in as_completed(future_to_company):
                completed += 1
                if progress_callback and completed % 5 == 0:
                    progress_callback(f"Progress: {completed}/{len(companies_info)} companies processed...")

                try:
                    lawyer_name = future.result()
                    lawyers.append(lawyer_name)
                except Exception:
                    lawyers.append("None found")

        result_df['Lawyer'] = lawyers

        if progress_callback:
            found_count = sum(1 for l in lawyers if l != "None found")
            progress_callback(f"Found lawyers for {found_count}/{len(lawyers)} companies")

    # Add back " US Equity" suffix for Bloomberg format
    result_df['Ticker'] = result_df['Ticker_Clean'] + ' US Equity'

    # Drop temporary columns
    result_df = result_df.drop(['Ticker_Clean', 'CIK'], axis=1, errors='ignore')

    # Format Filing Date
    result_df['Filing Date'] = pd.to_datetime(result_df['Filing Date']).dt.strftime('%Y-%m-%d')

    # Final columns: Company, Ticker, Exchange, Market Cap, CEO, IPO Date, Enterprise Value, Lawyer (if included), Stock Loan, Filing Date
    final_columns = ['Company', 'Ticker']

    # Add FMP enrichment columns in the right order
    if 'Exchange' in result_df.columns:
        final_columns.append('Exchange')

    final_columns.append('Market Cap')

    # Add new FMP columns
    if 'CEO' in result_df.columns:
        final_columns.append('CEO')
    if 'IPO Date' in result_df.columns:
        final_columns.append('IPO Date')
    if 'Enterprise Value TTM' in result_df.columns:
        final_columns.append('Enterprise Value TTM')

    # Add Lawyer column if included
    if 'Lawyer' in result_df.columns:
        final_columns.append('Lawyer')

    if '52wk High' in result_df.columns:
        final_columns.append('52wk High')
    if '52wk Low' in result_df.columns:
        final_columns.append('52wk Low')

    if 'Rebate Rate (%)' in result_df.columns:
        final_columns.extend(['Rebate Rate (%)', 'Fee Rate (%)', 'Available'])

    final_columns.append('Filing Date')

    # Only include columns that exist
    final_columns = [col for col in final_columns if col in result_df.columns]
    result_df = result_df[final_columns]

    if progress_callback:
        progress_callback(f"Search complete: {len(result_df)} companies")

    return result_df
