import requests
import pandas as pd
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import streamlit as st
from .filing_types import HIGH_PRIORITY_LEGAL_FILINGS
from .law_firm_reference import find_firms_by_reference


@st.cache_data(ttl=3600, show_spinner=False)
def load_all_companies():
    """Load all companies from SEC (cached for 1 hour)"""
    import time

    max_retries = 3
    for attempt in range(max_retries):
        try:
            url = "https://www.sec.gov/files/company_tickers.json"
            headers = {
                "User-Agent": "B. Dyson Capital Advisors contact@bdysoncapital.com",
                "Accept": "application/json"
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            # Check if response is not empty
            if not response.text or len(response.text) == 0:
                raise ValueError("Empty response from SEC API")

            data = response.json()

            companies = []
            for key, company_info in data.items():
                ticker = company_info.get('ticker', '').upper()
                cik = str(company_info['cik_str']).zfill(10)
                name = company_info['title']

                # Create display string
                if ticker:
                    display = f"{name} ({ticker}) - CIK {cik}"
                else:
                    display = f"{name} - CIK {cik}"

                companies.append({
                    'display': display,
                    'name': name,
                    'ticker': ticker,
                    'cik': cik
                })

            # Sort by name for better UX
            companies.sort(key=lambda x: x['name'])
            return companies

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            else:
                st.error("SEC API timeout. Please refresh the page to try again.")
                return []
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            else:
                st.error(f"Network error loading company list: {str(e)}. Please refresh the page.")
                return []
        except ValueError as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            else:
                st.error(f"Invalid response from SEC API: {str(e)}. Please try again later.")
                return []
        except Exception as e:
            st.error(f"Error loading company list: {str(e)}. Please refresh the page or try again later.")
            return []

    return []


def search_company_by_name_or_ticker(search_term):
    """Search for companies by name or ticker"""
    companies = load_all_companies()
    search_term = search_term.lower().strip()

    matches = []
    for company in companies:
        if (search_term in company['name'].lower() or
            search_term in company['ticker'].lower() or
            search_term in company['cik']):
            matches.append(company)

    return matches


def normalize_lawyer_name_for_matching(name):
    """Normalize lawyer name for matching - extract first and last name only"""
    name = name.strip()
    # Remove professional credentials and titles
    name = re.sub(r',?\s*Esq\.?', '', name, flags=re.IGNORECASE)
    name = re.sub(r',?\s*P\.C\.?', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^(Mr\.|Ms\.|Mrs\.|Dr\.)\s+', '', name)

    # Split into words
    parts = name.split()

    if len(parts) == 0:
        return ""
    elif len(parts) == 1:
        return parts[0].lower()
    elif len(parts) == 2:
        # First Last
        return f"{parts[0].lower()} {parts[1].lower()}"
    else:
        # First Middle Last or First M. Last - use first and last only
        return f"{parts[0].lower()} {parts[-1].lower()}"


def deduplicate_firm_lawyers(firm_to_lawyers):
    """
    Deduplicate lawyers within each firm using smart name matching.
    Michelle A. Wong and Michelle Wong are considered the same person.
    """
    deduplicated = defaultdict(set)

    for firm, lawyers in firm_to_lawyers.items():
        seen_normalized = {}  # normalized_name -> original_name

        for lawyer in lawyers:
            normalized = normalize_lawyer_name_for_matching(lawyer)

            if normalized not in seen_normalized:
                # First time seeing this name combination
                seen_normalized[normalized] = lawyer
                deduplicated[firm].add(lawyer)
            else:
                # Already seen this first+last combo
                # Keep the longer version (with middle name if available)
                existing = seen_normalized[normalized]
                if len(lawyer) > len(existing):
                    # Replace with longer version
                    deduplicated[firm].discard(existing)
                    deduplicated[firm].add(lawyer)
                    seen_normalized[normalized] = lawyer

    return deduplicated


def normalize_firm_name(firm):
    firm = firm.strip()
    firm = re.sub(r'\s+and\s+', ' & ', firm, flags=re.IGNORECASE)
    firm = re.sub(r'\s+', ' ', firm)
    if not any(firm.endswith(suffix) for suffix in ['LLP', 'LLC', 'P.C.', 'P.A.']):
        firm = firm + " LLP"
    return firm


def normalize_lawyer_name(name):
    name = name.strip()
    # Remove professional credentials: Esq., P.C., etc.
    name = re.sub(r',?\s*Esq\.?', '', name, flags=re.IGNORECASE)
    name = re.sub(r',?\s*P\.C\.?', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+', ' ', name)
    return name.strip()


def is_valid_person_name(name, company_name=None):
    """Validate that this is actually a person's name, not a title or company name"""
    name_lower = name.lower()

    # Basic format check: 2-4 words, properly capitalized
    words = name.split()
    if len(words) < 2 or len(words) > 4:
        return False

    # Check proper capitalization
    for word in words:
        if len(word) > 1 and not word[0].isupper():
            return False

    # Only reject obvious non-person terms (keep this minimal!)
    obvious_non_persons = [
        'chief executive', 'chief financial', 'chief legal', 'chief operating',
        'general counsel', 'corporate secretary', 'vice president',
        'the registrant', 'the company',
        'date filed', 'second amended', 'this registration',
        'annual meeting', 'our board', 'board of directors', 'special meeting'
    ]

    if any(phrase in name_lower for phrase in obvious_non_persons):
        return False

    # Reject obvious city names only
    obvious_cities = ['menlo park', 'redwood city', 'san francisco', 'new york', 'palo alto']
    if any(city in name_lower for city in obvious_cities):
        return False

    # Last name should be at least 2 characters (was 3, too strict)
    if len(words[-1].rstrip('.')) < 2:
        return False

    return True


def is_internal_employee(name, text_near_name):
    """Check if lawyer name appears with company title (only obvious titles)"""
    # Only check for the most obvious internal titles
    obvious_internal_titles = [
        'general counsel',
        'chief legal officer',
        'corporate secretary',
        'chief executive officer',
        'president and ceo',
        'chief financial officer'
    ]

    name_idx = text_near_name.find(name)
    if name_idx == -1:
        return False

    text_after_name = text_near_name[name_idx:name_idx + 100].lower()
    return any(title in text_after_name for title in obvious_internal_titles)


def is_not_law_firm(firm_name, company_name=None):
    """Filter out non-law-firms - comprehensive filtering"""
    firm_lower = firm_name.lower()

    # Filter document prefixes
    document_prefixes = [
        'opinion of', 'exhibit', 'exhibit to', 'registration of',
        'registration statement', 'amendment to', 'form ', 'filing of',
        'supplement to', 'prospectus', 'preliminary prospectus'
    ]
    if any(firm_lower.startswith(prefix) for prefix in document_prefixes):
        return True

    # Filter garbage names
    garbage_names = ['law_firms', 'lawyers', 'law firm', 'example', 'firm name', 'another']
    if any(garbage in firm_lower for garbage in garbage_names):
        return True

    # Filter company name itself and subsidiaries
    if company_name:
        company_lower = company_name.lower()
        # Check full company name
        if company_lower in firm_lower:
            return True
        # Check if this is a subsidiary (extract company ticker/abbreviation)
        # e.g., "LyondellBasell" -> check for "lyondell" or "lyb"
        company_words = company_lower.split()
        if company_words:
            main_word = company_words[0]
            if len(main_word) > 3 and main_word in firm_lower:
                return True

    # Filter operating companies ending in LLC (not law firms)
    # Law firms are almost always LLP, P.C., or P.A. - rarely LLC
    if 'llc' in firm_lower and 'llp' not in firm_lower:
        operating_company_keywords = [
            'international', 'finance', 'financial', 'capital', 'holdings',
            'ventures', 'trust', 'services', 'corporation', 'inc.',
            'group', 'management', 'investment', 'fund', 'partners llc'
        ]
        if any(keyword in firm_lower for keyword in operating_company_keywords):
            return True

    # Filter accounting firms (Big 4)
    accounting_patterns = [
        r'\bdeloitte\b', r'\bpwc\b', r'\bpricewaterhousecoopers\b',
        r'\bernst\s*&\s*young\b', r'\bkpmg\b', r'\bey\b'
    ]
    for pattern in accounting_patterns:
        if re.search(pattern, firm_lower):
            return True

    # Filter investment banks - comprehensive list
    investment_banks = [
        'goldman sachs', 'morgan stanley', 'jp morgan', 'jpmorgan',
        'credit suisse', 'ubs', 'deutsche bank', 'barclays',
        'cantor fitzgerald', 'oppenheimer', 'jefferies', 'cowen',
        'stifel', 'piper sandler', 'raymond james', 'roth capital',
        'needham', 'wedbush', 'craig-hallum', 'btig', 'maxim group'
    ]
    if any(bank in firm_lower for bank in investment_banks):
        return True

    # Filter "& Co" patterns that are likely not law firms
    if '& co' in firm_lower and 'llp' not in firm_lower:
        return True

    return False


def extract_lawyers_by_regex(text, company_name):
    """Extract lawyer names using regex patterns"""
    results = defaultdict(set)

    # Name pattern: FirstName (MiddleInitials)? LastName
    # Middle initials REQUIRE periods to avoid matching first letter of last name
    # Pattern handles both "Joshua N. Korff" and "Zoey Hitzert"
    name_with_optional_middle = r'[A-Z][a-z]+(?:(?:\s+[A-Z]\.)+\s+|\s+)[A-Z][a-z]+'

    # Firm pattern: Match complete multi-word firm names
    # Examples: "Kirkland & Ellis LLP", "Wilson Sonsini LLP", "Cooley LLP"
    # Pattern: Word (& Word | Word)* LLP/LLC/P.C./P.A.
    firm_pattern = r'[A-Z][a-z]+(?:\s+(?:&\s+)?[A-Z][a-z]+)*\s+(?:LLP|LLC|P\.C\.|P\.A\.)'

    # Single-line firm pattern: CRITICAL for Pattern 2, 3, 4 to prevent matching across newlines
    # Uses [^\S\n]+ instead of \s+ to match whitespace EXCEPT newlines
    # This prevents "Name\nFirm LLP" from being captured as one firm
    firm_pattern_single_line = r'[A-Z][a-z]+(?:[^\S\n]+(?:&[^\S\n]+)?[A-Z][a-z]+)*[^\S\n]+(?:LLP|LLC|P\.C\.|P\.A\.)'

    pattern1 = r'(' + name_with_optional_middle + r'(?:\s+(?:and|,)\s+' + name_with_optional_middle + r')*)\s+of\s+(' + firm_pattern + r')'

    matches = re.finditer(pattern1, text, re.MULTILINE)

    for match in matches:
        names_part = match.group(1)
        firm = match.group(2).strip()
        context = text[max(0, match.start()-100):match.end()+100]

        if is_not_law_firm(firm, company_name):
            continue

        names = re.split(r'\s+and\s+|,\s*', names_part)
        names = [n.strip() for n in names if n.strip()]

        valid_names = []
        for name in names:
            name = re.sub(r'^(Mr\.|Ms\.|Mrs\.|Dr\.)\s+', '', name)
            # Remove professional credentials
            name = re.sub(r',?\s*Esq\.?$', '', name, flags=re.IGNORECASE)
            name = re.sub(r',?\s*P\.C\.?$', '', name, flags=re.IGNORECASE)
            name = name.strip()

            if not is_valid_person_name(name, company_name):
                continue

            if not is_internal_employee(name, context):
                valid_names.append(name)

        if valid_names:
            normalized_firm = normalize_firm_name(firm)
            for name in valid_names:
                results[normalized_firm].add(normalize_lawyer_name(name))

    # Pattern 2: Name (with optional Esq./P.C./titles) on one line, firm on next line
    pattern2 = r'(' + name_with_optional_middle + r')(?:,?\s*(?:Esq\.|P\.C\.))?\s*\n\s*(' + firm_pattern_single_line + r')'

    matches2 = re.finditer(pattern2, text, re.MULTILINE)

    for match in matches2:
        name = match.group(1).strip()
        firm = match.group(2).strip()
        context = text[match.start():match.end() + 100]

        if is_not_law_firm(firm, company_name):
            continue

        if not is_valid_person_name(name, company_name):
            continue

        if not is_internal_employee(name, context):
            normalized_firm = normalize_firm_name(firm)
            results[normalized_firm].add(normalize_lawyer_name(name))

    # Pattern 3: "Copies to:" section with multiple names before firm
    pattern3 = r'(?:Copies to:|Copy to:)\s*\n((?:.*\n)+?)(' + firm_pattern_single_line + r')\s*$'

    matches3 = re.finditer(pattern3, text, re.MULTILINE)

    for match in matches3:
        names_section = match.group(1)
        firm = match.group(2).strip()

        if is_not_law_firm(firm, company_name):
            continue

        # Extract all names from lines in the names section
        # Handle both "Name, Esq." and "Name, P.C." as credentials
        for line in names_section.strip().split('\n'):
            line = line.strip()

            # Skip empty lines or lines that are clearly not names
            if not line or len(line) < 5:
                continue

            # Skip if this line looks like a firm itself (has LLP/LLC without comma before it)
            if re.search(r'(?<!,\s)(?:LLP|LLC|P\.A\.)(?:\s|$)', line):
                continue

            # Extract name with optional middle initials
            name_match = re.match(r'(' + name_with_optional_middle + r')(?:,?\s*(?:Esq\.|P\.C\.))?', line)

            if not name_match:
                continue

            name = name_match.group(1).strip()

            if not is_valid_person_name(name, company_name):
                continue

            context = text[match.start():match.end() + 200]
            if not is_internal_employee(name, context):
                normalized_firm = normalize_firm_name(firm)
                results[normalized_firm].add(normalize_lawyer_name(name))

    # Pattern 4: By: signature pattern
    pattern4 = r'By:\s*(' + name_with_optional_middle + r')(?:,?\s*(?:Esq\.|P\.C\.))?\s*\n\s*(' + firm_pattern_single_line + r')'

    matches4 = re.finditer(pattern4, text, re.MULTILINE)

    for match in matches4:
        name = match.group(1).strip()
        firm = match.group(2).strip()
        context = text[match.start():match.end() + 100]

        if is_not_law_firm(firm, company_name):
            continue

        if not is_valid_person_name(name, company_name):
            continue

        if not is_internal_employee(name, context):
            normalized_firm = normalize_firm_name(firm)
            results[normalized_firm].add(normalize_lawyer_name(name))

    # Flexible firm pattern for "legal matters" sections that allows commas and locations
    # Matches: "Gibson, Dunn & Crutcher LLP" or "Davis Polk & Wardwell LLP"
    # Pattern captures firm name up to location markers (city names, or double comma)
    firm_pattern_with_commas = r'[A-Z][a-z]+(?:[,\s]+(?:&[,\s]+)?[A-Z][a-z]+)*[,\s]+(?:LLP|LLC|P\.C\.|P\.A\.)'

    # Pattern 6: "represented by" or "passed upon by" patterns (common in legal matters sections)
    # Matches: "represented by [Name], [Firm]" or "passed upon by [Name] of [Firm]"
    pattern6 = r'(?:represented|passed upon|advised)\s+(?:for [^,]+\s+)?by\s+(' + name_with_optional_middle + r')(?:,?\s*(?:Esq\.|P\.C\.))?\s*(?:,\s*|of\s+)(' + firm_pattern_with_commas + r')'

    matches6 = re.finditer(pattern6, text, re.MULTILINE | re.IGNORECASE)

    for match in matches6:
        name = match.group(1).strip()
        firm = match.group(2).strip()
        context = text[max(0, match.start()-100):match.end()+100]

        if is_not_law_firm(firm, company_name):
            continue

        if not is_valid_person_name(name, company_name):
            continue

        if not is_internal_employee(name, context):
            normalized_firm = normalize_firm_name(firm)
            results[normalized_firm].add(normalize_lawyer_name(name))

    # Pattern 7: Firm-only patterns in legal matters sections (when no names are listed)
    # Matches: "passed upon by [Firm]" or "represented by [Firm]"
    # This captures firms even without specific lawyer names
    # Uses flexible pattern to handle commas in firm names
    pattern7 = r'(?:represented|passed upon|advised)\s+(?:for (?:us|the [^,]+?)\s+)?by\s+(' + firm_pattern_with_commas + r')(?:,\s+[A-Z][a-z]+)?'

    matches7 = re.finditer(pattern7, text, re.MULTILINE | re.IGNORECASE)

    for match in matches7:
        firm = match.group(1).strip()

        # Clean up firm name - remove trailing commas and location info
        firm = re.sub(r',\s*$', '', firm)

        if is_not_law_firm(firm, company_name):
            continue

        # For firm-only matches, add empty name (will be shown as just firm)
        normalized_firm = normalize_firm_name(firm)
        results[normalized_firm].add('(Firm only - no lawyer name listed)')

    # Pattern 8: AGGRESSIVE - Extract ALL law firm names from LEGAL MATTERS sections
    # This is a fallback to ensure we don't miss firms in legal matters sections
    legal_matters_match = re.search(r'LEGAL MATTERS.{0,3000}', text, re.IGNORECASE | re.DOTALL)
    if legal_matters_match:
        legal_section = legal_matters_match.group(0)

        # Simple firm pattern - just look for firm names with common suffixes
        # Allows commas in names: "Gibson, Dunn & Crutcher LLP"
        simple_firm_pattern = r'([A-Z][A-Za-z]+(?:(?:,\s*|\s+)(?:&\s+)?[A-Z][A-Za-z]+)*(?:,\s*|\s+)(?:LLP|LLC|P\.C\.|P\.A\.|N\.V\.))'

        for match in re.finditer(simple_firm_pattern, legal_section):
            firm = match.group(1).strip()

            # Remove location info if present (e.g., ", Houston" or ", New York")
            firm = re.sub(r',\s+[A-Z][a-z]+(?:,\s+[A-Z][a-z]+)?$', '', firm)
            firm = re.sub(r',\s*$', '', firm)

            if is_not_law_firm(firm, company_name):
                continue

            # Skip if this firm name starts with common non-firm words
            if firm.split()[0].lower() in ['neither', 'each', 'and', 'or', 'the', 'such', 'any', 'all']:
                continue

            normalized_firm = normalize_firm_name(firm)
            results[normalized_firm].add('(Firm only - no lawyer name listed)')

    # Pattern 5: DISABLED - Too greedy and creates garbage matches
    # Problem: firm_pattern can match person names + firm names together
    # Example: "Zoey Hitzert\nKirkland & Ellis LLP" matches as firm="Zoey Hitzert Kirkland & Ellis LLP"
    # The pattern can't distinguish where person names end and firm names begin
    # Result: Creates junk like "Annual Meeting", "Our Board" as lawyer names
    # Patterns 1-4 are sufficient and more accurate

    # FALLBACK: Use reference list of major law firms
    # If we haven't found any results yet, check against known firm list
    if len(results) == 0:
        reference_firms = find_firms_by_reference(text)
        for firm in reference_firms:
            # Still apply the non-law-firm filter
            if not is_not_law_firm(firm, company_name):
                normalized_firm = normalize_firm_name(firm)
                results[normalized_firm].add('(Firm only - no lawyer name listed)')

    return results


def get_cik_from_ticker(ticker):
    ticker = ticker.replace(" US Equity", "").strip()
    try:
        url = "https://www.sec.gov/files/company_tickers.json"
        headers = {"User-Agent": "Company contact@email.com"}
        response = requests.get(url, headers=headers)
        data = response.json()
        ticker_upper = ticker.upper()

        for key, company_info in data.items():
            if company_info.get('ticker', '').upper() == ticker_upper:
                cik = str(company_info['cik_str'])
                company_name = company_info['title']
                return cik, company_name
    except Exception:
        pass
    return None, None


def get_company_filings(cik, start_date, end_date):
    url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
    headers = {"User-Agent": "Company contact@email.com"}

    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        filings = []
        recent = data.get('filings', {}).get('recent', {})

        # Convert dates to strings for comparison
        if hasattr(start_date, 'strftime'):
            start_date_str = start_date.strftime('%Y-%m-%d')
        else:
            start_date_str = str(start_date)

        if hasattr(end_date, 'strftime'):
            end_date_str = end_date.strftime('%Y-%m-%d')
        else:
            end_date_str = str(end_date)

        for i in range(len(recent.get('form', []))):
            filing_type = recent['form'][i]
            filing_date = recent['filingDate'][i]

            if filing_type in HIGH_PRIORITY_LEGAL_FILINGS and start_date_str <= filing_date <= end_date_str:
                filings.append({
                    'type': filing_type,
                    'date': filing_date,
                    'accession': recent['accessionNumber'][i],
                    'primary_doc': recent.get('primaryDocument', [None])[i] if i < len(recent.get('primaryDocument', [])) else None
                })

        filings.sort(key=lambda x: x['date'], reverse=True)
        return filings
    except Exception:
        return []


def extract_counsel_sections(doc_url):
    headers = {"User-Agent": "Company contact@email.com"}

    try:
        response = requests.get(doc_url, headers=headers, timeout=20)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text(separator='\n')

        if len(text) < 5000:
            return None

        # Look for LEGAL MATTERS section (typically near end of document)
        legal_matters_idx = text.upper().find('LEGAL MATTERS')

        if legal_matters_idx != -1:
            # Extract from 1000 chars before to 5000 chars after LEGAL MATTERS
            start = max(0, legal_matters_idx - 1000)
            end = min(len(text), legal_matters_idx + 5000)
            legal_section = text[start:end]

            # Also include first 25k for other patterns (signature blocks, etc.)
            return text[:25000] + "\n\n" + legal_section
        else:
            # No LEGAL MATTERS section, return first 25k
            return text[:25000]
    except Exception:
        return None


def parse_with_openai(text_sections, company_name, api_key, retries=2):
    """AI extraction - more permissive"""
    if len(text_sections) > 15000:
        text_sections = text_sections[:15000]

    prompt = f"""Extract law firm names and lawyer names from this SEC filing for {company_name}.

Find:
1. Law firm names ending in LLP, LLC, P.C., or P.A.
2. Lawyer names (first and last name, like "John Smith" or "Jane K. Doe")
3. Look in sections like "Legal Matters", signature blocks, and anywhere lawyers are mentioned

Exclude only obvious non-lawyers:
- Job titles like "Chief Executive Officer", "General Counsel" (when used as a title)
- Accounting firms: Deloitte, PwC, KPMG, Ernst & Young
- Investment banks: Goldman Sachs, Morgan Stanley, JP Morgan

Examples:
"John Smith of Wilson Sonsini LLP" -> {{"Wilson Sonsini LLP": ["John Smith"]}}
"Jane Doe, Esq.\nCooley LLP" -> {{"Cooley LLP": ["Jane Doe"]}}

Text:
{text_sections}

Return JSON format:
{{"Law Firm Name LLP": ["Lawyer Name 1", "Lawyer Name 2"]}}"""

    for attempt in range(retries + 1):
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                },
                json={
                    "model": "gpt-5-nano",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0
                },
                timeout=30
            )

            # Check for HTTP errors
            if response.status_code != 200:
                error_msg = f"OpenAI API error {response.status_code}"
                try:
                    error_detail = response.json().get('error', {}).get('message', '')
                    if error_detail:
                        error_msg += f": {error_detail}"
                except:
                    pass
                raise Exception(error_msg)

            result = response.json()

            if 'choices' in result and len(result['choices']) > 0:
                response_text = result['choices'][0]['message']['content']
                response_text = re.sub(r'```json\s*|\s*```', '', response_text).strip()
                data = json.loads(response_text)

                filtered_data = {}
                for firm, lawyers in data.items():
                    if firm.lower() in ['firm a', 'firm b', 'example firm']:
                        continue

                    if not is_not_law_firm(firm, company_name):
                        normalized_firm = normalize_firm_name(firm)

                        normalized_lawyers = []
                        for l in lawyers:
                            if not l or not l.strip():
                                continue

                            if not is_valid_person_name(l, company_name):
                                continue

                            if l in text_sections:
                                idx = text_sections.find(l)
                                context = text_sections[idx:idx+200]
                                if is_internal_employee(l, context):
                                    continue

                            normalized_lawyers.append(normalize_lawyer_name(l))

                        if normalized_lawyers:
                            filtered_data[normalized_firm] = normalized_lawyers

                return filtered_data
        except Exception:
            if attempt < retries:
                continue

    return {}

def process_single_filing(filing, cik, company_name, api_key):
    """Process a single filing and extract lawyers (for parallel execution)"""
    accession_no_dashes = filing['accession'].replace('-', '')

    if filing['primary_doc']:
        doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{filing['primary_doc']}"
    else:
        doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{filing['accession']}.htm"

    extracted_text = extract_counsel_sections(doc_url)

    firm_to_lawyers = defaultdict(set)

    if not extracted_text:
        # Document failed to extract or was too short
        raise Exception(f"No text extracted from {filing['type']} ({filing['date']})")

    # Try regex extraction
    regex_results = extract_lawyers_by_regex(extracted_text, company_name)
    for firm, lawyers in regex_results.items():
        firm_to_lawyers[firm].update(lawyers)

    # Try OpenAI extraction
    firm_lawyers_dict = parse_with_openai(extracted_text, company_name, api_key)

    for firm, lawyers in firm_lawyers_dict.items():
        firm_to_lawyers[firm].update(lawyers)

    # Even if no lawyers found, try to extract just the law firm name
    if not firm_to_lawyers:
        # Look for "Legal Matters" section with just firm name
        firm_only_pattern = r'(?:LEGAL MATTERS|Legal Matters)\s+(?:.|\n){0,500}?\b([A-Z][A-Za-z\s&,]+(?:LLP|LLC|P\.C\.|P\.A\.))'
        firm_matches = re.finditer(firm_only_pattern, extracted_text, re.MULTILINE | re.IGNORECASE)

        for match in firm_matches:
            potential_firm = match.group(1).strip()
            # Basic validation
            if not is_not_law_firm(potential_firm, company_name) and len(potential_firm) > 10:
                normalized_firm = normalize_firm_name(potential_firm)
                firm_to_lawyers[normalized_firm] = set()  # Empty set of lawyers
                break  # Only take first match

    if not firm_to_lawyers:
        # Successfully extracted text but found no lawyers or firms
        raise Exception(f"No lawyers found in {filing['type']} ({filing['date']})")

    return firm_to_lawyers


def search_company_for_lawyers(company_identifier, start_date, end_date, api_key, progress_callback=None, cik=None, company_name=None):
    """Search for lawyers representing a company

    Args:
        company_identifier: Ticker, name, or CIK (for display/cache key)
        start_date: Start date for search range
        end_date: End date for search range
        api_key: OpenAI API key
        progress_callback: Progress callback function
        cik: Pre-resolved CIK (optional, for autocomplete)
        company_name: Pre-resolved company name (optional, for autocomplete)
    """

    if progress_callback:
        progress_callback(f"Finding lawyers for {company_identifier}")
        if hasattr(start_date, 'strftime'):
            start_str = start_date.strftime('%Y-%m-%d')
        else:
            start_str = str(start_date)
        if hasattr(end_date, 'strftime'):
            end_str = end_date.strftime('%Y-%m-%d')
        else:
            end_str = str(end_date)
        progress_callback(f"Date range: {start_str} to {end_str}")

    # Use provided CIK/name or lookup by identifier
    if not cik or not company_name:
        cik, company_name = get_cik_from_ticker(company_identifier)
        if not cik:
            raise ValueError(f"Company '{company_identifier}' not found")

    if progress_callback:
        progress_callback(f"Getting filings from {start_str} to {end_str}...")

    filings = get_company_filings(cik, start_date, end_date)

    if not filings:
        raise ValueError(f"No relevant filings found for {company_identifier}")

    if progress_callback:
        progress_callback(f"Found {len(filings)} total filings")
        if filings:
            oldest_date = min(f['date'] for f in filings)
            newest_date = max(f['date'] for f in filings)
            progress_callback(f"Date range: {oldest_date} to {newest_date}")

    if progress_callback:
        progress_callback(f"Processing {len(filings)} filings in parallel...")

    firm_to_lawyers = defaultdict(set)
    failed_count = 0
    success_count = 0
    no_text_count = 0
    no_lawyers_count = 0

    # Process filings in parallel (5 at a time to respect rate limits)
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_filing = {
            executor.submit(process_single_filing, filing, cik, company_name, api_key): filing
            for filing in filings
        }

        completed = 0
        for future in as_completed(future_to_filing):
            completed += 1
            if progress_callback and completed % 5 == 0:
                progress_callback(f"Progress: {completed}/{len(filings)} filings processed...")

            try:
                filing_results = future.result()
                if filing_results:
                    success_count += 1
                    for firm, lawyers in filing_results.items():
                        firm_to_lawyers[firm].update(lawyers)
            except Exception as e:
                failed_count += 1
                error_str = str(e)

                # Track failure reasons
                if "No text extracted" in error_str:
                    no_text_count += 1
                elif "No lawyers found" in error_str:
                    no_lawyers_count += 1

                # Log first few errors to help debug
                if failed_count <= 5 and progress_callback:
                    progress_callback(f"Warning: {error_str[:150]}")

    if progress_callback:
        progress_callback(f"Results: {success_count} filings with lawyers, {no_text_count} failed to extract, {no_lawyers_count} had no lawyers")

    if not firm_to_lawyers:
        raise ValueError(f"No lawyers found for {company_identifier}")

    # Deduplicate lawyers within each firm (handles name variations)
    firm_to_lawyers = deduplicate_firm_lawyers(firm_to_lawyers)

    results = []
    for firm, lawyers in firm_to_lawyers.items():
        if lawyers:
            for lawyer in sorted(lawyers):  # Sort for consistent output
                results.append({'Law Firm': firm, 'Lawyer': lawyer})
        else:
            results.append({'Law Firm': firm, 'Lawyer': ''})

    df = pd.DataFrame(results)

    # Remove exact duplicates (same firm + same lawyer)
    df = df.drop_duplicates(subset=['Law Firm', 'Lawyer'], keep='first')

    return df
