import streamlit as st
import pandas as pd
from search_modules import (
    search_company_for_lawyers,
    search_lawyer_for_companies,
    search_law_firm_for_companies
)
from search_modules.company_search import load_all_companies

st.set_page_config(
    page_title="Legal Counsel Finder",
    page_icon="⚖️",
    layout="wide"
)

st.markdown("""
<style>
    .main {
        padding-top: 2rem;
    }
    h1 {
        color: #1f1f1f;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    h2 {
        color: #4a4a4a;
        font-weight: 500;
        font-size: 1.5rem;
        margin-top: 1rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 0.5rem 1.5rem;
        font-size: 1rem;
    }
    .info-box {
        background-color: #f8f9fa;
        border-left: 3px solid #4a90e2;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

st.title("Legal Counsel Finder")
st.markdown("Search SEC EDGAR filings to find relationships between companies, law firms, and lawyers")

def get_api_key():
    """Get API key from Streamlit secrets"""
    try:
        return st.secrets["OPENAI_API_KEY"]
    except (KeyError, FileNotFoundError):
        return None

with st.sidebar:
    st.markdown("### About")
    st.markdown("""
    This tool searches SEC EDGAR filings to identify:
    - Law firms and lawyers representing a company
    - Companies represented by a specific lawyer
    - Companies represented by a specific law firm
    """)

    st.markdown("---")
    st.markdown("### Cache")
    st.markdown("Results are cached for 24 hours for faster repeat searches.")
    if st.button("Clear Cache"):
        st.cache_data.clear()
        st.success("Cache cleared!")

tab1, tab2, tab3 = st.tabs(["Search Company", "Search Lawyer", "Search Law Firm"])

with tab1:
    st.header("Find Lawyers for a Company")

    # Load companies for autocomplete
    companies = load_all_companies()

    # Search mode selection
    search_mode = st.radio(
        "Search by:",
        ["Company Search (Type to search)", "Direct Ticker/CIK Entry"],
        horizontal=True,
        key="search_mode"
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        if search_mode == "Company Search (Type to search)":
            if companies:
                # Create a mapping for selectbox
                company_options = [""] + [c['display'] for c in companies]

                selected_display = st.selectbox(
                    "Select Company",
                    options=company_options,
                    index=0,
                    help="Start typing to search by company name, ticker, or CIK",
                    key="company_select"
                )

                # Find selected company data
                selected_company = None
                if selected_display:
                    for c in companies:
                        if c['display'] == selected_display:
                            selected_company = c
                            break
            else:
                st.error("Unable to load company list. Please use Direct Entry mode.")
                selected_company = None
        else:
            # Manual entry mode
            manual_entry = st.text_input(
                "Company Ticker or CIK",
                placeholder="e.g., AAPL, TSLA, 0001318605",
                key="manual_ticker"
            )
            selected_company = None

    with col2:
        years_back = st.number_input(
            "Years to Search",
            min_value=1,
            max_value=10,
            value=5,
            key="years_back"
        )

    if st.button("Search Company", type="primary"):
        # Validate input based on mode
        if search_mode == "Company Search (Type to search)":
            if not selected_company:
                st.error("Please select a company from the dropdown")
            elif not get_api_key():
                st.error("API key not configured. Please contact your administrator.")
            else:
                with st.spinner("Searching SEC filings..."):
                    progress_container = st.container()
                    progress_messages = []

                    def progress_callback(message):
                        progress_messages.append(message)
                        with progress_container:
                            st.info(message)

                    try:
                        result_df = search_company_for_lawyers(
                            selected_company['display'],
                            years_back,
                            get_api_key(),
                            progress_callback,
                            cik=selected_company['cik'],
                            company_name=selected_company['name']
                        )

                        st.success(f"Found {len(result_df)} results")

                        st.dataframe(result_df, use_container_width=True, hide_index=True)

                        csv = result_df.to_csv(index=False)
                        st.download_button(
                            label="Download CSV",
                            data=csv,
                            file_name=f"{selected_company['ticker'] or selected_company['cik']}_lawyers.csv",
                            mime="text/csv"
                        )

                    except Exception as e:
                        st.error(f"Error: {str(e)}")
        else:
            # Manual entry mode
            if not manual_entry:
                st.error("Please enter a company ticker or CIK")
            elif not get_api_key():
                st.error("API key not configured. Please contact your administrator.")
            else:
                with st.spinner("Searching SEC filings..."):
                    progress_container = st.container()
                    progress_messages = []

                    def progress_callback(message):
                        progress_messages.append(message)
                        with progress_container:
                            st.info(message)

                    try:
                        result_df = search_company_for_lawyers(
                            manual_entry.strip().upper(),
                            years_back,
                            get_api_key(),
                            progress_callback
                        )

                        st.success(f"Found {len(result_df)} results")

                        st.dataframe(result_df, use_container_width=True, hide_index=True)

                        csv = result_df.to_csv(index=False)
                        st.download_button(
                            label="Download CSV",
                            data=csv,
                            file_name=f"{manual_entry.lower().replace(' ', '_')}_lawyers.csv",
                            mime="text/csv"
                        )

                    except Exception as e:
                        st.error(f"Error: {str(e)}")

with tab2:
    st.header("Find Companies for a Lawyer")

    lawyer_name = st.text_input(
        "Lawyer Name",
        placeholder="e.g., John Smith",
        key="lawyer_name"
    )

    if st.button("Search Lawyer", type="primary"):
        if not lawyer_name:
            st.error("Please enter a lawyer name")
        else:
            with st.spinner("Searching SEC filings..."):
                progress_container = st.container()
                progress_messages = []

                def progress_callback(message):
                    progress_messages.append(message)
                    with progress_container:
                        st.info(message)

                try:
                    result_df = search_lawyer_for_companies(
                        lawyer_name.strip(),
                        progress_callback
                    )

                    st.success(f"Found {len(result_df)} results")

                    st.dataframe(result_df, use_container_width=True, hide_index=True)

                    csv = result_df.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"{lawyer_name.lower().replace(' ', '_')}_companies.csv",
                        mime="text/csv"
                    )

                except Exception as e:
                    st.error(f"Error: {str(e)}")

with tab3:
    st.header("Find Companies for a Law Firm")

    firm_name = st.text_input(
        "Law Firm Name",
        placeholder="e.g., Cooley LLP, Latham & Watkins",
        key="firm_name"
    )

    if st.button("Search Law Firm", type="primary"):
        if not firm_name:
            st.error("Please enter a law firm name")
        else:
            with st.spinner("Searching SEC filings..."):
                progress_container = st.container()
                progress_messages = []

                def progress_callback(message):
                    progress_messages.append(message)
                    with progress_container:
                        st.info(message)

                try:
                    result_df = search_law_firm_for_companies(
                        firm_name.strip(),
                        progress_callback
                    )

                    st.success(f"Found {len(result_df)} results")

                    st.dataframe(result_df, use_container_width=True, hide_index=True)

                    csv = result_df.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"{firm_name.lower().replace(' ', '_').replace('&', 'and')}_companies.csv",
                        mime="text/csv"
                    )

                except Exception as e:
                    st.error(f"Error: {str(e)}")

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.9rem; padding: 1rem;'>
B. Dyson Capital Advisors | Data sourced from SEC EDGAR
</div>
""", unsafe_allow_html=True)
