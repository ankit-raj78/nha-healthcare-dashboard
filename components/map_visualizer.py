"""
Map Visualization Component for Healthcare Facilities
"""

import pandas as pd
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

try:
    import folium
    from folium import plugins
    MAP_AVAILABLE = True
except ImportError:
    logger.warning("Folium not available. Map functionality will be limited.")
    MAP_AVAILABLE = False


class MapVisualizer:
    """Creates interactive maps for healthcare facilities"""
    
    def __init__(self):
        """Initialize the map visualizer"""
        self.facility_colors = {
            'Hospital': '#e74c3c',  # Red
            'Primary Health Centre': '#3498db',  # Blue
            'Community Health Centre': '#2ecc71',  # Green
            'Sub Centre': '#f39c12',  # Orange
            'Pharmacy': '#9b59b6',  # Purple
            'Clinic/ Dispensary': '#e67e22',  # Dark Orange
            'Default': '#95a5a6'  # Gray
        }
        
        self.ownership_colors = {
            'Government': '#27ae60',  # Green
            'Private': '#8e44ad',  # Purple
            'PPP': '#f39c12',  # Orange
            'Default': '#7f8c8d'  # Gray
        }
    
    def create_facility_map(self, df: pd.DataFrame, color_by: str = 'facility_type') -> Optional[Any]:
        """Create an interactive map of healthcare facilities"""
        if not MAP_AVAILABLE:
            logger.error("Folium not available for map creation")
            return None
        
        if df.empty:
            logger.warning("No data provided for map creation")
            return None
        
        try:
            # Sample data if too large for performance
            df_map = self._sample_data_for_map(df)
            
            # Calculate map center
            center_lat = df_map['Latitude'].mean()
            center_lon = df_map['Longitude'].mean()
            
            # Create base map
            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=6,
                tiles='OpenStreetMap',
                control_scale=True
            )
            
            # Add different tile layers
            folium.TileLayer('CartoDB positron', name='CartoDB Positron').add_to(m)
            folium.TileLayer('CartoDB dark_matter', name='CartoDB Dark').add_to(m)
            
            # Add markers
            self._add_markers(m, df_map, color_by)
            
            # Add layer control
            folium.LayerControl().add_to(m)
            
            # Add marker clusters for better performance
            if len(df_map) > 100:
                self._add_cluster_map(m, df_map, color_by)
            
            # Add legend
            self._add_legend(m, color_by)
            
            logger.info(f"Created map with {len(df_map)} facilities")
            return m
            
        except Exception as e:
            logger.error(f"Error creating map: {e}")
            return None
    
    def _sample_data_for_map(self, df: pd.DataFrame, max_points: int = 2000) -> pd.DataFrame:
        """Sample data for map performance if dataset is too large"""
        if len(df) <= max_points:
            return df
        
        # Sample strategically - try to get representation from different facility types
        sampled_dfs = []
        
        if 'Facility Type' in df.columns:
            facility_types = df['Facility Type'].unique()
            points_per_type = max(1, max_points // len(facility_types))
            
            for facility_type in facility_types:
                type_df = df[df['Facility Type'] == facility_type]
                if len(type_df) > points_per_type:
                    sampled_dfs.append(type_df.sample(points_per_type))
                else:
                    sampled_dfs.append(type_df)
            
            result = pd.concat(sampled_dfs, ignore_index=True)
        else:
            result = df.sample(max_points)
        
        logger.info(f"Sampled {len(result)} facilities from {len(df)} for map display")
        return result
    
    def _add_markers(self, map_obj: Any, df: pd.DataFrame, color_by: str) -> None:
        """Add individual markers to the map"""
        color_mapping = self.facility_colors if color_by == 'facility_type' else self.ownership_colors
        
        for idx, row in df.iterrows():
            # Determine marker color
            if color_by == 'facility_type':
                color_key = row.get('Facility Type', 'Default')
            else:
                color_key = row.get('Ownership', 'Default')
            
            color = color_mapping.get(color_key, color_mapping['Default'])
            
            # Create popup content
            popup_html = self._create_popup_content(row)
            
            # Create marker
            folium.CircleMarker(
                location=[row['Latitude'], row['Longitude']],
                radius=6,
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=row.get('Name', 'Healthcare Facility'),
                color='white',
                fillColor=color,
                fillOpacity=0.8,
                weight=1
            ).add_to(map_obj)
    
    def _add_cluster_map(self, map_obj: Any, df: pd.DataFrame, color_by: str) -> None:
        """Add clustered markers for better performance with large datasets"""
        # Create marker cluster
        marker_cluster = plugins.MarkerCluster(
            name='Clustered Facilities',
            overlay=True,
            control=True
        )
        
        color_mapping = self.facility_colors if color_by == 'facility_type' else self.ownership_colors
        
        for idx, row in df.iterrows():
            # Determine marker color
            if color_by == 'facility_type':
                color_key = row.get('Facility Type', 'Default')
            else:
                color_key = row.get('Ownership', 'Default')
            
            color = color_mapping.get(color_key, color_mapping['Default'])
            
            # Create popup content
            popup_html = self._create_popup_content(row)
            
            # Add marker to cluster
            folium.Marker(
                location=[row['Latitude'], row['Longitude']],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=row.get('Name', 'Healthcare Facility'),
                icon=folium.Icon(color='blue', icon='plus', prefix='fa')
            ).add_to(marker_cluster)
        
        marker_cluster.add_to(map_obj)
    
    def _create_popup_content(self, row: pd.Series) -> str:
        """Create HTML content for facility popup"""
        html = f"""
        <div style="font-family: Arial, sans-serif; width: 250px;">
            <h4 style="margin-bottom: 10px; color: #2c3e50;">
                {row.get('Name', 'Healthcare Facility')}
            </h4>
            
            <div style="margin-bottom: 8px;">
                <strong>Type:</strong> {row.get('Facility Type', 'N/A')}
            </div>
            
            <div style="margin-bottom: 8px;">
                <strong>Ownership:</strong> {row.get('Ownership', 'N/A')}
            </div>
            
            <div style="margin-bottom: 8px;">
                <strong>Address:</strong> {str(row.get('Address', 'N/A'))[:100]}
                {'...' if len(str(row.get('Address', ''))) > 100 else ''}
            </div>
        """
        
        # Add state if available
        if 'State' in row and pd.notna(row['State']):
            html += f"""
            <div style="margin-bottom: 8px;">
                <strong>State:</strong> {row['State']}
            </div>
            """
        
        # Add ABDM status if available
        if 'ABDM Enabled' in row and pd.notna(row['ABDM Enabled']):
            abdm_color = '#27ae60' if str(row['ABDM Enabled']).lower() == 'yes' else '#e74c3c'
            html += f"""
            <div style="margin-bottom: 8px;">
                <strong>ABDM:</strong> 
                <span style="color: {abdm_color}; font-weight: bold;">
                    {row['ABDM Enabled']}
                </span>
            </div>
            """
        
        # Add coordinates
        html += f"""
            <div style="margin-top: 10px; font-size: 11px; color: #7f8c8d;">
                📍 {row['Latitude']:.4f}, {row['Longitude']:.4f}
            </div>
        </div>
        """
        
        return html
    
    def _add_legend(self, map_obj: Any, color_by: str) -> None:
        """Add a legend to the map"""
        if color_by == 'facility_type':
            legend_items = self.facility_colors
            title = "Facility Types"
        else:
            legend_items = self.ownership_colors
            title = "Ownership Types"
        
        legend_html = f"""
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 200px; height: auto; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px; border-radius: 5px;">
            <h4 style="margin-top: 0;">{title}</h4>
        """
        
        for item, color in legend_items.items():
            if item != 'Default':
                legend_html += f"""
                <div style="margin-bottom: 5px;">
                    <span style="background-color: {color}; 
                                 width: 15px; height: 15px; 
                                 display: inline-block; margin-right: 8px;
                                 border-radius: 50%;"></span>
                    {item}
                </div>
                """
        
        legend_html += "</div>"
        
        map_obj.get_root().html.add_child(folium.Element(legend_html))
    
    def create_heatmap(self, df: pd.DataFrame) -> Optional[Any]:
        """Create a heatmap of facility density"""
        if not MAP_AVAILABLE:
            return None
        
        try:
            # Calculate map center
            center_lat = df['Latitude'].mean()
            center_lon = df['Longitude'].mean()
            
            # Create base map
            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=6,
                tiles='OpenStreetMap'
            )
            
            # Prepare data for heatmap
            heat_data = [[row['Latitude'], row['Longitude']] for idx, row in df.iterrows()]
            
            # Add heatmap layer
            plugins.HeatMap(heat_data, radius=15, blur=10).add_to(m)
            
            return m
            
        except Exception as e:
            logger.error(f"Error creating heatmap: {e}")
            return None
