import re
import time
import requests
import pandas as pd
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from .utils import search_entity_for_companies, search_paginated, extract_ticker_and_clean_name, filter_important_filings, deduplicate_companies
from .company_search import extract_lawyers_by_regex, clean_firm_name

SEC_API_URL = "https://data.sec.gov/submissions/CIK{}.json"
HEADERS = {
    "User-Agent": "B. Dyson Capital Advisors contact@bdysoncapital.com",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}


def get_filing_text_url(cik, accession_number):
    """Construct URL for filing text"""
    # Format CIK with leading zeros (10 digits)
    cik_padded = str(cik).zfill(10)
    # Remove dashes from accession number for URL path
    accession_clean = accession_number.replace('-', '')
    # Construct the URL
    return f"https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik_padded}&accession_number={accession_number}&xbrl_type=v"


def fetch_filing_text(url, max_retries=3):
    """Fetch filing text from SEC with retries"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1 * (attempt + 1))  # Exponential backoff
                continue
            return None
    return None


def extract_most_recent_lawyer(company_name, filing_date, text, firm_name):
    """Extract the most recent lawyer for a company from filing text"""
    if not text:
        return None

    # Use the existing lawyer extraction logic
    try:
        firm_to_lawyers = extract_lawyers_by_regex(text, company_name)

        if not firm_to_lawyers:
            return None

        # First, try to find lawyers associated with this specific firm
        # Normalize firm name for comparison
        firm_normalized = clean_firm_name(firm_name).lower()

        # Remove common suffixes for better matching
        firm_base = re.sub(r'\s+(llp|llc|p\.c\.|p\.a\.)$', '', firm_normalized, flags=re.IGNORECASE).strip()

        for firm, lawyers in firm_to_lawyers.items():
            firm_clean = clean_firm_name(firm).lower()
            firm_clean_base = re.sub(r'\s+(llp|llc|p\.c\.|p\.a\.)$', '', firm_clean, flags=re.IGNORECASE).strip()

            # Check if this is the same firm (fuzzy match)
            if (firm_base in firm_clean_base or
                firm_clean_base in firm_base or
                firm_normalized == firm_clean):
                if lawyers:
                    # Return the first lawyer (alphabetically sorted)
                    sorted_lawyers = sorted(lawyers)
                    return sorted_lawyers[0]

        # If no exact firm match, just return ANY lawyer found
        # (Since we searched for this firm, any lawyer found is likely from this firm)
        for firm, lawyers in firm_to_lawyers.items():
            if lawyers:
                sorted_lawyers = sorted(lawyers)
                return sorted_lawyers[0]

        return None
    except Exception as e:
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

    # Keep CIK and accession data for lawyer extraction
    result_df = df_unique[['clean_company_name', 'ticker', 'filing_date', 'cik', 'adsh']].copy()
    result_df.columns = ['Company', 'Ticker', 'Filing Date', 'cik', 'adsh']

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

    # Now extract lawyers for each company from their most recent filing
    if progress_callback:
        progress_callback(f"Extracting most recent lawyer for each company...")

    # Add Most Recent Lawyer column
    result_df['Most Recent Lawyer'] = None

    # Extract lawyers in parallel (limit to 5 concurrent requests to avoid overwhelming SEC)
    def extract_lawyer_for_company(row):
        """Extract lawyer for a single company"""
        company = row['Company']

        try:
            cik = row.get('cik', '')
            adsh = row.get('adsh', '')

            # Skip if no valid data
            if not cik or not adsh:
                return None

            # Format CIK (remove leading zeros for URL)
            cik_stripped = str(cik).lstrip('0') if cik else ''

            # adsh is already the accession number without dashes
            # Construct accession with dashes: NNNNNNNNNN-NN-NNNNNN
            if len(adsh) == 18:
                accession_with_dashes = f"{adsh[:10]}-{adsh[10:12]}-{adsh[12:]}"
            else:
                accession_with_dashes = adsh

            # Try multiple URL formats
            doc_urls = [
                # Format 1: Standard filing document
                f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{adsh}/{accession_with_dashes}.htm",
                # Format 2: Index page
                f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{adsh}/{accession_with_dashes}-index.htm",
                # Format 3: Alternative format
                f"https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik}&accession_number={accession_with_dashes}&xbrl_type=v",
            ]

            # Try each URL
            from .company_search import extract_counsel_sections
            text = None
            for doc_url in doc_urls:
                try:
                    text = extract_counsel_sections(doc_url)
                    if text and len(text) > 500:  # Valid text
                        break
                except:
                    continue

            if text:
                # Extract lawyer from this filing
                lawyer = extract_most_recent_lawyer(company, row['Filing Date'], text, firm_name)
                return lawyer
        except Exception as e:
            pass

        return None

    # Process companies in parallel (5 workers to respect SEC rate limits)
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(extract_lawyer_for_company, row): idx for idx, row in result_df.iterrows()}

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
            except Exception:
                pass

    # Fill None values with "Not Found"
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
        progress_callback(f"Search complete: {len(result_df)} companies with lawyers")

    return result_df
