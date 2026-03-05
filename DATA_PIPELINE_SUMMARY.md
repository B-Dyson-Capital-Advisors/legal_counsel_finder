# Enhanced Data Pipeline Summary

## What Was Implemented

### 1. Enhanced Filtering
**Company Profiles Bulk API** - Added filters:
- ✓ currency = USD
- ✓ country = US
- ✓ exchange = NYSE or NASDAQ only
- ✓ isEtf = False
- ✓ isAdr = False
- ✓ isFund = False
- ✓ isActivelyTrading = True

**Result**: 25,198 → 3,947 US stocks

### 2. Key Metrics TTM Bulk API
**New data source added**:
- Endpoint: `https://financialmodelingprep.com/stable/key-metrics-ttm-bulk`
- Downloaded: 70,892 key metrics
- Filtered: enterpriseValueTTM > 100MM (49,125 stocks)

### 3. Data Merge Strategy
```
Company Profiles (USD + US) → 25,198 stocks
    ↓ (inner join on symbol)
Key Metrics (EV > 100MM) → 49,125 stocks
    ↓
Merged Dataset → 8,262 stocks (have both)
    ↓ (filter NYSE/NASDAQ, no ETF/ADR/fund)
Stock Reference → 3,947 stocks
    ↓ (merge with IB data)
Final Dataset → Ready for Stock Loan search
```

## Final Stock Reference Columns

**stock_reference_fmp.csv** (352 KB, 3,947 stocks):
1. **symbol** - Ticker symbol
2. **companyName** - Company name
3. **exchange** - NYSE or NASDAQ
4. **marketCap** - Market capitalization
5. **ceo** - CEO name
6. **ipoDate** - IPO date
7. **enterpriseValueTTM** - Enterprise value (> 100MM filter applied)

## Data Flow

### 1. Download Phase (scripts/download_fmp_bulk.py)
```bash
python scripts/download_fmp_bulk.py
```
Downloads:
- `data/fmp/profiles_bulk.csv` (91 MB, gitignored)
- `data/fmp/key_metrics_ttm_bulk.csv` (gitignored)

### 2. Processing Phase (scripts/process_market_data.py)
```bash
python scripts/process_market_data.py
```
Generates:
- `data/stock_reference_fmp.csv` (352 KB, **committed to git**)
- `data/screening_dataset_*.csv` (22 MB, gitignored)

### 3. App Integration (search_modules/stock_loan.py)
```python
# Loads stock_reference_fmp.csv with all 7 columns
us_stocks = load_stock_reference()

# Fetches IB short interest data
stock_loan_df = fetch_shortstock_data()

# Merges: FMP data + IB short interest
enriched_df = us_stocks.merge(stock_loan_df, ...)
```

## Key Benefits

✓ **Stricter filtering**: USD, US, NYSE/NASDAQ, EV > 100MM
✓ **Enhanced data**: Added CEO, IPO Date, Enterprise Value
✓ **Smaller file**: 3,947 stocks vs 6,218 (more focused)
✓ **Committable**: 352 KB (easily deployable)
✓ **Ready for IB merge**: Pre-filtered US stocks with all required fields

## Files Changed

1. **scripts/download_fmp_bulk.py**
   - Added `download_key_metrics_ttm_bulk()` method
   - Downloads both profiles + key metrics

2. **scripts/process_market_data.py**
   - Added `load_key_metrics_ttm()` method
   - Filters: currency=USD, country=US
   - Filters: enterpriseValueTTM > 100MM
   - Inner join: profiles + key metrics
   - Output: Enhanced stock_reference_fmp.csv

3. **search_modules/stock_reference.py**
   - Updated to handle new columns: CEO, IPO Date, Enterprise Value TTM
   - Backward compatible with old format

4. **data/stock_reference_fmp.csv**
   - Updated with 3,947 stocks (down from 6,218)
   - Now includes: marketCap, ceo, ipoDate, enterpriseValueTTM

## Verification

```bash
# Check file
head data/stock_reference_fmp.csv
# symbol,companyName,exchange,marketCap,ceo,ipoDate,enterpriseValueTTM

# Count stocks
wc -l data/stock_reference_fmp.csv
# 3948 (header + 3947 stocks)

# Check size
ls -lh data/stock_reference_fmp.csv
# 352K
```

## Next Steps

When the workflow runs:
1. Downloads profiles + key metrics (daily at 7 AM UTC)
2. Processes with all filters applied
3. Commits stock_reference_fmp.csv to git
4. Streamlit app deploys with updated data
5. Stock Loan search merges FMP + IB data automatically
