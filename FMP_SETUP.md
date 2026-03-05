# Financial Modeling Prep (FMP) Integration Setup

Complete guide to set up automated bulk market data downloads using FMP API.

## Where to Put Your API Key

You have **3 places** to configure your FMP API key depending on the environment:

### 1. **Local Development** (Running scripts manually)

Create a `.env` file in the project root:

```bash
# In /home/user/equity_intel/
cp .env.example .env
```

Then edit `.env` and add your API key:

```bash
FMP_API_KEY=your_actual_api_key_here
```

[OK] The `.env` file is already in `.gitignore` - it will NOT be committed to git.

---

### 2. **GitHub Actions** (Automated daily updates)

Add your API key as a **GitHub Secret**:

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `FMP_API_KEY`
5. Value: `your_actual_api_key_here`
6. Click **Add secret**

[OK] GitHub Actions will now have access to `${{ secrets.FMP_API_KEY }}`

---

### 3. **Streamlit Cloud** (If deploying the app)

Add to Streamlit secrets:

1. Go to your Streamlit Cloud dashboard
2. Click on your app → **Settings** → **Secrets**
3. Add:
   ```toml
   FMP_API_KEY = "your_actual_api_key_here"
   ```

---

## What Gets Downloaded

The FMP integration downloads these bulk datasets daily:

| Dataset | Description | Update Frequency | Rate Limit |
|---------|-------------|------------------|------------|
| **EOD Prices** | Open, High, Low, Close, Volume, Adj Close for ALL stocks | Daily after market close | 10 sec |
| **Company Profiles** | Name, sector, industry, market cap, CEO, employees | Daily | 60 sec |
| **Key Metrics** | P/E, P/B, dividend yield, enterprise value | Daily | 10 sec |
| **Financial Ratios** | All financial ratios (profitability, liquidity, etc.) | Daily | 10 sec |
| **Income Statements** | Revenue, earnings, margins | Quarterly/Annual | 10 sec |

---

## Quick Start

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Set Up API Key (Local)

```bash
# Copy example file
cp .env.example .env

# Edit .env and add your FMP API key
nano .env  # or use any text editor
```

### Step 3: Run Manual Download

```bash
# Download all bulk data
python scripts/download_fmp_bulk.py

# Process into screening datasets
python scripts/process_market_data.py
```

### Step 4: Enable GitHub Actions (Automated Daily Updates)

1. Add `FMP_API_KEY` to GitHub Secrets (see instructions above)
2. GitHub Actions will run automatically at **7 AM UTC daily**
3. Or trigger manually: **Actions** tab → **Update FMP Market Data** → **Run workflow**

---

## Output Files

After processing, you'll find these files in `data/`:

```
data/
├── fmp/                              # Raw FMP data
│   ├── eod_bulk_2026-03-04.csv      # EOD prices
│   ├── profiles_bulk.csv             # Company profiles
│   ├── key_metrics_annual_2026.csv   # Key metrics
│   ├── ratios_annual_2026.csv        # Financial ratios
│   └── income_statement_annual_2026.csv
│
├── screening_data_full.csv           # ALL stocks (complete dataset)
├── screening_data_large_cap.csv      # Market cap > $10B
├── screening_data_mid_cap.csv        # Market cap $2B-$10B
├── screening_data_small_cap.csv      # Market cap $300M-$2B
└── screening_data_us_only.csv        # US stocks only
```

---

## Using the Data in Your App

Example: Load screening data in your Streamlit app

```python
import pandas as pd

# Load pre-filtered data
large_cap_df = pd.read_csv('data/screening_data_large_cap.csv')

# Filter by sector
tech_stocks = large_cap_df[large_cap_df['sector'] == 'Technology']

# Display
st.dataframe(tech_stocks[['symbol', 'companyName', 'price', 'marketCap', 'peRatio']])
```

---

## GitHub Actions Schedule

The workflow runs automatically:

- **Schedule**: Daily at 7:00 AM UTC
  - US market closes at 4:00 PM ET (9:00 PM UTC)
  - FMP processes data overnight
  - Data ready by ~6-7 AM UTC next day

- **Manual Trigger**: You can also run manually from GitHub Actions tab

---

## Customization

### Change Data Update Frequency

Edit `.github/workflows/update_fmp_data.yml`:

```yaml
on:
  schedule:
    # Run at 7 AM UTC daily
    - cron: '0 7 * * *'

    # Or run twice daily (7 AM and 7 PM UTC)
    # - cron: '0 7,19 * * *'

    # Or run weekly on Monday at 7 AM
    # - cron: '0 7 * * 1'
```

### Add More Filters

Edit `scripts/process_market_data.py` in the `create_filtered_datasets()` method:

```python
# Example: Filter by P/E ratio
value_stocks = df[df['peRatio'] < 15].copy()
output_file = self.output_dir / 'screening_data_value.csv'
value_stocks.to_csv(output_file, index=False)
```

---

## Rate Limits & Best Practices

FMP bulk endpoints have rate limits:

- **EOD/Metrics/Ratios/Income**: 1 call per **10 seconds**
- **Profiles**: 1 call per **60 seconds**

Our scripts automatically handle rate limiting with `time.sleep()` between calls.

**Cost Optimization:**
- Bulk endpoints are included in Professional/Enterprise plans
- Much cheaper than individual API calls per stock
- Download once, use for entire day

---

## Troubleshooting

### Error: `FMP_API_KEY not found in environment variables`

**Solution:** Make sure you've set up your API key:
- Local: Create `.env` file with `FMP_API_KEY=your_key`
- GitHub Actions: Add `FMP_API_KEY` to repository secrets

### Error: `403 Forbidden` or `401 Unauthorized`

**Solution:**
- Check your API key is correct
- Verify you have Professional/Enterprise plan (bulk endpoints not available on free tier)
- Check your API key hasn't expired

### No data files generated

**Solution:**
- Check you have internet connection
- Verify FMP API is not down (check https://status.financialmodelingprep.com/)
- Look at script output for specific error messages

---

## Next Steps

1. [OK] Set up API key (see "Where to Put Your API Key" above)
2. [OK] Run manual download to test: `python scripts/download_fmp_bulk.py`
3. [OK] Process data: `python scripts/process_market_data.py`
4. [OK] Add FMP_API_KEY to GitHub Secrets for automation
5. [OK] Integrate screening data into your Streamlit app
6. [OK] Replace manual Excel workflow with automated CSV files

---

## Resources

- [FMP Bulk Endpoints Documentation](https://site.financialmodelingprep.com/developer/docs/bulk-endpoints)
- [FMP API Pricing](https://site.financialmodelingprep.com/developer/docs/pricing)
- [Your FMP Dashboard](https://site.financialmodelingprep.com/developer/dashboard)

---

## [OK] Benefits vs Manual Excel Workflow

| Manual Excel | Automated FMP |
|--------------|---------------|
| [X] Download manually | [OK] Auto-download daily |
| [X] Copy/paste data | [OK] Direct API access |
| [X] Update spreadsheet | [OK] Auto-process & filter |
| [X] Risk of errors | [OK] Validated data pipeline |
| [X] Time-consuming | [OK] Set and forget |
| [X] Outdated data | [OK] Always fresh |

---

**Questions?** Check the scripts for detailed comments or review the FMP documentation.
