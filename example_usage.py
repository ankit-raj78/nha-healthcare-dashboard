#!/usr/bin/env python3
"""
Example script demonstrating how to use the dataset processing tools.

This script shows various ways to work with the DatasetProcessor class
and provides examples of common operations.
"""

import pandas as pd
import numpy as np
from dataset_processor import DatasetProcessor
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_sample_datasets():
    """Create sample datasets for demonstration purposes"""
    
    # Sample dataset 1: User data
    users_data = {
        'user_id': range(1, 101),
        'name': [f'User_{i}' for i in range(1, 101)],
        'age': np.random.randint(18, 70, 100),
        'city': np.random.choice(['Delhi', 'Mumbai', 'Bangalore', 'Chennai', 'Kolkata'], 100),
        'signup_date': pd.date_range('2020-01-01', periods=100)
    }
    users_df = pd.DataFrame(users_data)
    users_df.to_csv('sample_users.csv', index=False)
    logger.info("Created sample_users.csv")
    
    # Sample dataset 2: Transactions data
    transactions_data = {
        'user_id': np.random.choice(range(1, 101), 500),
        'transaction_id': range(1, 501),
        'amount': np.random.uniform(10, 1000, 500),
        'category': np.random.choice(['Food', 'Shopping', 'Travel', 'Entertainment'], 500),
        'transaction_date': pd.date_range('2020-01-01', periods=500)
    }
    transactions_df = pd.DataFrame(transactions_data)
    transactions_df.to_csv('sample_transactions.csv', index=False)
    logger.info("Created sample_transactions.csv")
    
    # Sample dataset 3: Additional user info (for join example)
    user_info_data = {
        'user_id': range(51, 151),  # Overlapping with some users
        'phone': [f'+91-{np.random.randint(7000000000, 9999999999)}' for _ in range(100)],
        'email': [f'user{i}@example.com' for i in range(51, 151)],
        'subscription': np.random.choice(['Basic', 'Premium', 'Enterprise'], 100)
    }
    user_info_df = pd.DataFrame(user_info_data)
    user_info_df.to_csv('sample_user_info.csv', index=False)
    logger.info("Created sample_user_info.csv")
    
    return users_df, transactions_df, user_info_df

def example_basic_usage():
    """Example 1: Basic dataset loading and concatenation"""
    print("\n" + "="*60)
    print("EXAMPLE 1: Basic Dataset Loading and Concatenation")
    print("="*60)
    
    # Create sample datasets
    users_df, transactions_df, user_info_df = create_sample_datasets()
    
    # Initialize processor with first dataset
    processor = DatasetProcessor()
    processor.load_and_add_dataset('sample_users.csv', merge_type='concat')
    
    # Add more datasets
    processor.load_and_add_dataset('sample_transactions.csv', merge_type='concat')
    
    # Print summary
    processor.print_summary()
    
    # Save the result
    processor.save_dataset('example_1_result.csv')
    processor.save_merge_history('example_1_history.json')

def example_join_operations():
    """Example 2: Join operations"""
    print("\n" + "="*60)
    print("EXAMPLE 2: Join Operations")
    print("="*60)
    
    # Initialize with users dataset
    processor = DatasetProcessor()
    processor.load_and_add_dataset('sample_users.csv', merge_type='concat')
    
    # Perform inner join with user info
    processor.load_and_add_dataset(
        'sample_user_info.csv', 
        merge_type='inner', 
        key_columns=['user_id']
    )
    
    processor.print_summary()
    processor.save_dataset('example_2_result.csv')

