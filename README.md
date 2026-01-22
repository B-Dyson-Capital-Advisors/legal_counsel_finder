# Legal Counsel Finder

A Streamlit application that searches SEC EDGAR filings to identify relationships between companies, law firms, and lawyers.

## Features

### Search Company
Find law firms and lawyers that represent a specific company by searching through their SEC filings.
- Input: Company ticker and years to search back
- Output: List of law firms and lawyers
- Requires: OpenAI API key

### Search Lawyer
Find companies represented by a specific lawyer.
- Input: Lawyer name
- Output: List of companies with tickers and filing dates
- No API key required

### Search Law Firm
Find companies represented by a specific law firm.
- Input: Law firm name
- Output: List of companies with tickers and filing dates
- No API key required

## Installation

1. Clone this repository:
```bash
git clone https://github.com/B-Dyson-Capital-Advisors/legal_counsel_finder.git
cd legal_counsel_finder
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
streamlit run app.py
```

## Usage

### OpenAI API Key
For the Company Search feature, you need an OpenAI API key:
1. Get your API key from https://platform.openai.com/api-keys
2. Enter it in the sidebar when using the app
3. The key is stored only in your browser session and is never saved to disk

### Search Examples

**Company Search:**
- Ticker: AAPL
- Years: 5
- Result: Law firms and lawyers who worked on Apple's SEC filings

**Lawyer Search:**
- Name: John Smith
- Result: Companies this lawyer has represented

**Law Firm Search:**
- Name: Cooley LLP
- Result: Companies this firm has represented

## Export Results
All search results can be downloaded as CSV files using the download button.

## Data Source
All data is sourced from SEC EDGAR public filings.

## Project Structure
```
legal_counsel_finder/
├── app.py                          # Main Streamlit application
├── search_modules/                 # Search logic modules
│   ├── __init__.py
│   ├── company_search.py          # Company to lawyers search
│   ├── lawyer_search.py           # Lawyer to companies search
│   ├── law_firm_search.py         # Law firm to companies search
│   └── utils.py                   # Shared utilities
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## Notes
- The application uses adaptive date ranges to optimize search results
- Company searches use OpenAI GPT-4o-mini for extraction accuracy
- Lawyer and law firm searches use pattern matching and SEC EDGAR search API
