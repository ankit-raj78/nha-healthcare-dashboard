"""
Application Constants
"""

# Application Configuration
APP_CONFIG = {
    'name': 'NHA Healthcare Facilities Dashboard',
    'version': '1.0.0',
    'description': 'Comprehensive analysis and visualization of healthcare infrastructure across India',
    'author': 'Healthcare Analytics Team'
}

# Data Configuration
DATA_CONFIG = {
    'master_file': 'NHA_Master_merged_TEST.csv',
    'encoding': 'utf-8',
    'max_map_points': 2000,
    'search_result_limit': 500
}

# UI Configuration
UI_CONFIG = {
    'page_title': 'NHA Healthcare Facilities Dashboard',
    'page_icon': '🏥',
    'layout': 'wide',
    'sidebar_state': 'expanded'
}

# Search Configuration
SEARCH_CONFIG = {
    'model_name': 'all-MiniLM-L6-v2',
    'relevance_threshold': 0.2,
    'max_results': 500,
    'enable_fallback': True
}

# Map Configuration
MAP_CONFIG = {
    'default_zoom': 6,
    'marker_radius': 6,
    'cluster_threshold': 100,
    'heatmap_radius': 15
}

# Color Schemes
COLORS = {
    'facility_types': {
        'Hospital': '#e74c3c',
        'Primary Health Centre': '#3498db',
        'Community Health Centre': '#2ecc71',
        'Sub Centre': '#f39c12',
        'Pharmacy': '#9b59b6',
        'Clinic/ Dispensary': '#e67e22',
        'Default': '#95a5a6'
    },
    'ownership': {
        'Government': '#27ae60',
        'Private': '#8e44ad',
        'PPP': '#f39c12',
        'Default': '#7f8c8d'
    },
    'primary_palette': [
        '#3498db', '#e74c3c', '#2ecc71', '#f39c12', 
        '#9b59b6', '#1abc9c', '#e67e22', '#95a5a6'
    ]
}

# Facility Type Mappings
FACILITY_TYPE_MAPPINGS = {
    'phc': 'Primary Health Centre',
    'primary health centre': 'Primary Health Centre',
    'chc': 'Community Health Centre', 
    'community health centre': 'Community Health Centre',
    'hospital': 'Hospital',
    'clinic': 'Clinic/ Dispensary',
    'dispensary': 'Clinic/ Dispensary',
    'clinic/ dispensary': 'Clinic/ Dispensary',
    'sub centre': 'Sub Centre',
    'subcentre': 'Sub Centre',
    'pharmacy': 'Pharmacy'
}

# Ownership Mappings
OWNERSHIP_MAPPINGS = {
    'govt': 'Government',
    'government': 'Government',
    'public': 'Government',
    'private': 'Private',
    'ppp': 'PPP',
    'public private partnership': 'PPP'
}

# Search Examples
SEARCH_EXAMPLES = [
    "government hospitals in Maharashtra",
    "private clinics with ABDM enabled",
    "community health centers in rural areas",
    "hospitals in Mumbai",
    "primary health centres in Gujarat",
    "ABDM enabled facilities",
    "pharmacy near Delhi"
]

# Analytics Configuration
ANALYTICS_CONFIG = {
    'top_n_states': 15,
    'top_n_facility_types': 10,
    'chart_height': 400,
    'matrix_height': 500
}
