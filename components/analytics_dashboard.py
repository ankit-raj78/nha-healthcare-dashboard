"""
Analytics Dashboard Component for Healthcare Facilities
"""

import pandas as pd
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import streamlit as st
    PLOTLY_AVAILABLE = True
except ImportError:
    logger.warning("Plotly or Streamlit not available. Analytics functionality will be limited.")
    PLOTLY_AVAILABLE = False


class AnalyticsDashboard:
    """Creates analytics visualizations for healthcare facilities data"""
    
    def __init__(self):
        """Initialize the analytics dashboard"""
        self.color_palette = [
            '#3498db', '#e74c3c', '#2ecc71', '#f39c12', 
            '#9b59b6', '#1abc9c', '#e67e22', '#95a5a6'
        ]
    
    def render_analytics(self, df: pd.DataFrame) -> None:
        """Render comprehensive analytics dashboard"""
        if not PLOTLY_AVAILABLE:
            st.error("Analytics not available. Please install required packages.")
            return
        
        if df.empty:
            st.info("No data available for analytics")
            return
        
        try:
            # Create analytics layout
            col1, col2 = st.columns(2)
            
            with col1:
                self._render_facility_type_chart(df)
                self._render_ownership_distribution(df)
            
            with col2:
                self._render_state_distribution(df)
                self._render_abdm_analysis(df)
            
            # Full-width charts
            self._render_facility_ownership_matrix(df)
            self._render_geographic_analysis(df)
            
        except Exception as e:
            logger.error(f"Error rendering analytics: {e}")
            st.error(f"Error in analytics: {e}")
    
    def _render_facility_type_chart(self, df: pd.DataFrame) -> None:
        """Render facility type distribution chart"""
        try:
            if 'Facility Type' not in df.columns:
                return
            
            facility_counts = df['Facility Type'].value_counts().head(10)
            
            fig = px.bar(
                x=facility_counts.values,
                y=facility_counts.index,
                orientation='h',
                title="Top 10 Facility Types",
                labels={'x': 'Number of Facilities', 'y': 'Facility Type'},
                color=facility_counts.values,
                color_continuous_scale='Blues'
            )
            
            fig.update_layout(
                height=400,
                showlegend=False,
                yaxis={'categoryorder': 'total ascending'}
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            logger.error(f"Error creating facility type chart: {e}")
    
    def _render_ownership_distribution(self, df: pd.DataFrame) -> None:
        """Render ownership distribution pie chart"""
        try:
            if 'Ownership' not in df.columns:
                return
            
            ownership_counts = df['Ownership'].value_counts()
            
            fig = px.pie(
                values=ownership_counts.values,
                names=ownership_counts.index,
                title="Facility Ownership Distribution",
                color_discrete_sequence=self.color_palette
            )
            
            fig.update_traces(
                textposition='inside',
                textinfo='percent+label'
            )
            
            fig.update_layout(height=400)
            
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            logger.error(f"Error creating ownership chart: {e}")
    
    def _render_state_distribution(self, df: pd.DataFrame) -> None:
        """Render state-wise facility distribution"""
        try:
            if 'State' not in df.columns:
                # Create a placeholder chart
                fig = go.Figure()
                fig.add_annotation(
                    text="State information not available",
                    x=0.5, y=0.5,
                    showarrow=False,
                    font=dict(size=16)
                )
                fig.update_layout(
                    title="State-wise Distribution",
                    height=400,
                    xaxis=dict(visible=False),
                    yaxis=dict(visible=False)
                )
                st.plotly_chart(fig, use_container_width=True)
                return
            
            state_counts = df['State'].value_counts().head(15)
            
            fig = px.bar(
                x=state_counts.index,
                y=state_counts.values,
                title="Top 15 States by Facility Count",
                labels={'x': 'State', 'y': 'Number of Facilities'},
                color=state_counts.values,
                color_continuous_scale='Greens'
            )
            
            fig.update_layout(
                height=400,
                xaxis_tickangle=-45,
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            logger.error(f"Error creating state distribution chart: {e}")
    
    def _render_abdm_analysis(self, df: pd.DataFrame) -> None:
        """Render ABDM enablement analysis"""
        try:
            if 'ABDM Enabled' not in df.columns:
                # Create a placeholder chart
                fig = go.Figure()
                fig.add_annotation(
                    text="ABDM data not available",
                    x=0.5, y=0.5,
                    showarrow=False,
                    font=dict(size=16)
                )
                fig.update_layout(
                    title="ABDM Enablement Status",
                    height=400,
                    xaxis=dict(visible=False),
                    yaxis=dict(visible=False)
                )
                st.plotly_chart(fig, use_container_width=True)
                return
            
            abdm_counts = df['ABDM Enabled'].value_counts()
            
            colors = ['#e74c3c' if x.lower() == 'no' else '#2ecc71' for x in abdm_counts.index]
            
            fig = px.bar(
                x=abdm_counts.index,
                y=abdm_counts.values,
                title="ABDM Enablement Status",
                labels={'x': 'ABDM Status', 'y': 'Number of Facilities'},
                color=abdm_counts.index,
                color_discrete_map={'Yes': '#2ecc71', 'No': '#e74c3c'}
            )
            
            fig.update_layout(
                height=400,
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            logger.error(f"Error creating ABDM chart: {e}")
    
    def _render_facility_ownership_matrix(self, df: pd.DataFrame) -> None:
        """Render facility type vs ownership matrix"""
        try:
            if 'Facility Type' not in df.columns or 'Ownership' not in df.columns:
                return
            
            # Create cross-tabulation
            matrix = pd.crosstab(df['Facility Type'], df['Ownership'])
            
            fig = px.imshow(
                matrix.values,
                x=matrix.columns,
                y=matrix.index,
                color_continuous_scale='Blues',
                title="Facility Type vs Ownership Matrix",
                labels=dict(color="Count")
            )
            
            # Add text annotations
            for i in range(len(matrix.index)):
                for j in range(len(matrix.columns)):
                    fig.add_annotation(
                        x=j, y=i,
                        text=str(matrix.iloc[i, j]),
                        showarrow=False,
                        font=dict(color="white" if matrix.iloc[i, j] > matrix.values.max()/2 else "black")
                    )
            
            fig.update_layout(height=500)
            
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            logger.error(f"Error creating facility-ownership matrix: {e}")
    
    def _render_geographic_analysis(self, df: pd.DataFrame) -> None:
        """Render geographic analysis if coordinate data is available"""
        try:
            if 'Latitude' not in df.columns or 'Longitude' not in df.columns:
                return
            
            st.subheader("📍 Geographic Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Latitude distribution
                fig = px.histogram(
                    df,
                    x='Latitude',
                    nbins=30,
                    title="Latitude Distribution",
                    labels={'x': 'Latitude', 'y': 'Frequency'}
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Longitude distribution
                fig = px.histogram(
                    df,
                    x='Longitude',
                    nbins=30,
                    title="Longitude Distribution",
                    labels={'x': 'Longitude', 'y': 'Frequency'}
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
            
            # Coordinate scatter plot (sample for performance)
            if len(df) > 1000:
                sample_df = df.sample(1000)
                st.info("Showing 1000 random facilities for coordinate analysis")
            else:
                sample_df = df
            
            if 'Facility Type' in df.columns:
                fig = px.scatter(
                    sample_df,
                    x='Longitude',
                    y='Latitude',
                    color='Facility Type',
                    title="Geographic Distribution of Facilities",
                    hover_data=['Name'] if 'Name' in df.columns else None
                )
            else:
                fig = px.scatter(
                    sample_df,
                    x='Longitude',
                    y='Latitude',
                    title="Geographic Distribution of Facilities"
                )
            
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            logger.error(f"Error creating geographic analysis: {e}")
    
    def generate_summary_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate summary statistics for the dataset"""
        try:
            stats = {
                'total_facilities': len(df),
                'unique_facility_types': df['Facility Type'].nunique() if 'Facility Type' in df.columns else 0,
                'unique_states': df['State'].nunique() if 'State' in df.columns else 0,
                'coverage_area': {
                    'latitude_range': (df['Latitude'].min(), df['Latitude'].max()) if 'Latitude' in df.columns else None,
                    'longitude_range': (df['Longitude'].min(), df['Longitude'].max()) if 'Longitude' in df.columns else None
                }
            }
            
            # Add facility type breakdown
            if 'Facility Type' in df.columns:
                stats['facility_type_breakdown'] = df['Facility Type'].value_counts().to_dict()
            
            # Add ownership breakdown
            if 'Ownership' in df.columns:
                stats['ownership_breakdown'] = df['Ownership'].value_counts().to_dict()
            
            # Add ABDM stats
            if 'ABDM Enabled' in df.columns:
                stats['abdm_stats'] = df['ABDM Enabled'].value_counts().to_dict()
            
            return stats
            
        except Exception as e:
            logger.error(f"Error generating summary statistics: {e}")
            return {}
