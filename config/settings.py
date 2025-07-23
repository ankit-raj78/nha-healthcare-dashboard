"""
Dashboard Settings and Configuration
"""

import os
from pathlib import Path
from typing import Dict, Any

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Dashboard Configuration
DASHBOARD_CONFIG = {
    'title': 'NHA Healthcare Facilities Dashboard',
    'icon': '🏥',
    'subtitle': 'Comprehensive analysis and visualization of healthcare infrastructure across India',
    'layout': 'wide',
    'initial_sidebar_state': 'expanded',
    'menu_items': {
        'About': 'NHA Healthcare Facilities Dashboard - Comprehensive analysis and visualization of healthcare infrastructure across India'
    }
}

# Data settings
DATA_DIR = PROJECT_ROOT / "data"
USE_DEDUPLICATED_DATA = False  # Set to True to use deduplicated dataset by default

# Performance settings
MAX_ROWS_DISPLAY = 1000
MAP_SAMPLE_SIZE = 2000  # Maximum number of points to show on map for performance
SEARCH_RESULTS_LIMIT = 500

# UI settings
SIDEBAR_EXPANDED = True
SHOW_PROGRESS_BAR = True

# Cache settings
CACHE_TTL = 3600  # 1 hour in seconds

# Map settings
DEFAULT_MAP_CENTER = [20.5937, 78.9629]  # India center
DEFAULT_MAP_ZOOM = 5

# Feature flags
ENABLE_ADVANCED_SEARCH = True
ENABLE_DATA_EXPORT = True
ENABLE_MAP_CLUSTERING = True
ENABLE_ANALYTICS_DASHBOARD = True

# Search settings
MIN_SEARCH_LENGTH = 3
SEARCH_DEBOUNCE_MS = 300

# Data Settings
DATA_SETTINGS = {
    'data_directory': PROJECT_ROOT / 'data',
    'master_filename': 'NHA_Master_merged_TEST.csv',
    'backup_locations': [
        Path.cwd() / 'NHA_Master_merged_TEST.csv',
        Path.cwd().parent / 'NHA_Master_merged_TEST.csv',
        Path('/Users/ankitraj2/asar master data/NHA_Master_merged_TEST.csv')
    ],
    'encoding': 'utf-8',
    'coordinate_bounds': {
        'latitude': (-90, 90),
        'longitude': (-180, 180)
    }
}

# Performance Settings
PERFORMANCE_SETTINGS = {
    'max_map_markers': 2000,
    'max_search_results': 500,
    'pagination_size': 1000,
    'cache_ttl': 3600,  # 1 hour
    'enable_clustering': True,
    'cluster_threshold': 100
}

# Search Engine Settings
SEARCH_SETTINGS = {
    'model_name': 'all-MiniLM-L6-v2',
    'similarity_threshold': 0.2,
    'max_results': 500,
    'enable_semantic_search': True,
    'fallback_search': True,
    'search_columns': ['Name', 'Facility Type', 'Ownership', 'Address', 'State'],
    'boost_columns': {
        'Name': 2.0,
        'Facility Type': 1.5,
        'Ownership': 1.2
    }
}

# Visualization Settings
VISUALIZATION_SETTINGS = {
    'default_chart_height': 400,
    'map_height': 600,
    'color_schemes': {
        'primary': '#3498db',
        'secondary': '#2ecc71',
        'success': '#27ae60',
        'danger': '#e74c3c',
        'warning': '#f39c12',
        'info': '#3498db'
    },
    'facility_colors': {
        'Hospital': '#e74c3c',
        'Primary Health Centre': '#3498db',
        'Community Health Centre': '#2ecc71',
        'Sub Centre': '#f39c12',
        'Pharmacy': '#9b59b6',
        'Clinic/ Dispensary': '#e67e22'
    }
}

# Logging Settings
LOGGING_SETTINGS = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'handlers': ['console'],
    'log_file': PROJECT_ROOT / 'logs' / 'dashboard.log'
}

# Security Settings
SECURITY_SETTINGS = {
    'max_file_size': 100 * 1024 * 1024,  # 100MB
    'allowed_file_types': ['.csv', '.xlsx', '.xls'],
    'sanitize_inputs': True,
    'rate_limiting': True
}

# Export Settings
EXPORT_SETTINGS = {
    'formats': ['csv', 'xlsx', 'json'],
    'max_export_rows': 10000,
    'include_metadata': True,
    'timestamp_format': '%Y%m%d_%H%M%S'
}

# Development Settings
DEVELOPMENT_SETTINGS = {
    'debug_mode': os.getenv('DEBUG', 'False').lower() == 'true',
    'hot_reload': True,
    'show_errors': True,
    'profiling': False
}
