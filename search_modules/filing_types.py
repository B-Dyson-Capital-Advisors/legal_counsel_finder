"""
Centralized filing type definitions for SEC EDGAR searches.

This module defines which SEC filing types are relevant for legal counsel searches.
Used across all search modules for consistency.
"""

# Comprehensive list of SEC filings that typically contain legal counsel information
# or are important for tracking company legal relationships
RELEVANT_FILINGS = [
    # Registration Statements (IPOs, securities offerings)
    "S-1", "S-3", "S-4", "S-8",
    "S-1/A", "S-3/A", "S-4/A", "S-8/A",
    "S-3ASR", "S-1MEF", "S-4MEF",

    # Foreign filer registration statements
    "F-1", "F-3", "F-1/A", "F-3/A",

    # Prospectuses (supplements to registration statements)
    "424B1", "424B2", "424B3", "424B4", "424B5", "424B7", "424B8",

    # Post-effective amendments
    "POS AM", "POSASR",

    # Regulation D (private placements)
    "D", "D/A",

    # Tender Offers
    "SC TO-I", "SC TO-I/A",
    "SC 13E3", "SC 13E4",

    # Proxy Statements (mergers, major corporate actions)
    "DEF 14A", "DEFA14A", "DEFM14A",

    # Periodic Reports (may mention legal counsel)
    "8-K", "8-K/A",
    "10-K", "10-Q", "10-K/A", "10-Q/A",

    # Beneficial Ownership Reports
    "SC 13D", "SC 13G", "SC 13D/A", "SC 13G/A",

    # Correspondence and supplemental materials
    "CORRESP", "UPLOAD", "EX-24",

    # Effectiveness notices
    "EFFECT",
]


# Filings most likely to have detailed legal counsel sections
# (subset of RELEVANT_FILINGS, used for Tab 1: Search Company)
HIGH_PRIORITY_LEGAL_FILINGS = [
    "S-1", "S-3", "S-4", "S-8",
    "S-1/A", "S-3/A", "S-4/A", "S-8/A",
    "S-3ASR", "S-1MEF", "S-4MEF",
    "F-1", "F-3", "F-1/A", "F-3/A",
    "424B1", "424B2", "424B3", "424B4", "424B5", "424B7", "424B8",
    "POS AM", "POSASR",
    "D", "D/A",
    "SC TO-I", "SC TO-I/A",
    "SC 13E3", "SC 13E4",
    "DEF 14A", "DEFA14A", "DEFM14A",
    "CORRESP", "UPLOAD", "EX-24",
]
