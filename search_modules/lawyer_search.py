from .utils import search_entity_for_companies


def search_lawyer_for_companies(lawyer_name, start_date, end_date, progress_callback=None):
    """Search for companies represented by a lawyer"""
    return search_entity_for_companies(lawyer_name, 'lawyer', start_date, end_date, progress_callback)
