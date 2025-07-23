"""
Application Configuration Toggle
"""

# Feature Flags
ENABLE_AI_SEARCH = False  # Set to True to enable AI-powered search (may cause stability issues)
ENABLE_CLUSTERING = True   # Set to False to disable map clustering
ENABLE_HEATMAP = True     # Set to False to disable heatmap features

# Performance Settings
MAX_MAP_POINTS = 2000     # Maximum points to show on map
MAX_SEARCH_RESULTS = 500  # Maximum search results to return
SEARCH_TIMEOUT = 30       # Search timeout in seconds

# UI Settings
SHOW_DEBUG_INFO = False   # Show debug information in UI
COMPACT_MODE = False      # Use compact UI layout

# Data Settings  
LAZY_LOADING = True       # Enable lazy loading for better performance
CACHE_DURATION = 3600     # Cache duration in seconds (1 hour)

# Search Settings
FALLBACK_SEARCH_ONLY = True  # Use only text-based search (recommended for stability)
SEARCH_CASE_SENSITIVE = False
SEARCH_PARTIAL_MATCH = True

print("🔧 Configuration loaded:")
print(f"   • AI Search: {'Enabled' if ENABLE_AI_SEARCH else 'Disabled (for stability)'}")
print(f"   • Map Clustering: {'Enabled' if ENABLE_CLUSTERING else 'Disabled'}")
print(f"   • Max Map Points: {MAX_MAP_POINTS:,}")
print(f"   • Search Mode: {'Text-based only' if FALLBACK_SEARCH_ONLY else 'Hybrid AI + Text'}")
