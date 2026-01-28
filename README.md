# Legal Counsel Finder

A Streamlit application that searches SEC EDGAR filings to identify relationships between companies, law firms, and lawyers.

## Features

### Search Company
Find law firms and lawyers that represent a specific company by searching through their SEC filings.
- Input: Company name/ticker (searchable dropdown) and date range (from/to)
- Output: List of law firms and lawyers
- Supports: Active companies, delisted companies, acquired companies, and historical companies
- Requires: OpenAI API key

### Search Lawyer
Find companies represented by a specific lawyer.
- Input: Lawyer name and date range (from/to)
- Output: List of companies with tickers and filing dates
- No API key required

### Search Law Firm
Find companies represented by a specific law firm.
- Input: Law firm name and date range (from/to)
- Output: List of companies with tickers and filing dates
- No API key required

## Deployment (Recommended for Teams)

### Deploy to Streamlit Cloud

For team use, deploy to Streamlit Cloud where you configure the API key once and share a link:

1. Push your code to GitHub (can be private repo)
2. Go to https://share.streamlit.io/
3. Connect your GitHub account
4. Deploy from your repository
5. In the app settings, go to **Secrets** and add:
   ```toml
   OPENAI_API_KEY = "sk-your-actual-api-key-here"
   ```
6. Share the deployed URL with your team

Your team members will access the app directly without needing to configure any API keys.

## Local Development

For local development or testing:

1. Clone this repository:
```bash
git clone https://github.com/B-Dyson-Capital-Advisors/legal_counsel_finder.git
cd legal_counsel_finder
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure API key:
```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml with your API key
```

4. Run the application:
```bash
streamlit run app.py
```

## Usage

Simply use the deployed app URL provided by your administrator. All API keys are pre-configured in the deployment.

**Note:** Company Search requires an OpenAI API key, which is configured in the deployment settings by the administrator.

### Search Examples

**Company Search:**
- Select company from searchable dropdown (e.g., type "Apple" or "AAPL")
- Set date range: From 2019-01-01 to 2024-12-31
- Result: Law firms and lawyers who worked on the company's SEC filings during that period
- Works for active, delisted, and acquired companies

**Lawyer Search:**
- Name: John Smith
- Date range: From 2020-01-01 to 2024-12-31
- Result: Companies this lawyer has represented during that period

**Law Firm Search:**
- Name: Cooley LLP
- Date range: From 2020-01-01 to 2024-12-31
- Result: Companies this firm has represented during that period

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
├── .streamlit/
│   └── secrets.toml.example       # Example secrets configuration
├── requirements.txt               # Python dependencies
├── .gitignore                     # Protects secrets from git
└── README.md                      # This file
```

## Notes
- All search types use custom date ranges for precise control over search periods
- Company searches use OpenAI GPT-4o-mini for extraction accuracy
- Lawyer and law firm searches use pattern matching and SEC EDGAR search API
- Company autocomplete searches all SEC-registered companies (active and historical)
- Parallel processing provides 5-10x performance improvement
