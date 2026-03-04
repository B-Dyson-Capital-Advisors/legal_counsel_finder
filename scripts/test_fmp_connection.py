#!/usr/bin/env python3
"""
Quick test script to verify FMP API key is working
"""

import os
import requests

# Load .env file if exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def test_fmp_connection():
    """Test FMP API connection"""
    print("=" * 80)
    print("FMP API CONNECTION TEST")
    print("=" * 80)

    # Check API key
    api_key = os.getenv('FMP_API_KEY')

    if not api_key:
        print("\n❌ ERROR: FMP_API_KEY not found!")
        print("\nPlease set up your API key:")
        print("  1. Copy .env.example to .env")
        print("  2. Edit .env and add: FMP_API_KEY=your_actual_key")
        print("  3. Run this test again")
        return False

    print(f"\n✅ API key found: {api_key[:10]}...{api_key[-4:]}")

    # Test API call (get Apple stock profile - simple test)
    print(f"\n🔍 Testing API connection...")
    print(f"   Endpoint: /v3/profile/AAPL")

    url = "https://financialmodelingprep.com/api/v3/profile/AAPL"
    params = {'apikey': api_key}

    try:
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                company = data[0]
                print(f"\n✅ SUCCESS! API is working!")
                print(f"\n📊 Test Response (Apple Inc.):")
                print(f"   Symbol: {company.get('symbol')}")
                print(f"   Company: {company.get('companyName')}")
                print(f"   Sector: {company.get('sector')}")
                print(f"   Price: ${company.get('price')}")
                print(f"   Market Cap: ${company.get('mktCap'):,}")
                print(f"\n✅ Your FMP API key is valid and working!")
                print(f"✅ You can now run: python scripts/download_fmp_bulk.py")
                return True
            else:
                print(f"\n❌ API returned empty response")
                return False

        elif response.status_code == 401:
            print(f"\n❌ AUTHENTICATION ERROR (401)")
            print(f"   Your API key is invalid or expired")
            print(f"   Check your key at: https://site.financialmodelingprep.com/developer/dashboard")
            return False

        elif response.status_code == 403:
            print(f"\n❌ FORBIDDEN ERROR (403)")
            print(f"   Your API key may not have access to this endpoint")
            print(f"   Make sure you have Professional or Enterprise plan for bulk endpoints")
            return False

        else:
            print(f"\n❌ ERROR: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False

    except requests.exceptions.Timeout:
        print(f"\n❌ TIMEOUT ERROR")
        print(f"   Request timed out - check your internet connection")
        return False

    except requests.exceptions.RequestException as e:
        print(f"\n❌ CONNECTION ERROR")
        print(f"   {str(e)}")
        return False

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR")
        print(f"   {str(e)}")
        return False


if __name__ == "__main__":
    print("\n")
    success = test_fmp_connection()
    print("\n" + "=" * 80)

    if success:
        print("✅ ALL TESTS PASSED!")
        print("\nNext steps:")
        print("  1. Run: python scripts/download_fmp_bulk.py")
        print("  2. Run: python scripts/process_market_data.py")
        print("  3. Add FMP_API_KEY to GitHub Secrets for automation")
    else:
        print("❌ TEST FAILED - Please fix the errors above")

    print("=" * 80 + "\n")
