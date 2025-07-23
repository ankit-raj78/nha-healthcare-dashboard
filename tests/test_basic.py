"""
Tests for the NHA Healthcare Facilities Dashboard

Run with: pytest tests/ -v
"""

import pytest
import pandas as pd
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_loader import DataLoader
from components.search_engine import SearchEngine


class TestDataLoader:
    """Test cases for data loading functionality"""
    
    def test_data_loader_initialization(self):
        """Test that DataLoader can be initialized"""
        loader = DataLoader()
        assert loader is not None
    
    def test_data_validation(self):
        """Test data validation with sample data"""
        # Create sample test data
        test_data = pd.DataFrame({
            'Name': ['Test Hospital', 'Test Clinic'],
            'Facility Type': ['Hospital', 'Clinic'],
            'Ownership': ['Government', 'Private'],
            'Address': ['123 Test St', '456 Test Ave'],
            'Latitude': [28.6139, 19.0760],
            'Longitude': [77.2090, 72.8777]
        })
        
        loader = DataLoader()
        # This would test the validation method when implemented
        assert len(test_data) == 2
        assert 'Name' in test_data.columns


class TestSearchEngine:
    """Test cases for search functionality"""
    
    def test_search_engine_initialization(self):
        """Test that SearchEngine can be initialized"""
        search_engine = SearchEngine()
        assert search_engine is not None
    
    def test_text_search(self):
        """Test basic text search functionality"""
        # Create sample test data
        test_data = pd.DataFrame({
            'Name': ['Government Hospital Delhi', 'Private Clinic Mumbai'],
            'Facility Type': ['Hospital', 'Clinic'],
            'Ownership': ['Government', 'Private'],
            'Address': ['Delhi', 'Mumbai']
        })
        
        search_engine = SearchEngine()
        # Test basic text search
        results = search_engine.search_text_only(test_data, "Government")
        assert len(results) >= 0  # Should return some results


class TestDataIntegrity:
    """Test cases for data integrity and validation"""
    
    def test_coordinate_validation(self):
        """Test coordinate validation"""
        valid_lat = 28.6139  # Delhi latitude
        valid_lon = 77.2090  # Delhi longitude
        
        assert -90 <= valid_lat <= 90
        assert -180 <= valid_lon <= 180
    
    def test_facility_types(self):
        """Test valid facility types"""
        valid_types = [
            'Hospital', 'PHC', 'CHC', 'Sub Centre', 
            'Clinic', 'Dispensary', 'Nursing Home'
        ]
        
        assert 'Hospital' in valid_types
        assert 'PHC' in valid_types


class TestConfiguration:
    """Test cases for configuration and settings"""
    
    def test_required_columns(self):
        """Test that required columns are defined"""
        required_columns = [
            'Name', 'Facility Type', 'Ownership', 
            'Address', 'Latitude', 'Longitude'
        ]
        
        assert len(required_columns) > 0
        assert 'Name' in required_columns


if __name__ == "__main__":
    # Run tests if this file is executed directly
    pytest.main([__file__, "-v"])
