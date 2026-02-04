import streamlit as st
import pandas as pd
from search_modules import (
    search_company_for_lawyers,
    search_lawyer_for_companies,
    search_law_firm_for_companies
)
from search_modules.company_search import load_all_companies
from search_modules.stock_loan import fetch_shortstock_data, fetch_shortstock_with_market_cap

st.set_page_config(
    page_title="BDCA Screening Tool",
    page_icon="⚖️",
    layout="wide"
)

page = st.sidebar.radio(
    "Navigation",
    ["Legal Counsel Finder", "Stock Loan Availability"],
    index=0
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

preset_options = ["Last 30 days", "Last year", "Last 3 years", "Last 5 years", "Last 10 years", "All (since 2001)", "Custom"]

if page == "Legal Counsel Finder":
    st.title("Legal Counsel Finder")
    st.markdown("Search SEC EDGAR filings to find relationships between companies, law firms, and lawyers")

    tab1, tab2, tab3 = st.tabs(["Search Company", "Search Lawyer", "Search Law Firm"])

    with tab1:
        st.header("Find Lawyers for a Company")

        # Load companies for autocomplete
        companies = load_all_companies()

        # Single row layout: Company selector, Date Range dropdown, From date, To date
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

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
            company_preset = st.selectbox(
                "Date Range",
                options=preset_options,
                index=3,  # Default to "Last 5 years"
                key="company_preset_sel"
            )

        # Calculate dates based on preset
        if company_preset != "Custom":
            company_start_date, company_end_date = get_date_range(company_preset)
        else:
            company_start_date = (pd.Timestamp.now() - pd.DateOffset(years=5)).date()
            company_end_date = pd.Timestamp.now().date()

        with col3:
            company_start = st.date_input(
                "From",
                value=company_start_date,
                max_value=pd.Timestamp.now(),
                disabled=(company_preset != "Custom"),
                key="company_from"
            )

        with col4:
            company_end = st.date_input(
                "To",
                value=company_end_date,
                max_value=pd.Timestamp.now(),
                disabled=(company_preset != "Custom"),
                key="company_to"
            )

        # Search button with fixed width
        col_btn1, col_btn2 = st.columns([1, 6])
        with col_btn1:
            search_clicked = st.button("Search Company", type="primary", use_container_width=True)

        if search_clicked:
            if not selected_company:
                st.error("Please select a company from the dropdown")
            elif not get_api_key():
                st.error("API key not configured. Please contact your administrator.")
            else:
                # Use calculated dates when preset is not Custom, otherwise use widget values
                if company_preset != "Custom":
                    search_start = company_start_date
                    search_end = company_end_date
                else:
                    search_start = company_start
                    search_end = company_end

                if search_start >= search_end:
                    st.error("Start date must be before end date")
                else:
                    with st.spinner("Searching SEC filings..."):
                        status_placeholder = st.empty()

                        def progress_callback(message):
                            status_placeholder.info(message)

                        try:
                            result_df = search_company_for_lawyers(
                                selected_company['display'],
                                search_start,
                                search_end,
                                get_api_key(),
                                progress_callback,
                                cik=selected_company['cik'],
                                company_name=selected_company['name']
                            )

                            status_placeholder.empty()

                            st.session_state.company_results = {
                                'df': result_df,
                                'filename': f"{selected_company['ticker'] or selected_company['cik']}_lawyers.csv",
                                'search_start': search_start,
                                'search_end': search_end
                            }

                        except Exception as e:
                            status_placeholder.empty()
                            st.error(f"Error: {str(e)}")
                            st.session_state.company_results = None

        # Display stored results if they exist
        if st.session_state.company_results is not None:
            result_df = st.session_state.company_results['df']
            search_start = st.session_state.company_results.get('search_start')
            search_end = st.session_state.company_results.get('search_end')

            if search_start and search_end:
                # Format dates for display
                start_str = search_start.strftime('%Y/%m/%d') if hasattr(search_start, 'strftime') else str(search_start)
                end_str = search_end.strftime('%Y/%m/%d') if hasattr(search_end, 'strftime') else str(search_end)
                st.success(f"Found {len(result_df)} results from {start_str} to {end_str}")
            else:
                st.success(f"Found {len(result_df)} results")

            # Configure number formatting for display
            column_config = {}
            if 'Market Cap' in result_df.columns:
                column_config['Market Cap'] = st.column_config.NumberColumn(
                    'Market Cap',
                    format='%,.2f'
                )
            if 'Available' in result_df.columns:
                column_config['Available'] = st.column_config.NumberColumn(
                    'Available',
                    format='%,.0f'
                )

            st.dataframe(result_df, use_container_width=True, hide_index=True, column_config=column_config)

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

        # Single row layout: Lawyer name, Date Range dropdown, From date, To date
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

        with col1:
            lawyer_name = st.text_input(
                "Lawyer Name",
                placeholder="E.g. John Smith",
                key="lawyer_name"
            )

        with col2:
            lawyer_preset = st.selectbox(
                "Date Range",
                options=preset_options,
                index=3,  # Default to "Last 5 years"
                key="lawyer_preset_sel"
            )

        # Calculate dates based on preset
        if lawyer_preset != "Custom":
            lawyer_start_date, lawyer_end_date = get_date_range(lawyer_preset)
        else:
            lawyer_start_date = (pd.Timestamp.now() - pd.DateOffset(years=5)).date()
            lawyer_end_date = pd.Timestamp.now().date()

        with col3:
            lawyer_start = st.date_input(
                "From",
                value=lawyer_start_date,
                max_value=pd.Timestamp.now(),
                disabled=(lawyer_preset != "Custom"),
                key="lawyer_from"
            )

        with col4:
            lawyer_end = st.date_input(
                "To",
                value=lawyer_end_date,
                max_value=pd.Timestamp.now(),
                disabled=(lawyer_preset != "Custom"),
                key="lawyer_to"
            )

        # Search button with fixed width
        col_btn1, col_btn2 = st.columns([1, 6])
        with col_btn1:
            lawyer_search_clicked = st.button("Search Lawyer", type="primary", use_container_width=True)

        if lawyer_search_clicked:
            if not lawyer_name:
                st.error("Please enter a lawyer name")
            else:
                # Use calculated dates when preset is not Custom, otherwise use widget values
                if lawyer_preset != "Custom":
                    search_start = lawyer_start_date
                    search_end = lawyer_end_date
                else:
                    search_start = lawyer_start
                    search_end = lawyer_end

                if search_start >= search_end:
                    st.error("Start date must be before end date")
                else:
                    with st.spinner("Searching SEC filings..."):
                        status_placeholder = st.empty()

                        def progress_callback(message):
                            status_placeholder.info(message)

                        try:
                            result_df = search_lawyer_for_companies(
                                lawyer_name.strip(),
                                search_start,
                                search_end,
                                progress_callback
                            )

                            status_placeholder.empty()

                            st.session_state.lawyer_results = {
                                'df': result_df,
                                'filename': f"{lawyer_name.lower().replace(' ', '_')}_companies.csv",
                                'search_start': search_start,
                                'search_end': search_end
                            }

                        except Exception as e:
                            status_placeholder.empty()
                            st.error(f"Error: {str(e)}")
                            st.session_state.lawyer_results = None

        # Display stored results if they exist
        if st.session_state.lawyer_results is not None:
            result_df = st.session_state.lawyer_results['df']
            search_start = st.session_state.lawyer_results.get('search_start')
            search_end = st.session_state.lawyer_results.get('search_end')

            if search_start and search_end:
                # Format dates for display
                start_str = search_start.strftime('%Y/%m/%d') if hasattr(search_start, 'strftime') else str(search_start)
                end_str = search_end.strftime('%Y/%m/%d') if hasattr(search_end, 'strftime') else str(search_end)
                st.success(f"Found {len(result_df)} results from {start_str} to {end_str}")
            else:
                st.success(f"Found {len(result_df)} results")

            # Configure number formatting for display
            column_config = {}
            if 'Market Cap' in result_df.columns:
                column_config['Market Cap'] = st.column_config.NumberColumn(
                    'Market Cap',
                    format='%,.2f'
                )
            if 'Available' in result_df.columns:
                column_config['Available'] = st.column_config.NumberColumn(
                    'Available',
                    format='%,.0f'
                )

            st.dataframe(result_df, use_container_width=True, hide_index=True, column_config=column_config)

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

        # Single row layout: Firm name, Date Range dropdown, From date, To date
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

        with col1:
            firm_name = st.text_input(
                "Law Firm Name",
                placeholder="E.g. Cooley LLP, Latham & Watkins",
                key="firm_name"
            )

        with col2:
            firm_preset = st.selectbox(
                "Date Range",
                options=preset_options,
                index=1,  # Default to "Last year"
                key="firm_preset_sel"
            )

        # Calculate dates based on preset
        if firm_preset != "Custom":
            firm_start_date, firm_end_date = get_date_range(firm_preset)
        else:
            firm_start_date = (pd.Timestamp.now() - pd.DateOffset(years=1)).date()
            firm_end_date = pd.Timestamp.now().date()

        with col3:
            firm_start = st.date_input(
                "From",
                value=firm_start_date,
                max_value=pd.Timestamp.now(),
                disabled=(firm_preset != "Custom"),
                key="firm_from"
            )

        with col4:
            firm_end = st.date_input(
                "To",
                value=firm_end_date,
                max_value=pd.Timestamp.now(),
                disabled=(firm_preset != "Custom"),
                key="firm_to"
            )

        # Search button with fixed width
        col_btn1, col_btn2 = st.columns([1, 6])
        with col_btn1:
            firm_search_clicked = st.button("Search Law Firm", type="primary", use_container_width=True)

        if firm_search_clicked:
            if not firm_name:
                st.error("Please enter a law firm name")
            else:
                # Use calculated dates when preset is not Custom, otherwise use widget values
                if firm_preset != "Custom":
                    search_start = firm_start_date
                    search_end = firm_end_date
                else:
                    search_start = firm_start
                    search_end = firm_end

                if search_start >= search_end:
                    st.error("Start date must be before end date")
                else:
                    with st.spinner("Searching SEC filings..."):
                        status_placeholder = st.empty()

                        def progress_callback(message):
                            status_placeholder.info(message)

                        try:
                            result_df = search_law_firm_for_companies(
                                firm_name.strip(),
                                search_start,
                                search_end,
                                progress_callback
                            )

                            status_placeholder.empty()

                            st.session_state.firm_results = {
                                'df': result_df,
                                'filename': f"{firm_name.lower().replace(' ', '_').replace('&', 'and')}_companies.csv",
                                'search_start': search_start,
                                'search_end': search_end
                            }

                        except Exception as e:
                            status_placeholder.empty()
                            st.error(f"Error: {str(e)}")
                            st.session_state.firm_results = None

        # Display stored results if they exist
        if st.session_state.firm_results is not None:
            result_df = st.session_state.firm_results['df']
            search_start = st.session_state.firm_results.get('search_start')
            search_end = st.session_state.firm_results.get('search_end')

            if search_start and search_end:
                # Format dates for display
                start_str = search_start.strftime('%Y/%m/%d') if hasattr(search_start, 'strftime') else str(search_start)
                end_str = search_end.strftime('%Y/%m/%d') if hasattr(search_end, 'strftime') else str(search_end)
                st.success(f"Found {len(result_df)} results from {start_str} to {end_str}")
            else:
                st.success(f"Found {len(result_df)} results")

            # Configure number formatting for display
            column_config = {}
            if 'Market Cap' in result_df.columns:
                column_config['Market Cap'] = st.column_config.NumberColumn(
                    'Market Cap',
                    format='%,.2f'
                )
            if 'Available' in result_df.columns:
                column_config['Available'] = st.column_config.NumberColumn(
                    'Available',
                    format='%,.0f'
                )

            st.dataframe(result_df, use_container_width=True, hide_index=True, column_config=column_config)

            csv = result_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=st.session_state.firm_results['filename'],
                mime="text/csv",
                key="firm_csv_download"
            )

    # Footer for Legal Counsel Finder page
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.9rem; padding: 1rem;'>
    B. Dyson Capital Advisors | Data sourced from SEC EDGAR
    </div>
    """, unsafe_allow_html=True)

elif page == "Stock Loan Availability":
    st.title("Stock Loan Availability")
    st.markdown("Real-time stock loan availability data from Interactive Brokers - Filtered by legitimate stocks in reference file")

    if st.button("Fetch Latest Data", type="primary"):
        with st.spinner("Fetching data from Interactive Brokers FTP and merging with market cap data..."):
            try:
                # Use new function that filters by reference file and adds market cap
                df = fetch_shortstock_with_market_cap()

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

        st.success(f"Successfully loaded {len(result_df):,} records (filtered by reference stocks)")
        st.info(f"Data as of: {data_date} {data_time}")

        # Configure number formatting for display
        column_config = {}
        if 'Market Cap' in result_df.columns:
            column_config['Market Cap'] = st.column_config.NumberColumn(
                'Market Cap',
                format='%,.2f'
            )
        if 'Available' in result_df.columns:
            column_config['Available'] = st.column_config.NumberColumn(
                'Available',
                format='%,.0f'
            )

        st.dataframe(result_df, use_container_width=True, hide_index=True, column_config=column_config)

        csv = result_df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"stock_loan_availability_{data_date.replace('/', '_')}.csv",
            mime="text/csv",
            key="stock_loan_csv_download"
        )

    # Footer for Stock Loan Availability page
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.9rem; padding: 1rem;'>
    B. Dyson Capital Advisors | Data sourced from Interactive Brokers & Stock Reference File
    </div>
    """, unsafe_allow_html=True)
