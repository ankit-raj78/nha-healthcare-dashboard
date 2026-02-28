
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
import re
from datetime import datetime
import altair as alt

# Configure Streamlit page
st.set_page_config(
    page_title="NHA Master Healthcare Facilities Dashboard",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-container {
        background-color: #f0f8ff;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .search-container {
        background-color: #f9f9f9;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    """Load the NHA Master dataset"""
    try:
        df = pd.read_csv('NHA_Master_merged_TEST.csv')

        # Clean and prepare data
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')

        # Remove rows with invalid coordinates
        df = df.dropna(subset=['Latitude', 'Longitude'])

        # Filter out obviously incorrect coordinates
        df = df[
            (df['Latitude'].between(-90, 90)) & 
            (df['Longitude'].between(-180, 180))
        ]

        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

@st.cache_resource
def initialize_search_engine(df):
    """Initialize the natural language search engine"""
    try:
        # Use a lightweight sentence transformer model
        model = SentenceTransformer('all-MiniLM-L6-v2')

        # Create searchable text from facility information
        search_texts = []
        for _, row in df.iterrows():
            text_parts = []
            if pd.notna(row.get('Name')):
                text_parts.append(str(row['Name']))
            if pd.notna(row.get('Address')):
                text_parts.append(str(row['Address']))
            if pd.notna(row.get('Facility Type')):
                text_parts.append(str(row['Facility Type']))
            if pd.notna(row.get('Ownership')):
                text_parts.append(str(row['Ownership']))

            search_text = ' '.join(text_parts)
            search_texts.append(search_text)

        # Create embeddings
        embeddings = model.encode(search_texts)

        # Create FAISS index
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)  # Inner product (cosine similarity)

        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        index.add(embeddings.astype('float32'))

        return model, index, search_texts
    except Exception as e:
        st.error(f"Error initializing search engine: {e}")
        return None, None, None

def natural_language_search(query, model, index, search_texts, df, top_k=100):
    """Perform natural language search"""
    if not query.strip():
        return df.head(100)  # Return top 100 if no query

    try:
        # Encode the query
        query_embedding = model.encode([query])
        faiss.normalize_L2(query_embedding)

        # Search
        scores, indices = index.search(query_embedding.astype('float32'), min(top_k, len(df)))

        # Get results
        result_indices = indices[0]
        result_scores = scores[0]

        # Filter out very low scores
        valid_results = result_scores > 0.3
        result_indices = result_indices[valid_results]
        result_scores = result_scores[valid_results]

        if len(result_indices) == 0:
            return df.head(0)  # Return empty DataFrame

        # Return matching rows
        results_df = df.iloc[result_indices].copy()
        results_df['relevance_score'] = result_scores

        return results_df.sort_values('relevance_score', ascending=False)

    except Exception as e:
        st.error(f"Search error: {e}")
        return df.head(100)

def create_map(df_filtered):
    """Create an interactive map"""
    if df_filtered.empty:
        return None

    # Sample data if too large for performance
    if len(df_filtered) > 1000:
        df_map = df_filtered.sample(1000)
        st.info(f"Showing 1000 random facilities out of {len(df_filtered)} for map performance")
    else:
        df_map = df_filtered

    # Calculate center
    center_lat = df_map['Latitude'].mean()
    center_lon = df_map['Longitude'].mean()

    # Create map
    m = folium.Map(location=[center_lat, center_lon], zoom_start=6)

    # Add markers with different colors for different facility types
    facility_colors = {
        'Hospital': 'red',
        'Primary Health Centre': 'blue',
        'Community Health Centre': 'green',
        'Sub Centre': 'orange',
        'Pharmacy': 'purple',
        'Clinic/ Dispensary': 'darkred',
        'Default': 'gray'
    }

    for _, row in df_map.iterrows():
        color = facility_colors.get(row['Facility Type'], facility_colors['Default'])

        popup_text = f"""
        <b>{row['Name']}</b><br>
        Type: {row['Facility Type']}<br>
        Ownership: {row['Ownership']}<br>
        Address: {row['Address'][:100]}...
        """

        folium.Marker(
            [row['Latitude'], row['Longitude']],
            popup=folium.Popup(popup_text, max_width=300),
            tooltip=row['Name'],
            icon=folium.Icon(color=color)
        ).add_to(m)

    return m

def main():
    """Main dashboard function"""
    # Header
    st.markdown('<h1 class="main-header">🏥 NHA Master Healthcare Facilities Dashboard</h1>', 
                unsafe_allow_html=True)

    # Load data
    with st.spinner("Loading healthcare facilities data..."):
        df = load_data()

    if df is None:
        st.error("Failed to load data. Please check if NHA_Master_merged_TEST.csv exists.")
        return

    # Initialize search engine
    with st.spinner("Initializing natural language search engine..."):
        model, index, search_texts = initialize_search_engine(df)

    # Sidebar for filters and controls
    st.sidebar.header("🔍 Search & Filters")

    # Natural Language Search
    st.sidebar.markdown("### Natural Language Search")
    search_query = st.sidebar.text_area(
        "Search facilities using natural language:",
        placeholder="e.g., 'government hospitals in Mumbai', 'private clinics near Delhi', 'community health centers'",
        height=100
    )

    # Perform search
    if model is not None and index is not None:
        if search_query.strip():
            with st.spinner("Searching..."):
                df_filtered = natural_language_search(search_query, model, index, search_texts, df)
            st.sidebar.success(f"Found {len(df_filtered)} matching facilities")
        else:
            df_filtered = df
    else:
        df_filtered = df
        st.sidebar.warning("Search engine not available, showing all data")

    # Additional filters
    st.sidebar.markdown("### Additional Filters")

    # Facility Type filter
    facility_types = ['All'] + sorted(df['Facility Type'].dropna().unique().tolist())
    selected_type = st.sidebar.selectbox("Facility Type:", facility_types)

    # Ownership filter
    ownership_types = ['All'] + sorted(df['Ownership'].dropna().unique().tolist())
    selected_ownership = st.sidebar.selectbox("Ownership:", ownership_types)

    # Apply additional filters
    if selected_type != 'All':
        df_filtered = df_filtered[df_filtered['Facility Type'] == selected_type]

    if selected_ownership != 'All':
        df_filtered = df_filtered[df_filtered['Ownership'] == selected_ownership]

    # Main dashboard content
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        st.metric("Total Facilities", f"{len(df_filtered):,}")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        st.metric("Facility Types", df_filtered['Facility Type'].nunique())
        st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        gov_facilities = len(df_filtered[df_filtered['Ownership'] == 'Government'])
        st.metric("Government Facilities", f"{gov_facilities:,}")
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        private_facilities = len(df_filtered[df_filtered['Ownership'] == 'Private'])
        st.metric("Private Facilities", f"{private_facilities:,}")
        st.markdown('</div>', unsafe_allow_html=True)

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📍 Map View", "📊 Analytics", "📋 Data Table", "🔍 Search Results"])

    with tab1:
        st.subheader("Interactive Map of Healthcare Facilities")

        if not df_filtered.empty:
            map_obj = create_map(df_filtered)
            if map_obj:
                st_folium(map_obj, width=1200, height=600)
        else:
            st.info("No facilities to display on map")

    with tab2:
        st.subheader("Healthcare Facilities Analytics")

        if not df_filtered.empty:
            col1, col2 = st.columns(2)

            with col1:
                # Facility Type Distribution
                facility_counts = df_filtered['Facility Type'].value_counts().head(10)
                fig1 = px.bar(
                    x=facility_counts.values,
                    y=facility_counts.index,
                    orientation='h',
                    title="Top 10 Facility Types",
                    labels={'x': 'Count', 'y': 'Facility Type'}
                )
                fig1.update_layout(height=400)
                st.plotly_chart(fig1, use_container_width=True)

            with col2:
                # Ownership Distribution
                ownership_counts = df_filtered['Ownership'].value_counts()
                fig2 = px.pie(
                    values=ownership_counts.values,
                    names=ownership_counts.index,
                    title="Facility Ownership Distribution"
                )
                fig2.update_layout(height=400)
                st.plotly_chart(fig2, use_container_width=True)

            # ABDM Enabled Analysis
            if 'ABDM Enabled' in df_filtered.columns:
                abdm_counts = df_filtered['ABDM Enabled'].value_counts()
                fig3 = px.bar(
                    x=abdm_counts.index,
                    y=abdm_counts.values,
                    title="ABDM Enabled Facilities",
                    labels={'x': 'ABDM Status', 'y': 'Count'}
                )
                st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No data available for analytics")

    with tab3:
        st.subheader("Facilities Data Table")

        if not df_filtered.empty:
            # Show top results with relevance score if search was performed
            display_df = df_filtered.copy()

            # Select relevant columns for display
            display_columns = ['Name', 'Facility Type', 'Ownership', 'Address', 'Latitude', 'Longitude']
            if 'relevance_score' in display_df.columns:
                display_columns.append('relevance_score')
                display_df = display_df.sort_values('relevance_score', ascending=False)

            display_df = display_df[display_columns].head(1000)  # Limit to 1000 rows for performance

            st.dataframe(
                display_df,
                use_container_width=True,
                height=600
            )

            # Download button
            csv = display_df.to_csv(index=False)
            st.download_button(
                label="Download filtered data as CSV",
                data=csv,
                file_name=f"nha_facilities_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No facilities match the current filters")

    with tab4:
        st.subheader("Search Results Analysis")

        if search_query.strip() and not df_filtered.empty:
            st.write(f"**Search Query:** {search_query}")
            st.write(f"**Results Found:** {len(df_filtered)} facilities")

            if 'relevance_score' in df_filtered.columns:
                # Show relevance score distribution
                fig = px.histogram(
                    df_filtered,
                    x='relevance_score',
                    title="Relevance Score Distribution",
                    nbins=20
                )
                st.plotly_chart(fig, use_container_width=True)

                # Show top matches
                st.subheader("Top 10 Most Relevant Results")
                top_results = df_filtered.head(10)[['Name', 'Facility Type', 'Address', 'relevance_score']]
                st.dataframe(top_results, use_container_width=True)
        else:
            st.info("Enter a search query to see detailed search results analysis")

    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #666; padding: 1rem;'>"
        "NHA Master Healthcare Facilities Dashboard | "
        f"Data as of {datetime.now().strftime('%B %Y')} | "
        f"Total facilities in database: {len(df):,}"
        "</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
