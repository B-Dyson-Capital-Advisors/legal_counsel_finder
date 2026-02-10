from .utils import search_entity_for_companies


def search_law_firm_for_companies(firm_name, start_date, end_date, progress_callback=None):
    """Search for companies represented by a law firm"""
    return search_entity_for_companies(firm_name, 'law firm', start_date, end_date, progress_callback)
