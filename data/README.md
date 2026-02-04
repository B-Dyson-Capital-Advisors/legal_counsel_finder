# Data Directory

## Stock Reference File

Place your stock reference file in this directory with the naming pattern:
```
stock_loan_reference_YYMMDD.xlsx
```

### Required Format

The Excel file should have the following columns:
- **Column A (Symbol)**: Stock ticker symbol (e.g., "A", "AA", "AABB")
- **Column B (Date)**: Reference date (e.g., "2026.02.02")
- **Column C (Time)**: Reference time (e.g., "14:14:20")
- **Column D (Security Type)**: Type of security (e.g., "Common Stock")
- **Column E (Market Cap)**: Market capitalization as a number

### Example
```
Symbol | Date       | Time     | Security Type | Market Cap
A      | 2026.02.02 | 14:14:20 | Common Stock  | 38,181,936,796.82
AA     | 2026.02.02 | 14:14:20 | Common Stock  | 15,126,089,109.12
...
```

### What This File Does

The reference file serves multiple purposes:

1. **Filters Results**: Only tickers present in this file will be shown in lawyer/law firm search results
2. **Excludes ETFs/Trusts**: Since the reference file contains only legitimate common stocks, ETFs and trusts are automatically filtered out
3. **Adds Market Cap**: Market capitalization data is added to all search results
4. **Stock Loan Integration**: The reference data is merged with Interactive Brokers stock loan data

### Notes

- The application will automatically find and use the most recent file matching the pattern
- If no reference file is present, searches will return all results without market cap data
- Market cap values are displayed in the "Market Cap" column across all search types
