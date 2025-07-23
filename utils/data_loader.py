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
    
    def __init__(self, data_dir: Optional[Path] = None, use_deduplicated: bool = False):
        """Initialize DataLoader with data directory"""
        if data_dir is None:
            # Default to data directory in project root
            self.data_dir = Path(__file__).parent.parent / "data"
        else:
            self.data_dir = Path(data_dir)
        
        self.use_deduplicated = use_deduplicated
        self.master_file = "NHA_Master_deduplicated.csv" if use_deduplicated else "NHA_Master_merged_TEST.csv"
        
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
    
    def deduplicate_by_name(self, df: pd.DataFrame, strategy: str = 'comprehensive') -> pd.DataFrame:
        """
        Deduplicate facilities based on name with different strategies
        
        Args:
            df: Input dataframe
            strategy: 'simple', 'comprehensive', or 'intelligent'
        
        Returns:
            Deduplicated dataframe
        """
        try:
            original_count = len(df)
            logger.info(f"Starting deduplication of {original_count:,} records")
            
            if strategy == 'simple':
                # Simple name-based deduplication
                deduplicated_df = self._simple_name_deduplication(df)
            elif strategy == 'comprehensive':
                # Name + location based deduplication
                deduplicated_df = self._comprehensive_deduplication(df)
            elif strategy == 'intelligent':
                # Advanced deduplication with fuzzy matching
                deduplicated_df = self._intelligent_deduplication(df)
            else:
                raise ValueError(f"Unknown deduplication strategy: {strategy}")
            
            final_count = len(deduplicated_df)
            removed_count = original_count - final_count
            
            logger.info(f"Deduplication completed: {removed_count:,} duplicates removed")
            logger.info(f"Final dataset: {final_count:,} unique facilities")
            
            return deduplicated_df
            
        except Exception as e:
            logger.error(f"Error in deduplication: {e}")
            return df
    
    def _simple_name_deduplication(self, df: pd.DataFrame) -> pd.DataFrame:
        """Simple deduplication keeping first occurrence of each name"""
        # Clean names for better matching
        df_copy = df.copy()
        df_copy['Name_cleaned'] = df_copy['Name'].str.strip().str.upper()
        
        # Keep first occurrence of each cleaned name
        deduplicated = df_copy.drop_duplicates(subset=['Name_cleaned'], keep='first')
        
        # Remove the temporary column
        deduplicated = deduplicated.drop('Name_cleaned', axis=1)
        
        return deduplicated
    
    def _comprehensive_deduplication(self, df: pd.DataFrame) -> pd.DataFrame:
        """Comprehensive deduplication using name + location"""
        df_copy = df.copy()
        
        # Clean and normalize names
        df_copy['Name_cleaned'] = (df_copy['Name']
                                  .str.strip()
                                  .str.upper()
                                  .str.replace(r'[^\w\s]', '', regex=True)
                                  .str.replace(r'\s+', ' ', regex=True))
        
        # Round coordinates to reduce minor GPS variations
        df_copy['Lat_rounded'] = df_copy['Latitude'].round(4)
        df_copy['Lon_rounded'] = df_copy['Longitude'].round(4)
        
        # Create composite key for deduplication
        dedup_columns = ['Name_cleaned', 'Lat_rounded', 'Lon_rounded']
        
        # Remove exact duplicates first
        deduplicated = df_copy.drop_duplicates(subset=dedup_columns, keep='first')
        
        # Handle cases where same name exists at different locations
        # This keeps facilities with same name but different locations
        
        # Clean up temporary columns
        deduplicated = deduplicated.drop(['Name_cleaned', 'Lat_rounded', 'Lon_rounded'], axis=1)
        
        return deduplicated
    
    def _intelligent_deduplication(self, df: pd.DataFrame) -> pd.DataFrame:
        """Intelligent deduplication with fuzzy name matching and location clustering"""
        try:
            from difflib import SequenceMatcher
            df_copy = df.copy()
            
            # Start with comprehensive deduplication first
            deduplicated = self._comprehensive_deduplication(df_copy)
            
            # Clean names for fuzzy matching
            deduplicated['Name_cleaned'] = (deduplicated['Name']
                                          .str.strip()
                                          .str.upper()
                                          .str.replace(r'[^\w\s]', '', regex=True)
                                          .str.replace(r'\s+', ' ', regex=True))
            
            # Further fuzzy matching for similar names at similar locations
            tolerance_km = 1.0  # 1 km tolerance for location matching
            similarity_threshold = 0.9  # 90% name similarity
            
            # Group by approximate location (rounded coordinates)
            deduplicated['Lat_group'] = (deduplicated['Latitude'] * 100).round() / 100
            deduplicated['Lon_group'] = (deduplicated['Longitude'] * 100).round() / 100
            
            to_remove = set()
            
            for (lat_group, lon_group), group in deduplicated.groupby(['Lat_group', 'Lon_group']):
                if len(group) < 2:
                    continue
                
                # Compare names within each location group
                names = group['Name_cleaned'].tolist()
                indices = group.index.tolist()
                
                for i in range(len(names)):
                    if indices[i] in to_remove:
                        continue
                    
                    for j in range(i + 1, len(names)):
                        if indices[j] in to_remove:
                            continue
                        
                        similarity = SequenceMatcher(None, names[i], names[j]).ratio()
                        if similarity >= similarity_threshold:
                            # Mark the second occurrence for removal
                            to_remove.add(indices[j])
            
            # Remove fuzzy duplicates
            final_deduplicated = deduplicated.drop(index=to_remove)
            
            # Clean up temporary columns
            temp_cols = ['Name_cleaned', 'Lat_group', 'Lon_group']
            final_deduplicated = final_deduplicated.drop([col for col in temp_cols if col in final_deduplicated.columns], axis=1)
            
            return final_deduplicated
            
        except ImportError:
            logger.warning("Advanced fuzzy matching not available, falling back to comprehensive deduplication")
            return self._comprehensive_deduplication(df)
        except Exception as e:
            logger.error(f"Error in intelligent deduplication: {e}")
            return self._comprehensive_deduplication(df)
    
    def analyze_duplicates(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze duplicate patterns in the dataset"""
        analysis = {}
        
        # Basic duplicate analysis
        total_records = len(df)
        unique_names = df['Name'].nunique()
        
        analysis['summary'] = {
            'total_records': total_records,
            'unique_names': unique_names,
            'duplicate_records': total_records - unique_names,
            'duplication_rate': ((total_records - unique_names) / total_records) * 100
        }
        
        # Top duplicates
        name_counts = df['Name'].value_counts()
        duplicates = name_counts[name_counts > 1]
        
        analysis['top_duplicates'] = duplicates.head(20).to_dict()
        
        # Duplicate distribution
        duplicate_counts = duplicates.value_counts().sort_index()
        analysis['duplicate_distribution'] = duplicate_counts.to_dict()
        
        # Geographic spread of duplicates
        if 'Latitude' in df.columns and 'Longitude' in df.columns:
            geographic_analysis = {}
            
            for name in duplicates.head(10).index:
                facilities = df[df['Name'] == name]
                if len(facilities) > 1:
                    coords = facilities[['Latitude', 'Longitude']].dropna()
                    if len(coords) > 1:
                        # Calculate coordinate spread
                        lat_spread = coords['Latitude'].max() - coords['Latitude'].min()
                        lon_spread = coords['Longitude'].max() - coords['Longitude'].min()
                        
                        geographic_analysis[name] = {
                            'count': len(facilities),
                            'coordinate_spread': {
                                'latitude': round(lat_spread, 4),
                                'longitude': round(lon_spread, 4)
                            },
                            'likely_duplicates': lat_spread < 0.01 and lon_spread < 0.01
                        }
            
            analysis['geographic_patterns'] = geographic_analysis
        
        return analysis

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
