import streamlit as st
import pandas as pd
from search_modules import (
    search_company_for_lawyers,
    search_lawyer_for_companies,
    search_law_firm_for_companies
)
from search_modules.company_search import load_all_companies
from search_modules.stock_loan import fetch_shortstock_data

st.set_page_config(
    page_title="Legal Counsel Finder",
    page_icon="⚖️",
    layout="centered"
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

    /* Hide default radio button styling */
    .stRadio > div {
        gap: 0.5rem;
    }
    .stRadio > div > label {
        background-color: transparent;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        cursor: pointer;
        transition: background-color 0.2s ease;
        border: 1px solid transparent;
    }
    .stRadio > div > label:hover {
        background-color: #f6f8fa;
        border-color: #d0d7de;
    }
    .stRadio > div > label[data-checked="true"] {
        background-color: #0969da;
        color: white;
        border-color: #0969da;
    }
    .stRadio > div > label[data-checked="true"]:hover {
        background-color: #0860ca;
    }
</style>
""", unsafe_allow_html=True)

st.title("Legal Counsel Finder")

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Select Feature", ["Legal Counsel Finder", "Stock Loan Availability"])

def get_api_key():
    """Get API key from Streamlit secrets"""
    try:
        return st.secrets["OPENAI_API_KEY"]
    except (KeyError, FileNotFoundError):
        return None

# Initialize session state for results persistence
if 'company_results' not in st.session_state:
    st.session_state.company_results = None
if 'lawyer_results' not in st.session_state:
    st.session_state.lawyer_results = None
if 'firm_results' not in st.session_state:
    st.session_state.firm_results = None
if 'stock_loan_results' not in st.session_state:
    st.session_state.stock_loan_results = None

# Date range presets
def get_date_range(preset):
    """Calculate date range based on preset selection"""
    end_date = pd.Timestamp.now()
    if preset == "Last 30 days":
        start_date = end_date - pd.DateOffset(days=30)
    elif preset == "Last year":
        start_date = end_date - pd.DateOffset(years=1)
    elif preset == "Last 3 years":
        start_date = end_date - pd.DateOffset(years=3)
    elif preset == "Last 5 years":
        start_date = end_date - pd.DateOffset(years=5)
    elif preset == "Last 10 years":
        start_date = end_date - pd.DateOffset(years=10)
    elif preset == "All (since 2001)":
        start_date = pd.Timestamp("2001-01-01")
    else:  # Custom
        return None, None
    return start_date.date(), end_date.date()

if page == "Legal Counsel Finder":
    st.markdown("Search SEC EDGAR filings to find relationships between companies, law firms, and lawyers")

    tab1, tab2, tab3 = st.tabs(["Search Company", "Search Lawyer", "Search Law Firm"])

    with tab1:
        st.header("Find Lawyers for a Company")

        # Load companies for autocomplete
        companies = load_all_companies()

        # Single row layout: Company selector, Date Range dropdown, From date, To date
        col1, col2, col3, col4 = st.columns([3, 2, 1, 1])

        with col1:
            if companies:
                # Create a mapping for selectbox
                company_options = [""] + [c['display'] for c in companies]

                selected_display = st.selectbox(
                    "Select Company (enter ticker or company name)",
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
                st.error("Unable to load company list. Please refresh the page.")
                selected_company = None

        with col2:
            date_preset = st.selectbox(
                "Date Range",
                options=["Last 30 days", "Last year", "Last 3 years", "Last 5 years", "Last 10 years", "All (since 2001)", "Custom"],
                index=3,  # Default to "Last 5 years"
                key="company_date_preset"
            )

        # Calculate dates based on preset
        if date_preset != "Custom":
            preset_start, preset_end = get_date_range(date_preset)
        else:
            preset_start = (pd.Timestamp.now() - pd.DateOffset(years=5)).date()
            preset_end = pd.Timestamp.now().date()

        with col3:
            start_date = st.date_input(
                "From",
                value=preset_start,
                max_value=pd.Timestamp.now(),
                key="start_date"
            )

        with col4:
            end_date = st.date_input(
                "To",
                value=preset_end,
                max_value=pd.Timestamp.now(),
                key="end_date"
            )

        search_clicked = st.button("Search Company", type="primary", key="company_search_btn", use_container_width=True)

        if search_clicked:
            if not selected_company:
                st.error("Please select a company from the dropdown")
            elif not get_api_key():
                st.error("API key not configured. Please contact your administrator.")
            elif start_date >= end_date:
                st.error("Start date must be before end date")
            else:
                with st.spinner("Searching SEC filings..."):
                    # Single status container that updates
                    status_placeholder = st.empty()
    
                    def progress_callback(message):
                        status_placeholder.info(message)
    
                    try:
                        result_df = search_company_for_lawyers(
                            selected_company['display'],
                            start_date,
                            end_date,
                            get_api_key(),
                            progress_callback,
                            cik=selected_company['cik'],
                            company_name=selected_company['name']
                        )
    
                        status_placeholder.empty()
    
                        # Store results in session state
                        st.session_state.company_results = {
                            'df': result_df,
                            'filename': f"{selected_company['ticker'] or selected_company['cik']}_lawyers.csv"
                        }
    
                    except Exception as e:
                        status_placeholder.empty()
                        st.error(f"Error: {str(e)}")
                        st.session_state.company_results = None
    
        # Display stored results if they exist
        if st.session_state.company_results is not None:
            result_df = st.session_state.company_results['df']
            st.success(f"Found {len(result_df)} results")
            st.dataframe(result_df, use_container_width=True, hide_index=True)
    
            csv = result_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=st.session_state.company_results['filename'],
                mime="text/csv",
                key="company_csv_download"
            )
    
    with tab2:
        st.header("Find Companies for a Lawyer")
    
        # Single row layout: Lawyer name, From date, To date
        col1, col2, col3 = st.columns([3, 1, 1])
    
        with col1:
            lawyer_name = st.text_input(
                "Lawyer Name",
                placeholder="e.g., John Smith",
                key="lawyer_name"
            )
    
        with col2:
            lawyer_start_date = st.date_input(
                "From",
                value=pd.Timestamp.now() - pd.DateOffset(years=5),
                max_value=pd.Timestamp.now(),
                key="lawyer_start_date"
            )
    
        with col3:
            lawyer_end_date = st.date_input(
                "To",
                value=pd.Timestamp.now(),
                max_value=pd.Timestamp.now(),
                key="lawyer_end_date"
            )
    
        if st.button("Search Lawyer", type="primary"):
            if not lawyer_name:
                st.error("Please enter a lawyer name")
            elif lawyer_start_date >= lawyer_end_date:
                st.error("Start date must be before end date")
            else:
                with st.spinner("Searching SEC filings..."):
                    # Single status container that updates
                    status_placeholder = st.empty()
    
                    def progress_callback(message):
                        status_placeholder.info(message)
    
                    try:
                        result_df = search_lawyer_for_companies(
                            lawyer_name.strip(),
                            lawyer_start_date,
                            lawyer_end_date,
                            progress_callback
                        )
    
                        status_placeholder.empty()
    
                        # Store results in session state
                        st.session_state.lawyer_results = {
                            'df': result_df,
                            'filename': f"{lawyer_name.lower().replace(' ', '_')}_companies.csv"
                        }
    
                    except Exception as e:
                        status_placeholder.empty()
                        st.error(f"Error: {str(e)}")
                        st.session_state.lawyer_results = None
    
        # Display stored results if they exist
        if st.session_state.lawyer_results is not None:
            result_df = st.session_state.lawyer_results['df']
            st.success(f"Found {len(result_df)} results")
            st.dataframe(result_df, use_container_width=True, hide_index=True)
    
            csv = result_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=st.session_state.lawyer_results['filename'],
                mime="text/csv",
                key="lawyer_csv_download"
            )
    
    with tab3:
        st.header("Find Companies for a Law Firm")
    
        # Single row layout: Firm name, From date, To date
        col1, col2, col3 = st.columns([3, 1, 1])
    
        with col1:
            firm_name = st.text_input(
                "Law Firm Name",
                placeholder="e.g., Cooley LLP, Latham & Watkins",
                key="firm_name"
            )
    
        with col2:
            firm_start_date = st.date_input(
                "From",
                value=pd.Timestamp.now() - pd.DateOffset(years=1),
                max_value=pd.Timestamp.now(),
                key="firm_start_date"
            )
    
        with col3:
            firm_end_date = st.date_input(
                "To",
                value=pd.Timestamp.now(),
                max_value=pd.Timestamp.now(),
                key="firm_end_date"
            )
    
        if st.button("Search Law Firm", type="primary"):
            if not firm_name:
                st.error("Please enter a law firm name")
            elif firm_start_date >= firm_end_date:
                st.error("Start date must be before end date")
            else:
                with st.spinner("Searching SEC filings..."):
                    # Single status container that updates
                    status_placeholder = st.empty()
    
                    def progress_callback(message):
                        status_placeholder.info(message)
    
                    try:
                        result_df = search_law_firm_for_companies(
                            firm_name.strip(),
                            firm_start_date,
                            firm_end_date,
                            progress_callback
                        )
    
                        status_placeholder.empty()
    
                        # Store results in session state
                        st.session_state.firm_results = {
                            'df': result_df,
                            'filename': f"{firm_name.lower().replace(' ', '_').replace('&', 'and')}_companies.csv"
                        }
    
                    except Exception as e:
                        status_placeholder.empty()
                        st.error(f"Error: {str(e)}")
                        st.session_state.firm_results = None
    
        # Display stored results if they exist
        if st.session_state.firm_results is not None:
            result_df = st.session_state.firm_results['df']
            st.success(f"Found {len(result_df)} results")
            st.dataframe(result_df, use_container_width=True, hide_index=True)
    
            csv = result_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=st.session_state.firm_results['filename'],
                mime="text/csv",
                key="firm_csv_download"
            )

elif page == "Stock Loan Availability":
    st.markdown("Real-time stock loan availability data from Interactive Brokers")

    if st.button("Fetch Latest Data", type="primary"):
        with st.spinner("Fetching data from Interactive Brokers FTP..."):
            try:
                df = fetch_shortstock_data()

                # Store results in session state
                st.session_state.stock_loan_results = {
                    'df': df,
                    'date': df['Date'].iloc[0],
                    'time': df['Time'].iloc[0]
                }

            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.session_state.stock_loan_results = None

    # Display stored results if they exist
    if st.session_state.stock_loan_results is not None:
        result_df = st.session_state.stock_loan_results['df']
        data_date = st.session_state.stock_loan_results['date']
        data_time = st.session_state.stock_loan_results['time']

        st.success(f"Successfully loaded {len(result_df):,} records")
        st.info(f"Data as of: {data_date} {data_time}")

        # Display the dataframe
        st.dataframe(result_df, use_container_width=True, hide_index=True)

        # Download button
        csv = result_df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"stock_loan_availability_{data_date.replace('/', '_')}.csv",
            mime="text/csv",
            key="stock_loan_csv_download"
        )

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.9rem; padding: 1rem;'>
B. Dyson Capital Advisors | Data sourced from SEC EDGAR
</div>
""", unsafe_allow_html=True)
