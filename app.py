import streamlit as st
import pandas as pd
from search_modules import (
    search_company_for_lawyers,
    search_lawyer_for_companies,
    search_law_firm_for_companies
)

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

tab1, tab2, tab3 = st.tabs(["Search Company", "Search Lawyer", "Search Law Firm"])

with tab1:
    st.header("Find Lawyers for a Company")

    col1, col2 = st.columns([2, 1])

    with col1:
        company_ticker = st.text_input(
            "Company Ticker",
            placeholder="e.g., AAPL, TSLA, NVDA",
            key="company_ticker"
        )

    with col2:
        years_back = st.number_input(
            "Years to Search",
            min_value=1,
            max_value=10,
            value=5,
            key="years_back"
        )

    if st.button("Search Company", type="primary"):
        if not company_ticker:
            st.error("Please enter a company ticker")
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
                        company_ticker.strip().upper(),
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
                        file_name=f"{company_ticker.lower()}_lawyers.csv",
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