def example_data_cleaning():
    """Example 3: Data cleaning operations"""
    print("\n" + "="*60)
    print("EXAMPLE 3: Data Cleaning Operations")
    print("="*60)
    
    # Create a messy dataset
    messy_data = pd.concat([
        pd.DataFrame({'A': [1, 2, 3], 'B': ['a', 'b', 'c']}),
        pd.DataFrame({'A': [1, 2, 3], 'B': ['a', 'b', 'c']}),  # Duplicates
        pd.DataFrame({'A': [None, None, None], 'B': [None, None, None]}),  # Empty rows
        pd.DataFrame({'A': [4, 5], 'B': ['d', 'e']})
    ], ignore_index=True)
    
    messy_data.to_csv('messy_data.csv', index=False)
    
    # Load and clean
    processor = DatasetProcessor()
    processor.load_and_add_dataset('messy_data.csv')
    
    print("Before cleaning:")
    processor.print_summary()
    
    # Clean the dataset
    processor.clean_dataset(
        remove_duplicates=True,
        remove_empty_rows=True
    )
    
    print("After cleaning:")
    processor.print_summary()
    
    processor.save_dataset('example_3_cleaned.csv')

def example_analysis():
    """Example 4: Dataset analysis"""
    print("\n" + "="*60)
    print("EXAMPLE 4: Dataset Analysis")
    print("="*60)
    
    processor = DatasetProcessor()
    processor.load_and_add_dataset('sample_users.csv')
    
    # Analyze the dataset
    analysis = processor.analyze_dataset()
    
    print("Dataset Analysis Results:")
    print(f"Shape: {analysis['shape']}")
    print(f"Memory Usage: {analysis['memory_usage_mb']:.2f} MB")
    print(f"Columns: {len(analysis['columns'])}")
    print(f"Numeric Columns: {analysis['numeric_columns']}")
    print(f"Categorical Columns: {analysis['categorical_columns']}")
    print(f"Missing Values: {sum(analysis['missing_values'].values())}")
    print(f"Duplicate Rows: {analysis['duplicate_rows']}")

def example_command_line_equivalent():
    """Example 5: Show command-line equivalent operations"""
    print("\n" + "="*60)
    print("EXAMPLE 5: Command-Line Equivalent Operations")
    print("="*60)
    
    print("The following operations were performed programmatically.")
    print("Here are the equivalent command-line commands:\n")
    
    commands = [
        "# Basic concatenation:",
        "python dataset_processor.py --master sample_users.csv --add sample_transactions.csv --output concatenated.csv",
        "",
        "# Inner join:",
        "python dataset_processor.py --master sample_users.csv --add sample_user_info.csv --merge-type inner --key-columns user_id --output joined.csv",
        "",
        "# With cleaning:",
        "python dataset_processor.py --master messy_data.csv --clean --output cleaned.csv",
        "",
        "# Analysis only:",
        "python dataset_processor.py --master sample_users.csv --analyze-only",
        "",
        "# Multiple datasets at once:",
        "python dataset_processor.py --master sample_users.csv --add sample_transactions.csv sample_user_info.csv --merge-type concat --clean --output final_master.csv"
    ]
    
    for cmd in commands:
        print(cmd)

def cleanup_example_files():
    """Clean up example files"""
    import os
    
    files_to_remove = [
        'sample_users.csv', 'sample_transactions.csv', 'sample_user_info.csv',
        'messy_data.csv', 'example_1_result.csv', 'example_2_result.csv',
        'example_3_cleaned.csv', 'example_1_history.json', 'dataset_processing.log'
    ]
    
    for file in files_to_remove:
        try:
            if os.path.exists(file):
                os.remove(file)
                print(f"Removed: {file}")
        except Exception as e:
            print(f"Could not remove {file}: {e}")

def main():
    """Run all examples"""
    print("DATASET PROCESSOR - EXAMPLE DEMONSTRATIONS")
    print("="*60)
    
    try:
        # Run examples
        example_basic_usage()
        example_join_operations()
        example_data_cleaning()
        example_analysis()
        example_command_line_equivalent()
        
        print("\n" + "="*60)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nGenerated files:")
        print("- example_1_result.csv (concatenated datasets)")
        print("- example_2_result.csv (joined datasets)")
        print("- example_3_cleaned.csv (cleaned dataset)")
        print("- example_1_history.json (merge history)")
        print("- dataset_processing.log (processing log)")
        
        # Ask if user wants to clean up
        cleanup = input("\nDo you want to clean up example files? (y/n): ").lower().strip()
        if cleanup == 'y':
            cleanup_example_files()
            print("Example files cleaned up.")
        
    except Exception as e:
        logger.error(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
