"""
Data Loading Utilities for NHA Healthcare Facilities Dashboard
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
import os

logger = logging.getLogger(__name__)


class DataLoader:
    """Handles loading and preprocessing of healthcare facilities data"""
    
    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize DataLoader with data directory"""
        if data_dir is None:
            # Default to data directory in project root
            self.data_dir = Path(__file__).parent.parent / "data"
        else:
            self.data_dir = Path(data_dir)
        
        self.master_file = "NHA_Master_merged_TEST.csv"
        
    def load_master_dataset(self) -> Optional[pd.DataFrame]:
        """Load the main NHA master dataset"""
        try:
            # Try different possible locations for the data file
            possible_paths = [
                self.data_dir / self.master_file,
                Path.cwd() / self.master_file,
                Path.cwd().parent / self.master_file,
                Path("/Users/ankitraj2/asar master data") / self.master_file
            ]
            
            df = None
            for path in possible_paths:
                if path.exists():
                    logger.info(f"Loading data from: {path}")
                    df = pd.read_csv(path)
                    break
            
            if df is None:
                logger.error(f"Could not find {self.master_file} in any expected location")
                return None
            
            # Preprocess the data
            df = self._preprocess_data(df)
            logger.info(f"Successfully loaded and preprocessed {len(df):,} facilities")
            return df
            
        except Exception as e:
            logger.error(f"Error loading master dataset: {e}")
            return None
    
    def _preprocess_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Preprocess the healthcare facilities data"""
        try:
            # Clean coordinate data
            df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
            df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
            
            # Remove rows with invalid coordinates
            valid_coords = (
                df['Latitude'].notna() & 
                df['Longitude'].notna() &
                (df['Latitude'].between(-90, 90)) & 
                (df['Longitude'].between(-180, 180))
            )
            
            original_count = len(df)
            df = df[valid_coords].copy()
            removed_count = original_count - len(df)
            
            if removed_count > 0:
                logger.warning(f"Removed {removed_count} facilities with invalid coordinates")
            
            # Clean text fields
            text_columns = ['Name', 'Address', 'Facility Type', 'Ownership']
            for col in text_columns:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip()
                    df[col] = df[col].replace('nan', '')
            
            # Standardize facility types
            if 'Facility Type' in df.columns:
                df['Facility Type'] = self._standardize_facility_types(df['Facility Type'])
            
            # Standardize ownership
            if 'Ownership' in df.columns:
                df['Ownership'] = self._standardize_ownership(df['Ownership'])
            
            logger.info(f"Data preprocessing completed successfully")
            return df
            
        except Exception as e:
            logger.error(f"Error in data preprocessing: {e}")
            return df
    
    def _standardize_facility_types(self, facility_types: pd.Series) -> pd.Series:
        """Standardize facility type names"""
        type_mapping = {
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
        
        standardized = facility_types.str.lower().map(type_mapping)
        return standardized.fillna(facility_types)
    
    def _standardize_ownership(self, ownership: pd.Series) -> pd.Series:
        """Standardize ownership types"""
        ownership_mapping = {
            'govt': 'Government',
            'government': 'Government',
            'public': 'Government',
            'private': 'Private',
            'ppp': 'PPP',
            'public private partnership': 'PPP'
        }
        
        standardized = ownership.str.lower().map(ownership_mapping)
        return standardized.fillna(ownership)
    
    def get_data_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get comprehensive information about the dataset"""
        info = {
            'total_facilities': len(df),
            'facility_types': df['Facility Type'].value_counts().to_dict(),
            'ownership_distribution': df['Ownership'].value_counts().to_dict(),
            'columns': list(df.columns),
            'coordinate_coverage': {
                'valid_coordinates': len(df[df['Latitude'].notna() & df['Longitude'].notna()]),
                'missing_coordinates': len(df[df['Latitude'].isna() | df['Longitude'].isna()])
            }
        }
        
        # Add state information if available
        if 'State' in df.columns:
            info['state_distribution'] = df['State'].value_counts().to_dict()
        
        # Add ABDM information if available
        if 'ABDM Enabled' in df.columns:
            info['abdm_distribution'] = df['ABDM Enabled'].value_counts().to_dict()
        
        return info
