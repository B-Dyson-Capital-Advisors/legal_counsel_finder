#!/usr/bin/env python3
"""
Test FMP Earnings Calendar API endpoints
Tests date range approach vs per-ticker approach
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta

# Load .env file if exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def load_from_streamlit_secrets():
    """Try to load API key from Streamlit secrets.toml"""
    secrets_file = Path(__file__).parent.parent / '.streamlit' / 'secrets.toml'
    if secrets_file.exists():
        try:
            with open(secrets_file, 'r') as f:
                for line in f:
                    if line.strip().startswith('FMP_API_KEY'):
                        if '=' in line:
                            value = line.split('=', 1)[1].strip()
                            value = value.split('#')[0].strip().strip('"').strip("'")
                            if value and value != "PUT_YOUR_FMP_API_KEY_HERE":
                                return value
        except Exception:
            pass
    return None

def get_api_key():
    """Get API key from environment or secrets"""
    api_key = os.getenv('FMP_API_KEY')
    if not api_key:
        api_key = load_from_streamlit_secrets()
    return api_key

def test_date_range_earnings(api_key):
    """
    Test Option 1: Date Range Approach
    Gets ALL companies with earnings in a date range
    """
    print("\n" + "="*80)
    print("TEST 1: DATE RANGE APPROACH (RECOMMENDED FOR 6000 TICKERS)")
    print("="*80)

    # Get last 3 months of data (FMP limit is 3 months per call)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    # Format dates
    from_date = start_date.strftime('%Y-%m-%d')
    to_date = end_date.strftime('%Y-%m-%d')

    print(f"\nDate Range: {from_date} to {to_date}")
    print(f"Endpoint: /api/v3/earning_calendar")

    url = "https://financialmodelingprep.com/api/v3/earning_calendar"
    params = {
        'from': from_date,
        'to': to_date,
        'apikey': api_key
    }

    try:
        print(f"\nFetching earnings data...")
        response = requests.get(url, params=params, timeout=30)

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                print(f"\n✅ SUCCESS! Retrieved {len(data):,} earnings events")

                # Show sample record
                print(f"\n📊 Sample Record (first entry):")
                sample = data[0]
                print(json.dumps(sample, indent=2))

                # Analyze data
                print(f"\n📈 Data Analysis:")
                symbols = set(item.get('symbol') for item in data if item.get('symbol'))
                print(f"   - Unique companies: {len(symbols):,}")
                print(f"   - Total earnings events: {len(data):,}")

                # Show some example tickers
                print(f"\n   Sample tickers found: {list(symbols)[:10]}")

                # Check data fields
                if data:
                    fields = list(data[0].keys())
                    print(f"\n   Available fields: {fields}")

                return True, len(data), symbols

            elif isinstance(data, dict) and 'Error Message' in data:
                print(f"\n❌ API Error: {data['Error Message']}")
                return False, 0, set()
            else:
                print(f"\n⚠️ Unexpected response format")
                print(f"Response preview: {str(data)[:500]}")
                return False, 0, set()

        elif response.status_code == 401:
            print(f"\n❌ AUTHENTICATION ERROR")
            print(f"   Your API key is invalid")
            return False, 0, set()

        elif response.status_code == 403:
            print(f"\n❌ FORBIDDEN")
            print(f"   Your plan may not have access to this endpoint")
            return False, 0, set()

        else:
            print(f"\n❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False, 0, set()

    except requests.exceptions.Timeout:
        print(f"\n❌ TIMEOUT - Request took too long")
        return False, 0, set()

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return False, 0, set()

def test_stable_earnings(api_key):
    """
    Test the /stable/ version of earnings calendar
    """
    print("\n" + "="*80)
    print("TEST 2: STABLE ENDPOINT (NEW API VERSION)")
    print("="*80)

    print(f"\nEndpoint: /stable/earnings-calendar")

    url = "https://financialmodelingprep.com/stable/earnings-calendar"
    params = {'apikey': api_key}

    try:
        print(f"\nFetching data...")
        response = requests.get(url, params=params, timeout=30)

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                print(f"\n✅ SUCCESS! Retrieved {len(data):,} records")
                print(f"\n📊 Sample Record:")
                print(json.dumps(data[0], indent=2))
                return True
            else:
                print(f"\n⚠️ Response: {str(data)[:500]}")
                return False
        else:
            print(f"\n⚠️ HTTP {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return False

def test_single_ticker_earnings(api_key, symbol='AAPL'):
    """
    Test Option 2: Per-Ticker Historical Approach
    Gets earnings history for ONE ticker
    """
    print("\n" + "="*80)
    print(f"TEST 3: SINGLE TICKER HISTORICAL (for comparison)")
    print("="*80)

    print(f"\nSymbol: {symbol}")
    print(f"Endpoint: /api/v3/historical/earning_calendar/{symbol}")

    url = f"https://financialmodelingprep.com/api/v3/historical/earning_calendar/{symbol}"
    params = {
        'limit': 10,
        'apikey': api_key
    }

    try:
        print(f"\nFetching earnings history for {symbol}...")
        response = requests.get(url, params=params, timeout=10)

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                print(f"\n✅ SUCCESS! Retrieved {len(data)} historical earnings")
                print(f"\n📊 Sample Record:")
                print(json.dumps(data[0], indent=2))

                print(f"\n⚠️ NOTE: You'd need to call this 6,000 times (one per ticker)")
                print(f"   This would be SLOW and hit rate limits!")
                return True
            else:
                print(f"\n⚠️ Response: {str(data)[:500]}")
                return False
        else:
            print(f"\n❌ HTTP {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return False

def main():
    """Run all earnings calendar tests"""
    print("\n" + "="*80)
    print("FMP EARNINGS CALENDAR API TEST")
    print("="*80)

    # Get API key
    api_key = get_api_key()

    if not api_key:
        print("\n❌ ERROR: FMP_API_KEY not found!")
        print("\nPlease set up your API key:")
        print("  1. Add to .env file: FMP_API_KEY=your_key")
        print("  2. Or add to .streamlit/secrets.toml")
        sys.exit(1)

    print(f"\n✓ API Key found: {api_key[:10]}...{api_key[-4:]}")

    # Run tests
    test1_success, total_events, symbols = test_date_range_earnings(api_key)
    test2_success = test_stable_earnings(api_key)
    test3_success = test_single_ticker_earnings(api_key)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY & RECOMMENDATIONS")
    print("="*80)

    if test1_success:
        print(f"\n✅ OPTION 1 (Date Range) - WORKS!")
        print(f"   - Retrieved {total_events:,} earnings events")
        print(f"   - Covers {len(symbols):,} unique companies")
        print(f"   - Only 1 API call needed (vs 6,000 calls)")
        print(f"\n💡 RECOMMENDED APPROACH:")
        print(f"   1. Call date range endpoint for last 3 months")
        print(f"   2. Filter results to match your 6,000 tickers")
        print(f"   3. Get most recent/next earnings date per ticker")
        print(f"   4. Update your data with a scheduled job (daily/weekly)")
    else:
        print(f"\n⚠️ Option 1 - Date range approach had issues")

    if test3_success:
        print(f"\n⚠️ OPTION 2 (Per-Ticker) - Works but NOT recommended")
        print(f"   - Would require 6,000 API calls")
        print(f"   - Risk hitting rate limits")
        print(f"   - Much slower than date range approach")

    print("\n" + "="*80)
    print("\nNext Steps:")
    print("  1. If Option 1 works, I can create a script to:")
    print("     - Fetch date range earnings data")
    print("     - Match with your 6,000 tickers")
    print("     - Add 'next_earnings_date' to your dataset")
    print("  2. Let me know which fields you want to keep!")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
