import re
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from .filing_types import RELEVANT_FILINGS

SEC_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"

HEADERS = {
    "User-Agent": "B. Dyson Capital Advisors contact@bdysoncapital.com",
    "Accept-Encoding": "gzip, deflate",
    "Host": "efts.sec.gov"
}

TARGET_COMPANIES = 100


def extract_ticker_and_clean_name(company_name):
    """Extract ticker from company name"""
    name_without_cik = re.sub(r'\s*\(CIK\s+\d+\)', '', company_name)
    ticker_match = re.search(r'\(([A-Z0-9\-]+)', name_without_cik)
    ticker = ticker_match.group(1) if ticker_match else ""
    clean_name = re.split(r'\s*\(', name_without_cik)[0].strip()
    return clean_name, ticker


def search_edgar(search_term, from_date, to_date, start_index=0, max_results=100):
    """Search SEC EDGAR"""
    results = []
    from_str = from_date.strftime("%Y-%m-%d")
    to_str = to_date.strftime("%Y-%m-%d")

    params = {
        "q": f'"{search_term}"',
        "dateRange": "custom",
        "startdt": from_str,
        "enddt": to_str,
        "from": start_index,
        "size": min(max_results, 100)
    }

    try:
        response = requests.get(SEC_SEARCH_URL, params=params, headers=HEADERS)
        response.raise_for_status()
        data = response.json()

        if "hits" in data and "hits" in data["hits"]:
            total_hits = data["hits"]["total"]["value"]

            for hit in data["hits"]["hits"]:
                source = hit.get("_source", {})
                filing_info = {
                    "search_term": search_term,
                    "company_name": source.get("display_names", ["Unknown"])[0] if source.get("display_names") else "Unknown",
                    "filing_type": source.get("file_type", ""),
                    "filing_date": source.get("file_date", ""),
                }
                results.append(filing_info)

            return results, total_hits

    except requests.exceptions.RequestException as e:
        raise Exception(f"Error searching SEC EDGAR: {e}")

    time.sleep(0.15)
    return results, 0


def search_paginated(search_term, from_date, to_date, max_total=500):
    """Search with pagination, stopping when no new companies are found"""
    all_results = []
    start_index = 0
    page_size = 100
    seen_companies = set()
    pages_without_new_companies = 0
    max_stale_pages = 3  # Stop after 3 consecutive pages with no new companies

    while len(all_results) < max_total:
        results, total = search_edgar(search_term, from_date, to_date, start_index, page_size)
        if not results:
            break

        # Track new companies in this page
        new_companies_this_page = 0
        for result in results:
            company_name = result.get('company_name', '')
            # Extract clean company name for tracking
            clean_name = re.sub(r'\s*\(CIK\s+\d+\)', '', company_name)
            clean_name = re.split(r'\s*\(', clean_name)[0].strip()

            if clean_name and clean_name not in seen_companies:
                seen_companies.add(clean_name)
                new_companies_this_page += 1

        all_results.extend(results)
        start_index += page_size

        # Stop if we've reached the total available
        if len(all_results) >= total:
            break

        # Check if we're still finding new companies
        if new_companies_this_page == 0:
            pages_without_new_companies += 1
            if pages_without_new_companies >= max_stale_pages:
                # Stop early - we're not finding new companies anymore
                break
        else:
            pages_without_new_companies = 0

    return all_results, total


def count_unique_companies(search_term, from_date, to_date):
    """Count unique companies in a date range"""
    results, _ = search_paginated(search_term, from_date, to_date, max_total=500)

    if not results:
        return 0

    df = pd.DataFrame(results)
    df_filtered = df[df["filing_type"].isin(RELEVANT_FILINGS)].copy()

    df_filtered[['clean_company_name', 'ticker']] = df_filtered['company_name'].apply(
        lambda x: pd.Series(extract_ticker_and_clean_name(x))
    )

    unique_with_tickers = df_filtered[df_filtered['ticker'] != '']['clean_company_name'].nunique()
    return unique_with_tickers


def determine_optimal_date_range(search_term, progress_callback=None):
    """Adaptive date range to keep results under 100 companies (parallelized)"""
    end_date = datetime.now()

    if progress_callback:
        progress_callback(f"Testing volume for '{search_term}'...")

    # Run both 2-year and 4-year tests in parallel
    test_2yr = end_date - timedelta(days=730)
    test_4yr = end_date - timedelta(days=1460)

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_2yr = executor.submit(count_unique_companies, search_term, test_2yr, end_date)
        future_4yr = executor.submit(count_unique_companies, search_term, test_4yr, end_date)

        count_2yr = future_2yr.result()
        count_4yr = future_4yr.result()

    if progress_callback:
        progress_callback(f"2 years: {count_2yr} unique companies")
        progress_callback(f"4 years: {count_4yr} unique companies")

    # Decide based on results
    if count_2yr >= TARGET_COMPANIES:
        days = 730
        final_range = "2 years"
    elif count_2yr >= 40:
        days = 730
        final_range = "2 years"
    elif count_4yr >= TARGET_COMPANIES:
        days = 1095
        final_range = "3 years"
    elif count_4yr >= 30:
        days = 1460
        final_range = "4 years"
    elif count_4yr >= 15:
        days = 1825
        final_range = "5 years"
    else:
        days = 2555
        final_range = "7 years"

    start_date = end_date - timedelta(days=days)
    return start_date, end_date, final_range


def filter_important_filings(df):
    """Filter for comprehensive filing types"""
    if df.empty:
        return df
    return df[df["filing_type"].isin(RELEVANT_FILINGS)].copy()


def deduplicate_companies(df):
    """Keep only most recent filing per company"""
    if df.empty:
        return df
    df = df.sort_values('filing_date', ascending=False)
    df_unique = df.drop_duplicates(subset=['clean_company_name'], keep='first')
    return df_unique
