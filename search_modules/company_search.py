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


LAW_FIRM_SUFFIXES = ('LLP', 'LLC', 'PLLC', 'P.C.', 'P.A.')
LAW_FIRM_SUFFIX_PATTERN = r'(?:LLP|LLC|PLLC|P\.C\.|P\.A\.)'


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


def clean_firm_name(firm):
    firm = firm.strip()
    firm = re.sub(r'^\s*(?:opinion\s+of|opinion)\s+', '', firm, flags=re.IGNORECASE)
    firm = re.sub(r'\s+', ' ', firm)
    firm = re.sub(r'[.;:]+$', '', firm)
    firm = re.sub(rf'\b({LAW_FIRM_SUFFIX_PATTERN})\b(?:[\s\.,]*(\1))+\b', r'\1', firm, flags=re.IGNORECASE)
    return firm.strip()


def is_valid_firm_name(firm_name, company_name=None):
    if not firm_name:
        return False

    if is_not_law_firm(firm_name, company_name):
        return False

    if not re.search(rf'\b{LAW_FIRM_SUFFIX_PATTERN}\b', firm_name):
        return False

    if re.search(r'\d', firm_name):
        return False

    firm_lower = firm_name.lower()
    metadata_tokens = [
        'opinion', 'date filed', 'filed', 'dated', 'registration statement',
        'statement on', 'form', 'exhibit', 'signature', 'address', 'street',
        'suite', 'city', 'state', 'zip', 'telephone', 'tel.', 'fax', 'email',
        'attention', 're:', 'subject'
    ]
    if any(token in firm_lower for token in metadata_tokens):
        return False

    if len(firm_name.split()) > 8:
        return False

    return True


def normalize_firm_name(firm):
    firm = clean_firm_name(firm)
    firm = re.sub(r'\s+and\s+', ' & ', firm, flags=re.IGNORECASE)
    firm = re.sub(r'\s+', ' ', firm)
    if not any(firm.endswith(suffix) for suffix in LAW_FIRM_SUFFIXES):
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

    if company_name:
        company_lower = company_name.lower()
        company_words = set(company_lower.split())
        name_words = set(name_lower.split())

        if any(word in company_words and len(word) > 4 for word in name_words):
            return False

    invalid_phrases = [
        'legal officer', 'chief legal', 'general counsel', 'corporate counsel',
        'secretary', 'president', 'vice president', 'chief executive',
        'ceo', 'cfo', 'clo', 'officer', 'director', 'manager',
        'associate', 'partner', 'attorney', 'lawyer', 'counsel',
        'corporation', 'company', 'inc', 'llc', 'llp', 'limited',
        'the registrant', 'the company', 'issuer',
        'chief financial', 'financial officer', 'date filed',
        'registration statement', 'signature', 'address', 'dated'
    ]

    if any(phrase in name_lower for phrase in invalid_phrases):
        return False

    if re.search(r'\d', name):
        return False

    words = name.split()
    if len(words) < 2 or len(words) > 4:
        return False

    invalid_word_tokens = {
        'chief', 'financial', 'officer', 'filed', 'date', 'amended',
        'registration', 'statement', 'signature', 'address', 'dated',
        'street', 'suite', 'city', 'state', 'zip', 'telephone', 'fax', 'email'
    }
    if any(word.lower().strip('.,"\'') in invalid_word_tokens for word in words):
        return False

    if not re.match(r"^[A-Za-z.'\\-\\s]+$", name):
        return False

    for word in words:
        if len(word) > 1 and not word[0].isupper():
            return False

    if not any(len(word) > 3 for word in words):
        return False

    if name_lower.startswith('by ') or name_lower.startswith('for '):
        return False

    return True


def is_internal_employee(name, text_near_name):
    """Check if lawyer name appears with company title"""
    internal_titles = [
        'general counsel', 'chief legal officer', 'clo',
        'corporate counsel', 'secretary', 'corporate secretary',
        'in-house counsel', 'legal counsel', 'vice president',
        'senior counsel', 'associate general counsel', 'president',
        'chief executive', 'ceo', 'cfo'
    ]

    name_idx = text_near_name.find(name)
    if name_idx == -1:
        return False

    text_after_name = text_near_name[name_idx:name_idx + 100].lower()
    return any(title in text_after_name for title in internal_titles)


