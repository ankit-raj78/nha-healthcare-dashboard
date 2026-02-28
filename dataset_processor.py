#!/usr/bin/env python3
"""
Dataset Analysis and Master Data Creation Script

This script provides functionality to:
1. Analyze existing datasets
2. Merge multiple datasets into a master dataset
3. Perform data cleaning and quality checks
4. Export the final master dataset

Usage:
    python dataset_processor.py --help
"""

import pandas as pd
import numpy as np
import argparse
import sys
from pathlib import Path
import logging
from datetime import datetime
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dataset_processing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DatasetProcessor:
    """
    A comprehensive class for dataset analysis and merging operations
    """
    
    def __init__(self, master_file_path=None):
        """Initialize the processor with an optional master dataset"""
        self.master_df = pd.DataFrame()
        self.merge_history = []
        
        if master_file_path and Path(master_file_path).exists():
            self.load_master_dataset(master_file_path)
    
    def load_master_dataset(self, file_path):
        """Load the master dataset from file"""
        try:
            logger.info(f"Loading master dataset from {file_path}")
            
            if file_path.endswith('.csv'):
                # For large CSV files, load in chunks if needed
                try:
                    self.master_df = pd.read_csv(file_path)
                except pd.errors.ParserError:
                    logger.warning("Large file detected, loading sample...")
                    self.master_df = pd.read_csv(file_path, nrows=10000)
                    
            elif file_path.endswith(('.xlsx', '.xls')):
                self.master_df = pd.read_excel(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_path}")
            
            logger.info(f"Master dataset loaded successfully. Shape: {self.master_df.shape}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load master dataset: {e}")
            return False
    
    def analyze_dataset(self, df=None, dataset_name="Dataset"):
        """Perform comprehensive analysis of a dataset"""
        if df is None:
            df = self.master_df
        
        if df.empty:
            logger.warning("Dataset is empty")
            return {}
        
        logger.info(f"Analyzing {dataset_name}")
        
        analysis = {
            'name': dataset_name,
            'shape': df.shape,
            'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024**2,
            'columns': list(df.columns),
            'dtypes': df.dtypes.to_dict(),
            'missing_values': df.isnull().sum().to_dict(),
            'duplicate_rows': df.duplicated().sum(),
            'numeric_columns': list(df.select_dtypes(include=[np.number]).columns),
            'categorical_columns': list(df.select_dtypes(include=['object']).columns),
            'timestamp': datetime.now().isoformat()
        }
        
        # Add statistics for numeric columns
        if analysis['numeric_columns']:
            analysis['numeric_stats'] = df[analysis['numeric_columns']].describe().to_dict()
        
        # Add value counts for categorical columns (top 5 for each)
        categorical_stats = {}
        for col in analysis['categorical_columns'][:5]:  # Limit to first 5 categorical columns
            if df[col].nunique() <= 50:  # Only for columns with reasonable number of unique values
                categorical_stats[col] = df[col].value_counts().head().to_dict()
        analysis['categorical_stats'] = categorical_stats
        
        return analysis
    
    def load_and_add_dataset(self, file_path, merge_type='concat', key_columns=None, **kwargs):
        """Load and add a new dataset to the master dataset"""
        try:
            logger.info(f"Loading dataset from {file_path}")
            
            # Determine file type and load
            file_path = Path(file_path)
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return False
            
            if file_path.suffix.lower() == '.csv':
                new_df = pd.read_csv(file_path, **kwargs)
            elif file_path.suffix.lower() in ['.xlsx', '.xls']:
                new_df = pd.read_excel(file_path, **kwargs)
            elif file_path.suffix.lower() == '.json':
                new_df = pd.read_json(file_path, **kwargs)
            else:
                logger.error(f"Unsupported file format: {file_path.suffix}")
                return False
            
            logger.info(f"Loaded dataset. Shape: {new_df.shape}")
            
            # Analyze the new dataset
            analysis = self.analyze_dataset(new_df, file_path.name)
            
            # Merge with master dataset
            return self.merge_dataset(new_df, file_path.name, merge_type, key_columns, analysis)
            
        except Exception as e:
            logger.error(f"Failed to load and add dataset {file_path}: {e}")
            return False
    
    def merge_dataset(self, new_df, dataset_name, merge_type='concat', key_columns=None, analysis=None):
        """Merge a new dataset with the master dataset"""
        try:
            original_shape = self.master_df.shape if not self.master_df.empty else (0, 0)
            
            if self.master_df.empty:
                self.master_df = new_df.copy()
                merge_info = f"Initialized master dataset with {dataset_name}"
                merge_type_used = "initialize"
            elif merge_type == 'concat':
                self.master_df = pd.concat([self.master_df, new_df], ignore_index=True, sort=False)
                merge_info = f"Concatenated {dataset_name}"
                merge_type_used = "concat"
            elif merge_type in ['inner', 'outer', 'left', 'right']:
                if not key_columns:
                    logger.error("Key columns required for join operations")
                    return False
                self.master_df = pd.merge(self.master_df, new_df, on=key_columns, how=merge_type)
                merge_info = f"Performed {merge_type} join with {dataset_name} on {key_columns}"
                merge_type_used = merge_type
            else:
                logger.error(f"Unsupported merge type: {merge_type}")
                return False
            
            final_shape = self.master_df.shape
            
            # Record merge operation
            merge_record = {
                'dataset_name': dataset_name,
                'merge_type': merge_type_used,
                'key_columns': key_columns,
                'original_shape': original_shape,
                'new_dataset_shape': new_df.shape,
                'final_shape': final_shape,
                'timestamp': datetime.now().isoformat(),
                'analysis': analysis
            }
            
            self.merge_history.append(merge_record)
            
            logger.info(f"✅ {merge_info}")
            logger.info(f"Shape change: {original_shape} → {final_shape}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to merge dataset {dataset_name}: {e}")
            return False
    
    def clean_dataset(self, remove_duplicates=True, remove_empty_rows=True, 
                     fill_na_strategy=None, columns_to_drop=None):
        """Clean the master dataset"""
        if self.master_df.empty:
            logger.warning("Master dataset is empty, nothing to clean")
            return
        
        logger.info("Starting dataset cleaning...")
        original_shape = self.master_df.shape
        
        # Remove duplicates
        if remove_duplicates:
            before = len(self.master_df)
            self.master_df = self.master_df.drop_duplicates()
            after = len(self.master_df)
            logger.info(f"Removed {before - after} duplicate rows")
        
        # Remove completely empty rows
        if remove_empty_rows:
            before = len(self.master_df)
            self.master_df = self.master_df.dropna(how='all')
            after = len(self.master_df)
            logger.info(f"Removed {before - after} completely empty rows")
        
        # Drop specified columns
        if columns_to_drop:
            existing_cols = [col for col in columns_to_drop if col in self.master_df.columns]
            if existing_cols:
                self.master_df = self.master_df.drop(columns=existing_cols)
                logger.info(f"Dropped columns: {existing_cols}")
        
        # Handle missing values
        if fill_na_strategy:
            if fill_na_strategy == 'drop':
                before = len(self.master_df)
                self.master_df = self.master_df.dropna()
                after = len(self.master_df)
                logger.info(f"Dropped {before - after} rows with missing values")
            elif fill_na_strategy == 'forward_fill':
                self.master_df = self.master_df.fillna(method='ffill')
                logger.info("Applied forward fill for missing values")
            elif fill_na_strategy == 'backward_fill':
                self.master_df = self.master_df.fillna(method='bfill')
                logger.info("Applied backward fill for missing values")
        
        # Reset index
        self.master_df = self.master_df.reset_index(drop=True)
        
        final_shape = self.master_df.shape
        logger.info(f"Cleaning completed. Shape change: {original_shape} → {final_shape}")
    
    def save_dataset(self, output_path, file_format='csv'):
        """Save the master dataset to file"""
        try:
            output_path = Path(output_path)
            
            if file_format.lower() == 'csv':
                self.master_df.to_csv(output_path, index=False)
            elif file_format.lower() == 'xlsx':
                self.master_df.to_excel(output_path, index=False)
            elif file_format.lower() == 'json':
                self.master_df.to_json(output_path, orient='records', indent=2)
            else:
                logger.error(f"Unsupported output format: {file_format}")
                return False
            
            logger.info(f"✅ Master dataset saved to {output_path}")
            logger.info(f"Final shape: {self.master_df.shape}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save dataset: {e}")
            return False
    
    def save_merge_history(self, output_path="merge_history.json"):
        """Save the merge history to a JSON file"""
        try:
            with open(output_path, 'w') as f:
                json.dump(self.merge_history, f, indent=2)
            logger.info(f"Merge history saved to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save merge history: {e}")
            return False
    
    def print_summary(self):
        """Print a summary of the current state"""
        print("\n" + "="*60)
        print("DATASET PROCESSOR SUMMARY")
        print("="*60)
        
        if not self.master_df.empty:
            print(f"Master Dataset Shape: {self.master_df.shape}")
            print(f"Memory Usage: {self.master_df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
            print(f"Columns: {len(self.master_df.columns)}")
            print(f"Missing Values: {self.master_df.isnull().sum().sum()}")
            print(f"Duplicate Rows: {self.master_df.duplicated().sum()}")
        else:
            print("Master dataset is empty")
        
        print(f"\nMerge Operations Performed: {len(self.merge_history)}")
        for i, record in enumerate(self.merge_history, 1):
            print(f"  {i}. {record['dataset_name']} ({record['merge_type']})")
        
        print("="*60)

def main():
    """Main function for command-line interface"""
    parser = argparse.ArgumentParser(description="Dataset Analysis and Master Data Creation Tool")
    parser.add_argument('--master', type=str, help='Path to master dataset file')
    parser.add_argument('--add', type=str, nargs='+', help='Paths to datasets to add')
    parser.add_argument('--merge-type', type=str, default='concat', 
                       choices=['concat', 'inner', 'outer', 'left', 'right'],
                       help='Type of merge operation')
    parser.add_argument('--key-columns', type=str, nargs='+', help='Key columns for join operations')
    parser.add_argument('--output', type=str, default='master_dataset.csv', help='Output file path')
    parser.add_argument('--format', type=str, default='csv', choices=['csv', 'xlsx', 'json'],
                       help='Output file format')
    parser.add_argument('--clean', action='store_true', help='Clean the dataset before saving')
    parser.add_argument('--analyze-only', action='store_true', help='Only analyze, do not merge')
    
    args = parser.parse_args()
    
    # Initialize processor
    processor = DatasetProcessor(args.master)
    
    if args.analyze_only:
        # Just analyze the master dataset
        if not processor.master_df.empty:
            analysis = processor.analyze_dataset()
            print(json.dumps(analysis, indent=2, default=str))
        else:
            logger.error("No master dataset loaded for analysis")
        return
    
    # Add datasets if specified
    if args.add:
        for dataset_path in args.add:
            success = processor.load_and_add_dataset(
                dataset_path, 
                merge_type=args.merge_type,
                key_columns=args.key_columns
            )
            if not success:
                logger.error(f"Failed to add dataset: {dataset_path}")
    
    # Clean dataset if requested
    if args.clean:
        processor.clean_dataset()
    
    # Save the result
    if not processor.master_df.empty:
        processor.save_dataset(args.output, args.format)
        processor.save_merge_history()
    
    # Print summary
    processor.print_summary()

if __name__ == "__main__":
    main()
