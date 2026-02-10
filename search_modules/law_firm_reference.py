"""
Reference list of major law firms worldwide.
Used as fallback for extraction when regex patterns don't catch everything.
"""

# Major U.S. and international law firms (Am Law 100, UK Magic Circle, etc.)
MAJOR_LAW_FIRMS = [
    # Top U.S. firms
    "Kirkland & Ellis LLP",
    "Latham & Watkins LLP",
    "DLA Piper LLP",
    "Baker McKenzie LLP",
    "Skadden, Arps, Slate, Meagher & Flom LLP",
    "Sidley Austin LLP",
    "Morgan, Lewis & Bockius LLP",
    "White & Case LLP",
    "Cooley LLP",
    "Ropes & Gray LLP",
    "WilmerHale LLP",
    "Goodwin Procter LLP",
    "Gibson, Dunn & Crutcher LLP",
    "Gibson Dunn & Crutcher LLP",  # Alternative format
    "Paul, Weiss, Rifkind, Wharton & Garrison LLP",
    "Sullivan & Cromwell LLP",
    "Davis Polk & Wardwell LLP",
    "Cravath, Swaine & Moore LLP",
    "Wachtell, Lipton, Rosen & Katz",
    "Simpson Thacher & Bartlett LLP",
    "Cleary Gottlieb Steen & Hamilton LLP",
    "Debevoise & Plimpton LLP",
    "Shearman & Sterling LLP",
    "Allen & Overy LLP",
    "Clifford Chance LLP",
    "Freshfields Bruckhaus Deringer LLP",
    "Linklaters LLP",
    "Slaughter and May",

    # Silicon Valley / Tech focused
    "Wilson Sonsini Goodrich & Rosati P.C.",
    "Wilson Sonsini Goodrich & Rosati PC",
    "Fenwick & West LLP",
    "Gunderson Dettmer Stough Villeneuve Franklin & Hachigian LLP",
    "Orrick, Herrington & Sutcliffe LLP",
    "Morrison & Foerster LLP",
    "Perkins Coie LLP",

    # Corporate / M&A
    "Weil, Gotshal & Manges LLP",
    "Fried, Frank, Harris, Shriver & Jacobson LLP",
    "Willkie Farr & Gallagher LLP",
    "Paul Hastings LLP",
    "Milbank LLP",
    "Proskauer Rose LLP",
    "Schulte Roth & Zabel LLP",
    "Akin Gump Strauss Hauer & Feld LLP",

    # Life Sciences / Healthcare
    "Covington & Burling LLP",
    "Hogan Lovells LLP",
    "Arnold & Porter Kaye Scholer LLP",

    # Finance / Banking
    "Cadwalader, Wickersham & Taft LLP",
    "Cahill Gordon & Reindel LLP",
    "Mayer Brown LLP",

    # Energy / Natural Resources
    "Vinson & Elkins LLP",
    "Baker Botts LLP",
    "Bracewell LLP",
    "Andrews Kurth Kenyon LLP",

    # General corporate
    "Foley & Lardner LLP",
    "Greenberg Traurig LLP",
    "McDermott Will & Emery LLP",
    "K&L Gates LLP",
    "Norton Rose Fulbright LLP",
    "Bryan Cave Leighton Paisner LLP",
    "Reed Smith LLP",
    "Dechert LLP",
    "Hunton Andrews Kurth LLP",
    "O'Melveny & Myers LLP",
    "Quinn Emanuel Urquhart & Sullivan LLP",
    "King & Spalding LLP",
    "Alston & Bird LLP",
    "Jones Day",
    "Pillsbury Winthrop Shaw Pittman LLP",

    # International / European
    "Freshfields Bruckhaus Deringer",
    "Herbert Smith Freehills LLP",
    "Ashurst LLP",
    "Simmons & Simmons LLP",
    "Macfarlanes LLP",
    "Travers Smith LLP",
    "De Brauw Blackstone Westbroek N.V.",
    "De Brauw Blackstone Westbroek",
    "NautaDutilh N.V.",
    "Loyens & Loeff N.V.",

    # Canadian
    "Osler, Hoskin & Harcourt LLP",
    "Blake, Cassels & Graydon LLP",
    "Davies Ward Phillips & Vineberg LLP",
    "Torys LLP",

    # Asian
    "Rajah & Tann LLP",
    "Allen & Gledhill LLP",
    "Kim & Chang",

    # Other notable firms
    "Katten Muchin Rosenman LLP",
    "Stroock & Stroock & Lavan LLP",
    "Kramer Levin Naftalis & Frankel LLP",
    "Akerman LLP",
    "Ballard Spahr LLP",
    "Venable LLP",
    "Troutman Pepper Hamilton Sanders LLP",
    "Dentons LLP",
]

def normalize_firm_name_for_matching(name):
    """Normalize firm name for fuzzy matching"""
    import re
    # Remove punctuation variations
    normalized = re.sub(r'[,.]', '', name.lower())
    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    # Handle & variations
    normalized = normalized.replace(' and ', ' & ')
    return normalized

def find_firms_by_reference(text):
    """
    Find law firms in text by checking against reference list.
    Returns set of firm names found.
    """
    import re
    found_firms = set()

    text_lower = text.lower()

    for firm in MAJOR_LAW_FIRMS:
        # Try exact match first (case insensitive)
        if firm.lower() in text_lower:
            found_firms.add(firm)
            continue

        # Try without punctuation
        firm_normalized = normalize_firm_name_for_matching(firm)
        text_normalized = normalize_firm_name_for_matching(text)

        if firm_normalized in text_normalized:
            found_firms.add(firm)

    return found_firms
