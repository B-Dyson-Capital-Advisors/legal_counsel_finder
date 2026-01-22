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

## Local Installation

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

3. (Optional) Configure API key for local use:
```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml with your API key
```

4. Run the application:
```bash
streamlit run app.py
```

## Usage

### For Deployed Apps
If your admin has deployed the app to Streamlit Cloud, simply use the provided URL. All API keys are pre-configured.

### For Local Development
The app will check for an API key in this order:
1. Streamlit secrets (`.streamlit/secrets.toml`)
2. Sidebar input (session-based)

Get your OpenAI API key from https://platform.openai.com/api-keys

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
├── .streamlit/
│   └── secrets.toml.example       # Example secrets configuration
├── requirements.txt               # Python dependencies
├── .gitignore                     # Protects secrets from git
└── README.md                      # This file
```

## Notes
- The application uses adaptive date ranges to optimize search results
- Company searches use OpenAI GPT-4o-mini for extraction accuracy
- Lawyer and law firm searches use pattern matching and SEC EDGAR search API
