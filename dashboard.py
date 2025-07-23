"""
NHA Healthcare Facilities Dashboard
A comprehensive Streamlit application for analyzing and visualizing healthcare facility data
"""

import streamlit as st
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.main import main

if __name__ == "__main__":
    main()