def is_not_law_firm(firm_name, company_name=None):
    """Filter out non-law-firms"""
    firm_lower = firm_name.lower()

    if firm_lower.startswith('opinion of') or firm_lower.startswith('opinion '):
        return True

    garbage_names = ['law_firms', 'lawyers', 'law firm', 'example', 'firm name', 'another']
    if any(garbage in firm_lower for garbage in garbage_names):
        return True

    if company_name and company_name.lower() in firm_lower:
        return True

    accounting_patterns = [
        r'\bdeloitte\b', r'\bpwc\b', r'\bpricewaterhousecoopers\b',
        r'\bernst\s*&\s*young\b', r'\bkpmg\b', r'\bey\b'
    ]
    for pattern in accounting_patterns:
        if re.search(pattern, firm_lower):
            return True

    investment_banks = [
        'goldman sachs', 'morgan stanley', 'jp morgan', 'jpmorgan',
        'credit suisse', 'ubs', 'deutsche bank', 'barclays',
        'cantor fitzgerald', 'oppenheimer', 'jefferies', 'cowen',
        'stifel', 'piper sandler', 'raymond james', 'roth capital',
        'needham', 'wedbush', 'craig-hallum', 'btig', "maxim group"
    ]
    if any(bank in firm_lower for bank in investment_banks):
        return True

    if '& co' in firm_lower and 'llp' not in firm_lower:
        return True

    fund_keywords = ['fund', 'capital', 'ventures', 'holdings', 'trust company']
    if any(keyword in firm_lower for keyword in fund_keywords) and 'llc' in firm_lower and 'llp' not in firm_lower:
        return True

    return False


def extract_lawyers_by_regex(text, company_name):
    """Extract lawyer names using regex patterns"""
    results = defaultdict(set)

    name_line_pattern = r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+(?:Jr\.|Sr\.|II|III|IV))?)'

    # Pattern 0: Multiple name lines with credentials, followed by firm on next line
    # Example:
    # Benjamin A. Potter, Esq.
    # Drew Capurro, Esq.
    # Latham & Watkins LLP
    pattern0 = rf'((?:{name_line_pattern}(?:,?\s*(?:Esq\.|P\.C\.))\s*\n)+)\s*([A-Z][^\n]{{5,60}}?{LAW_FIRM_SUFFIX_PATTERN})'

    matches0 = re.finditer(pattern0, text, re.MULTILINE)

    for match in matches0:
        names_block = match.group(1)
        firm = clean_firm_name(match.group(2))

        if not firm or not is_valid_firm_name(firm, company_name):
            continue

        for line in names_block.strip().split('\n'):
            line = line.strip()
            name_match = re.match(rf'{name_line_pattern}', line)
            if not name_match:
                continue

            name = name_match.group(1).strip()
            if not is_valid_person_name(name, company_name):
                continue

            context = text[match.start():match.end() + 150]
            if not is_internal_employee(name, context):
                normalized_firm = normalize_firm_name(firm)
                results[normalized_firm].add(normalize_lawyer_name(name))

    pattern1 = rf'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+(?:and|,)\s+[A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)*)\s+of\s+([A-Z][^\n]{{5,60}}?{LAW_FIRM_SUFFIX_PATTERN})'

    matches = re.finditer(pattern1, text, re.MULTILINE)

    for match in matches:
        names_part = match.group(1)
        firm = clean_firm_name(match.group(2))
        context = text[max(0, match.start()-100):match.end()+100]

        if not firm or not is_valid_firm_name(firm, company_name):
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
    # Updated to handle ", Esq." or ", P.C." credentials between name and newline
    pattern2 = rf'{name_line_pattern}(?:,?\s*(?:Esq\.|P\.C\.))?\s*\n\s*([A-Z][^\n]{{5,60}}?{LAW_FIRM_SUFFIX_PATTERN})'

    matches2 = re.finditer(pattern2, text, re.MULTILINE)

    for match in matches2:
        name = match.group(1).strip()
        firm = clean_firm_name(match.group(2))
        context = text[match.start():match.end() + 100]

        if not firm or not is_valid_firm_name(firm, company_name):
            continue

        if not is_valid_person_name(name, company_name):
            continue

        if not is_internal_employee(name, context):
            normalized_firm = normalize_firm_name(firm)
            results[normalized_firm].add(normalize_lawyer_name(name))

    # Pattern 3: "Copies to:" section with multiple names before firm
    # Need to handle ", P.C." as a credential (like ", Esq.") not a firm suffix
    # Key: "Name, P.C." = credential | "Firm Name P.C." (no comma) = firm
    pattern3 = rf'(?:Copies to:|Copy to:)\s*\n((?:.*\n)+?)([A-Z][^\n,]{{5,60}}?{LAW_FIRM_SUFFIX_PATTERN}(?:[^\n]{{0,20}})?$)'

    matches3 = re.finditer(pattern3, text, re.MULTILINE)

    for match in matches3:
        names_section = match.group(1)
        firm = clean_firm_name(match.group(2))

        if not firm or not is_valid_firm_name(firm, company_name):
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

            # Extract name, removing ", Esq." or ", P.C." credentials
            # Pattern: "FirstName MiddleInitial? LastName, (Esq.|P.C.)"
            name_match = re.match(r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)(?:,?\s*(?:Esq\.|P\.C\.))?', line)

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
    # Handle both ", Esq." and ", P.C." credentials
    pattern4 = rf'By:\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)(?:,?\s*(?:Esq\.|P\.C\.))?\s*\n\s*([A-Z][^\n]{{5,60}}?{LAW_FIRM_SUFFIX_PATTERN})'

    matches4 = re.finditer(pattern4, text, re.MULTILINE)

    for match in matches4:
        name = match.group(1).strip()
        firm = clean_firm_name(match.group(2))
        context = text[match.start():match.end() + 100]

        if not firm or not is_valid_firm_name(firm, company_name):
            continue

        if not is_valid_person_name(name, company_name):
            continue

        if not is_internal_employee(name, context):
            normalized_firm = normalize_firm_name(firm)
            results[normalized_firm].add(normalize_lawyer_name(name))

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

        return text[:25000]
    except Exception:
        return None


