"""
Main Streamlit Application for NHA Healthcare Facilities Dashboard
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import custom modules
from components.search_engine import SearchEngine
from components.map_visualizer import MapVisualizer
from components.analytics_dashboard import AnalyticsDashboard
from utils.data_loader import DataLoader
from utils.constants import APP_CONFIG
from config.settings import DASHBOARD_CONFIG


def configure_page() -> None:
    """Configure Streamlit page settings"""
    st.set_page_config(
        page_title="NHA Healthcare Facilities Dashboard",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'About': "NHA Healthcare Facilities Dashboard - Comprehensive analysis and visualization of healthcare infrastructure across India"
        }
    )


def load_custom_css() -> None:
    """Load custom CSS styling"""
    css = """
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: 600;
    }
    .metric-container {
        background: linear-gradient(90deg, #f0f8ff 0%, #e6f3ff 100%);
        padding: 1.5rem;
        border-radius: 0.75rem;
        border-left: 4px solid #1f77b4;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    .search-container {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 0.75rem;
        margin: 1rem 0;
        border: 1px solid #e9ecef;
    }
    .stTab {
        font-weight: 600;
    }
    .info-box {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


@st.cache_data
def load_data() -> Optional[pd.DataFrame]:
    """Load and cache the healthcare facilities dataset"""
    try:
        data_loader = DataLoader()
        df = data_loader.load_master_dataset()
        
        if df is not None:
            logger.info(f"Successfully loaded {len(df):,} healthcare facilities")
            return df
        else:
            st.error("Failed to load healthcare facilities data")
            return None
            
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        st.error(f"Error loading data: {e}")
        return None


@st.cache_resource
def initialize_search_engine(df: pd.DataFrame) -> Optional[SearchEngine]:
    """Initialize and cache the natural language search engine"""
    try:
        search_engine = SearchEngine()
        search_engine.initialize(df)
        logger.info("Search engine initialized successfully")
        return search_engine
    except Exception as e:
        logger.error(f"Error initializing search engine: {e}")
        st.error(f"Search engine initialization failed: {e}")
        return None


def render_header() -> None:
    """Render the main dashboard header"""
    st.markdown(
        '<h1 class="main-header">🏥 NHA Healthcare Facilities Dashboard</h1>', 
        unsafe_allow_html=True
    )
    
    st.markdown(
        """
        <div style="text-align: center; margin-bottom: 2rem; color: #666;">
        Comprehensive analysis and visualization of healthcare infrastructure across India
        </div>
        """,
        unsafe_allow_html=True
    )


def render_sidebar(df: pd.DataFrame, search_engine: Optional[SearchEngine]) -> Dict[str, Any]:
    """Render sidebar controls and return filter selections"""
    st.sidebar.header("🔍 Search & Filters")
    
    filters = {}
    
    # Natural Language Search
    st.sidebar.markdown("### 🤖 Natural Language Search")
    search_query = st.sidebar.text_area(
        "Describe what you're looking for:",
        placeholder="e.g., 'government hospitals in Maharashtra', 'private clinics with ABDM', 'community health centers in rural areas'",
        height=100,
        help="Use natural language to search for specific types of facilities, locations, or characteristics"
    )
    filters['search_query'] = search_query
    
    # Quick Search Examples
    if st.sidebar.button("🏥 Government Hospitals"):
        filters['search_query'] = "government hospitals"
    if st.sidebar.button("🏩 Private Clinics"):
        filters['search_query'] = "private clinics"
    if st.sidebar.button("🏢 Community Health Centers"):
        filters['search_query'] = "community health centers"
    
    st.sidebar.markdown("---")
    
    # Traditional Filters
    st.sidebar.markdown("### 🎛️ Filter Options")
    
    # Facility Type
    facility_types = ['All'] + sorted(df['Facility Type'].dropna().unique().tolist())
    filters['facility_type'] = st.sidebar.selectbox(
        "🏥 Facility Type:", 
        facility_types,
        help="Filter by specific type of healthcare facility"
    )
    
    # Ownership
    ownership_types = ['All'] + sorted(df['Ownership'].dropna().unique().tolist())
    filters['ownership'] = st.sidebar.selectbox(
        "🏛️ Ownership:", 
        ownership_types,
        help="Filter by facility ownership type"
    )
    
    # State filter (if state column exists)
    if 'State' in df.columns:
        states = ['All'] + sorted(df['State'].dropna().unique().tolist())
        filters['state'] = st.sidebar.selectbox(
            "🗺️ State:", 
            states,
            help="Filter by state/region"
        )
    
    # ABDM filter (if available)
    if 'ABDM Enabled' in df.columns:
        abdm_options = ['All', 'Yes', 'No']
        filters['abdm_enabled'] = st.sidebar.selectbox(
            "📱 ABDM Enabled:", 
            abdm_options,
            help="Filter by ABDM (Ayushman Bharat Digital Mission) enablement"
        )
    
    return filters


def apply_filters(df: pd.DataFrame, filters: Dict[str, Any], search_engine: Optional[SearchEngine]) -> pd.DataFrame:
    """Apply all filters to the dataframe"""
    df_filtered = df.copy()
    
    # Apply natural language search
    if filters['search_query'].strip() and search_engine:
        with st.spinner("🔍 Searching..."):
            df_filtered = search_engine.search(filters['search_query'], df_filtered)
            st.sidebar.success(f"Found {len(df_filtered):,} matching facilities")
    
    # Apply traditional filters
    if filters['facility_type'] != 'All':
        df_filtered = df_filtered[df_filtered['Facility Type'] == filters['facility_type']]
    
    if filters['ownership'] != 'All':
        df_filtered = df_filtered[df_filtered['Ownership'] == filters['ownership']]
    
    if 'state' in filters and filters['state'] != 'All':
        df_filtered = df_filtered[df_filtered['State'] == filters['state']]
    
    if 'abdm_enabled' in filters and filters['abdm_enabled'] != 'All':
        df_filtered = df_filtered[df_filtered['ABDM Enabled'] == filters['abdm_enabled']]
    
    return df_filtered


def render_metrics(df_filtered: pd.DataFrame, df_total: pd.DataFrame) -> None:
    """Render key metrics in columns"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        st.metric(
            "Total Facilities", 
            f"{len(df_filtered):,}",
            delta=f"of {len(df_total):,} total"
        )
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        st.metric(
            "Facility Types", 
            df_filtered['Facility Type'].nunique()
        )
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        gov_facilities = len(df_filtered[df_filtered['Ownership'] == 'Government'])
        st.metric(
            "Government", 
            f"{gov_facilities:,}",
            delta=f"{gov_facilities/len(df_filtered)*100:.1f}%" if len(df_filtered) > 0 else "0%"
        )
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        private_facilities = len(df_filtered[df_filtered['Ownership'] == 'Private'])
        st.metric(
            "Private", 
            f"{private_facilities:,}",
            delta=f"{private_facilities/len(df_filtered)*100:.1f}%" if len(df_filtered) > 0 else "0%"
        )
        st.markdown('</div>', unsafe_allow_html=True)


def main() -> None:
    """Main application function"""
    # Configure page
    configure_page()
    load_custom_css()
    
    # Render header
    render_header()
    
    # Load data
    with st.spinner("📊 Loading healthcare facilities data..."):
        df = load_data()
    
    if df is None:
        st.error("❌ Unable to load data. Please check the data source and try again.")
        return
    
    # Initialize search engine
    with st.spinner("🔍 Initializing natural language search..."):
        search_engine = initialize_search_engine(df)
    
    # Render sidebar and get filters
    filters = render_sidebar(df, search_engine)
    
    # Apply filters
    df_filtered = apply_filters(df, filters, search_engine)
    
    # Render metrics
    render_metrics(df_filtered, df)
    
    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📍 Interactive Map", "📊 Analytics", "📋 Data Explorer", "🔍 Search Insights"])
    
    with tab1:
        st.subheader("🗺️ Healthcare Facilities Map")
        if not df_filtered.empty:
            map_viz = MapVisualizer()
            map_obj = map_viz.create_facility_map(df_filtered)
            if map_obj:
                st_folium(map_obj, width=1200, height=600)
        else:
            st.info("No facilities match the current filters")
    
    with tab2:
        st.subheader("📈 Analytics Dashboard")
        if not df_filtered.empty:
            analytics = AnalyticsDashboard()
            analytics.render_analytics(df_filtered)
        else:
            st.info("No data available for analytics")
    
    with tab3:
        st.subheader("📋 Facility Data")
        if not df_filtered.empty:
            # Data table with enhanced features
            st.dataframe(
                df_filtered.head(1000),  # Limit for performance
                use_container_width=True,
                height=400
            )
            
            # Download button
            csv = df_filtered.to_csv(index=False)
            st.download_button(
                label="📥 Download Filtered Data (CSV)",
                data=csv,
                file_name=f"nha_facilities_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No facilities match the current filters")
    
    with tab4:
        st.subheader("🔍 Search Analysis")
        if filters['search_query'].strip() and not df_filtered.empty:
            st.write(f"**Search Query:** {filters['search_query']}")
            st.write(f"**Results:** {len(df_filtered):,} facilities found")
            
            # Search results analysis would go here
            if 'relevance_score' in df_filtered.columns:
                fig = px.histogram(
                    df_filtered,
                    x='relevance_score',
                    title="Search Relevance Distribution",
                    nbins=20
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Enter a search query to see detailed analysis")
    
    # Footer
    st.markdown("---")
    st.markdown(
        f"""
        <div style='text-align: center; color: #666; padding: 1rem;'>
        <b>NHA Healthcare Facilities Dashboard</b> | 
        Data updated: {pd.Timestamp.now().strftime('%B %Y')} | 
        Total facilities: {len(df):,}
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
