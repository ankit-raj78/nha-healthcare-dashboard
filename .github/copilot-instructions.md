# Copilot Instructions for NHA Healthcare Facilities Dashboard

<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

## Project Overview
This is a Python Streamlit dashboard project for analyzing and visualizing NHA (National Health Authority) healthcare facilities data across India.

## Key Technologies
- **Streamlit**: Web dashboard framework
- **Pandas**: Data manipulation and analysis
- **Plotly**: Interactive visualizations
- **Folium**: Interactive maps
- **Sentence Transformers**: Natural language search capabilities
- **FAISS**: Vector similarity search
- **Python 3.9+**: Core programming language

## Code Style Guidelines
- Use Python PEP 8 style guidelines
- Prefer type hints for function parameters and return values
- Use descriptive variable and function names
- Include docstrings for all functions and classes
- Follow Streamlit best practices with caching decorators

## Project Structure
- `app/`: Main application code
- `data/`: Dataset files and data processing utilities
- `components/`: Reusable Streamlit components
- `utils/`: Utility functions and helpers
- `config/`: Configuration files
- `tests/`: Unit tests

## Domain-Specific Context
- Healthcare facility types: Hospitals, PHCs, CHCs, Sub-centres, Clinics
- Ownership types: Government, Private, PPP
- Geographic scope: Pan-India healthcare infrastructure
- Data sources: NHA Master dataset, PMJAY, CGHS, PMGSY, etc.

## Performance Considerations
- Use `@st.cache_data` for data loading functions
- Implement pagination for large datasets
- Use map sampling for performance with large coordinate datasets
- Optimize search queries with proper indexing

## Security Guidelines
- Validate all user inputs
- Sanitize search queries
- Use environment variables for sensitive configuration
- Implement proper error handling and logging