def parse_with_openai(text_sections, company_name, api_key, retries=2):
    """AI extraction with strict validation"""
    if len(text_sections) > 15000:
        text_sections = text_sections[:15000]

    prompt = f"""Extract ONLY EXTERNAL law firm names and EXTERNAL lawyers from this SEC filing for {company_name}.

CRITICAL RULES:
1. ONLY extract PEOPLE'S NAMES - first and last names like "John Smith" or "Jane K. Doe"
2. DO NOT extract:
   - Titles like "Legal Officer", "General Counsel", "Chief Legal Officer"
   - Company names like "{company_name}" or "Corporation"
   - Generic terms like "Attorney", "Counsel", "Lawyer"
   - Phrases like "The Company", "The Registrant"
3. Find law firms ending in LLP, LLC, or P.C.
4. EXCLUDE: Accounting firms (Deloitte, PwC, KPMG, EY)
5. EXCLUDE: Investment banks (Goldman Sachs, Cantor Fitzgerald, etc.)
6. ONLY include lawyers who work AT the law firm, NOT company employees

WHAT A VALID NAME LOOKS LIKE:
✓ "John Smith" - first + last name
✓ "Jane K. Doe" - first + middle initial + last name
✓ "Robert Johnson III" - first + last + suffix

WHAT IS NOT A VALID NAME:
✗ "Legal Officer" - this is a TITLE
✗ "{company_name}" - this is a COMPANY NAME
✗ "Chief Legal Officer" - this is a TITLE
✗ "General Counsel" - this is a TITLE
✗ "Corporate Secretary" - this is a TITLE

PATTERNS TO LOOK FOR:
"Carlos Ramirez and Nicholaus Johnson of Cooley LLP"
-> {{"Cooley LLP": ["Carlos Ramirez", "Nicholaus Johnson"]}}

"First Name Last Name
Law Firm Name LLP"
-> {{"Law Firm Name LLP": ["First Name Last Name"]}}

Text:
{text_sections}

Return JSON with law firms and ONLY PERSON NAMES (not titles, not company names):
{{"Cooley LLP": ["John Smith", "Jane Doe"]}}"""

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

                    cleaned_firm = clean_firm_name(firm)
                    if cleaned_firm and is_valid_firm_name(cleaned_firm, company_name):
                        normalized_firm = normalize_firm_name(cleaned_firm)

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
        firm_only_pattern = rf'(?:LEGAL MATTERS|Legal Matters)\s+(?:.|\n){{0,500}}?\b([A-Z][A-Za-z\s&,]+{LAW_FIRM_SUFFIX_PATTERN})'
        firm_matches = re.finditer(firm_only_pattern, extracted_text, re.MULTILINE | re.IGNORECASE)

        for match in firm_matches:
            potential_firm = clean_firm_name(match.group(1))
            # Basic validation
            if potential_firm and is_valid_firm_name(potential_firm, company_name) and len(potential_firm) > 10:
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
