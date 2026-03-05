# Solution: Fix Market Cap Data Availability in Deployed App

## Problem

You correctly identified that `profiles_bulk.csv` was **never visible in GitHub** because:

1. **File is gitignored** (`.gitignore` excludes `data/fmp/`)
2. **91 MB size** - too large to commit to git
3. **Workflow downloads it** but doesn't commit it (gitignored)
4. **Only exists as workflow artifact** - not in repo
5. **Streamlit deploys from git** → file never available to app
6. **App falls back to old Excel files** → inaccurate market caps

## Solution

Created a **compact, committable stock reference file**:

### Files Changed

1. **data/stock_reference_fmp.csv** (NEW - 0.5 MB)
   - Pre-filtered to US stocks only (NYSE/NASDAQ)
   - 6,218 stocks vs 88K+ in profiles_bulk
   - Only 6 essential columns: symbol, companyName, exchange, marketCap, sector, industry
   - **Small enough to commit to git** and deploy with app

2. **.gitignore**
   - Added exception: `!data/stock_reference_fmp.csv`
   - Allows this specific file while blocking large bulk data

3. **scripts/process_market_data.py**
   - Now generates BOTH files:
     - `stock_reference_fmp.csv` (0.5 MB, committable)
     - `screening_dataset_*.csv` (79 MB, gitignored)
   - Workflow auto-commits the compact file

4. **search_modules/stock_reference.py**
   - Updated to use `stock_reference_fmp.csv` as primary source
   - Faster load time (0.5 MB vs 91 MB)
   - Falls back to old Excel files if needed

5. **search_modules/stock_loan.py**
   - Simplified to reuse `load_stock_reference()` instead of duplicating logic
   - Removes redundant profiles_bulk.csv loading

## How It Works Now

### Workflow (GitHub Actions)
```
1. Download profiles_bulk.csv (91 MB) → gitignored
2. Process → Generate stock_reference_fmp.csv (0.5 MB)
3. git add data/ → Includes stock_reference_fmp.csv
4. Commit & push → File now in repo
```

### Streamlit App
```
1. Deploys from git → Has stock_reference_fmp.csv
2. load_stock_reference() → Loads 0.5 MB file instantly
3. Accurate market caps → Sorting works correctly
```

## Benefits

- **Deployed app has accurate FMP market cap data**
- **6,218 US stocks with market cap, sector, industry**
- **Fast load time** (0.5 MB vs 91 MB)
- **No API calls needed** on app startup
- **Workflow auto-updates daily** (7 AM UTC)
- **Small enough for git** (523 KB)

## Verification

Run locally:
```bash
python scripts/process_market_data.py
ls -lh data/stock_reference_fmp.csv  # 523K
```

The workflow will auto-commit this file daily, ensuring the deployed app always has fresh market data.

## Next Deploy

On next Streamlit deploy, the app will:
1. Find `stock_reference_fmp.csv` in the repo
2. Load 6,218 US stocks with accurate market caps
3. Market cap sorting will work correctly
