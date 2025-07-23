# NHA Healthcare Facilities Dashboard

A comprehensive Streamlit-based web application for analyzing and visualizing healthcare facility data from the National Health Authority (NHA) of India.

## 🌟 Features

### 🔍 **Natural Language Search**
- AI-powered semantic search using sentence transformers
- Search facilities using plain English queries
- Examples: "government hospitals in Mumbai", "private clinics with ABDM"

### 📊 **Interactive Analytics**
- Facility type distribution analysis
- Ownership breakdown (Government, Private, PPP)
- State-wise facility distribution
- ABDM enablement statistics
- Cross-tabulation matrices

### 🗺️ **Interactive Maps**
- Geographic visualization of healthcare facilities
- Color-coded markers by facility type or ownership
- Clustered markers for performance with large datasets
- Popup information for each facility
- Heatmap view for facility density analysis

### 📋 **Data Management**
- Advanced filtering and search capabilities
- Data export functionality (CSV format)
- Real-time data processing and visualization
- Support for large datasets with performance optimization

## 🚀 Quick Start

### Prerequisites
- Python 3.9 or higher
- pip package manager

### Installation

1. **Clone or download the project:**
   ```bash
   cd /path/to/your/projects
   # The project is already set up in the current directory
   ```

2. **Create and activate virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Prepare your data:**
   - Place your `NHA_Master_merged_TEST.csv` file in the `data/` directory
   - Or ensure it's accessible in the project root

5. **Run the application:**
   ```bash
   streamlit run dashboard.py
   ```

6. **Open your browser:**
   - Navigate to `http://localhost:8501`
   - The dashboard will automatically load and initialize

## 📁 Project Structure

```
streamlit/
├── dashboard.py              # Main application entry point
├── requirements.txt          # Python dependencies
├── README.md                # This file
├── .github/
│   └── copilot-instructions.md  # AI assistant configuration
├── app/
│   ├── __init__.py
│   └── main.py              # Main application logic
├── components/
│   ├── __init__.py
│   ├── search_engine.py     # Natural language search engine
│   ├── map_visualizer.py    # Interactive map components
│   └── analytics_dashboard.py  # Analytics and charts
├── utils/
│   ├── __init__.py
│   ├── data_loader.py       # Data loading and preprocessing
│   └── constants.py         # Application constants
├── config/
│   ├── __init__.py
│   └── settings.py          # Configuration settings
├── data/                    # Data directory (place CSV files here)
├── tests/                   # Unit tests
└── venv/                    # Virtual environment
```

## 🔧 Configuration

### Data Sources
The application looks for the main dataset file in the following locations:
1. `data/NHA_Master_merged_TEST.csv`
2. `./NHA_Master_merged_TEST.csv` (project root)
3. `../NHA_Master_merged_TEST.csv` (parent directory)

### Search Engine
- **Model**: Uses `all-MiniLM-L6-v2` sentence transformer model
- **Backend**: FAISS vector database for fast similarity search
- **Fallback**: Text-based search when AI models are unavailable

### Performance Settings
- **Map Markers**: Limited to 2,000 points for optimal performance
- **Search Results**: Maximum 500 results per query
- **Data Table**: Displays up to 1,000 rows for performance

## 📊 Data Format

The application expects CSV data with the following key columns:
- `Name`: Facility name
- `Facility Type`: Type of healthcare facility
- `Ownership`: Ownership type (Government, Private, PPP)
- `Address`: Facility address
- `Latitude`: Geographic latitude coordinate
- `Longitude`: Geographic longitude coordinate
- `State`: State/region (optional)
- `ABDM Enabled`: ABDM enablement status (optional)

## 🎯 Usage Examples

### Natural Language Search
```
"government hospitals in Maharashtra"
"private clinics near Mumbai" 
"community health centers with ABDM enabled"
"hospitals in Delhi with emergency services"
```

### Traditional Filtering
- Filter by facility type (Hospital, PHC, CHC, etc.)
- Filter by ownership (Government, Private, PPP)
- Filter by state/region
- Filter by ABDM enablement status

## 🛠️ Development

### Adding New Features
1. **Components**: Add new visualization components in `components/`
2. **Data Processing**: Extend data loading logic in `utils/data_loader.py`
3. **Search**: Enhance search capabilities in `components/search_engine.py`
4. **Configuration**: Update settings in `config/settings.py`

### Testing
```bash
# Run tests (when implemented)
python -m pytest tests/

# Code formatting
black .

# Linting
flake8 .
```

## 📈 Performance Optimization

### For Large Datasets
- Data sampling for map visualization (configurable limit)
- Lazy loading of search indices
- Caching of preprocessed data
- Pagination for data tables

### Memory Management
- Efficient data structures using pandas
- Vector search with FAISS indexing
- Streamlit caching for expensive operations

## 🔒 Security Considerations

- Input sanitization for search queries
- File size limits for data uploads
- Safe handling of coordinate data
- Error handling for malformed data

## 🐛 Troubleshooting

### Common Issues

1. **Module Import Errors**
   ```bash
   # Ensure virtual environment is activated
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Data Loading Issues**
   ```bash
   # Check file path and permissions
   ls -la data/NHA_Master_merged_TEST.csv
   ```

3. **Search Not Working**
   ```bash
   # Install required AI packages
   pip install sentence-transformers faiss-cpu
   ```

4. **Map Not Loading**
   ```bash
   # Install mapping dependencies
   pip install folium streamlit-folium
   ```

## 📝 License

This project is developed for healthcare data analysis and visualization purposes.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the configuration settings
3. Check the logs for error messages
4. Ensure all dependencies are correctly installed

## 🔄 Updates and Maintenance

- Regular updates to dependencies
- Performance monitoring and optimization
- Feature enhancements based on user feedback
- Security updates and patches

---

**Built with ❤️ for better healthcare data visualization and analysis**
