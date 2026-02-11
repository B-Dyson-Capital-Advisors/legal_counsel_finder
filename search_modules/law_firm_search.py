import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from .utils import search_paginated, extract_ticker_and_clean_name, filter_important_filings
from .company_search import get_company_filings, process_single_filing, clean_firm_name
import re


def get_most_recent_lawyer_from_filing(cik, company_name, firm_name, adsh):
    """
    Extract lawyer from a specific filing (much faster - only 1 filing fetch).

    Args:
        cik: Company CIK
        company_name: Company name
        firm_name: Law firm to search for
        adsh: Accession number of the filing (from search results)

    Returns:
        Lawyer name from that firm, or None
    """
    try:
        # Construct filing URL from adsh
        if len(adsh) == 18:
            accession_with_dashes = f"{adsh[:10]}-{adsh[10:12]}-{adsh[12:]}"
        else:
            accession_with_dashes = adsh

        cik_stripped = str(cik).lstrip('0')
        adsh_clean = adsh.replace('-', '')

        # Try different URL formats
        doc_urls = [
            f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{adsh_clean}/{accession_with_dashes}.htm",
            f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{adsh_clean}/{accession_with_dashes}-index.htm",
        ]

        # Extract text from filing
        from .company_search import extract_counsel_sections, extract_lawyers_by_regex

        text = None
        for doc_url in doc_urls:
            try:
                text = extract_counsel_sections(doc_url)
                if text and len(text) > 500:
                    break
            except:
                continue

        if not text:
            return None

        # Extract lawyers using regex
        firm_to_lawyers = extract_lawyers_by_regex(text, company_name)

        if not firm_to_lawyers:
            return None

        # Find lawyers from the specific firm
        firm_normalized = clean_firm_name(firm_name).lower()
        firm_base = re.sub(r'\s+(llp|llc|p\.c\.|p\.a\.)$', '', firm_normalized, flags=re.IGNORECASE).strip()

        for firm, lawyers in firm_to_lawyers.items():
            firm_clean = clean_firm_name(firm).lower()
            firm_clean_base = re.sub(r'\s+(llp|llc|p\.c\.|p\.a\.)$', '', firm_clean, flags=re.IGNORECASE).strip()

            # Fuzzy match
            if (firm_base in firm_clean_base or
                firm_clean_base in firm_base or
                firm_normalized == firm_clean):
                if lawyers:
                    return sorted(lawyers)[0]

        return None

    except Exception:
        return None


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

    # Extract most recent lawyer for ALL companies
    if progress_callback:
        progress_callback(f"Extracting lawyers for all companies...")

    # Build company filing data mapping from df_unique (includes CIK and adsh)
    company_filing_map = {}
    for _, row in df_unique.iterrows():
        company = row['clean_company_name']
        cik = row.get('cik', '')
        adsh = row.get('adsh', '')
        if company and cik and adsh:
            company_filing_map[company] = {
                'cik': str(cik).zfill(10),
                'adsh': adsh
            }

    # Add Most Recent Lawyer column
    result_df['Most Recent Lawyer'] = None

    # Extract lawyers in parallel (15 workers for speed)
    def extract_lawyer_for_row(row):
        """Extract lawyer from the filing we already found"""
        company = row['Company']
        filing_data = company_filing_map.get(company)

        if not filing_data:
            return None

        # Use the filing we already found from the search (much faster!)
        lawyer = get_most_recent_lawyer_from_filing(
            filing_data['cik'],
            company,
            firm_name,
            filing_data['adsh']
        )
        return lawyer

    # Process ALL companies in parallel
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(extract_lawyer_for_row, row): idx
                   for idx, row in result_df.iterrows()}

        completed = 0
        for future in as_completed(futures):
            completed += 1
            if progress_callback and completed % 10 == 0:
                progress_callback(f"Lawyer extraction: {completed}/{len(result_df)} companies...")

            try:
                idx = futures[future]
                lawyer = future.result()
                if lawyer:
                    result_df.at[idx, 'Most Recent Lawyer'] = lawyer
            except:
                pass

    # Fill None with "Not Found" for all companies
    result_df['Most Recent Lawyer'] = result_df['Most Recent Lawyer'].fillna('Not Found')

    # Format Filing Date
    result_df['Filing Date'] = pd.to_datetime(result_df['Filing Date']).dt.strftime('%Y-%m-%d')

    # Reorder columns: Company, Ticker, Most Recent Lawyer, Market Cap, 52wk High/Low, Stock Loan columns, Filing Date
    final_columns = ['Company', 'Ticker', 'Most Recent Lawyer', 'Market Cap']

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
