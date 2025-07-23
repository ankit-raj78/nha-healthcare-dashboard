#!/usr/bin/env python3
"""
NHA Healthcare Facilities Dataset Deduplication Script

This script performs comprehensive deduplication analysis and processing
of the NHA Master dataset based on facility names and other criteria.
"""

import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path
import argparse
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_loader import DataLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deduplication.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Main deduplication process"""
    parser = argparse.ArgumentParser(description='Deduplicate NHA Healthcare Facilities Dataset')
    parser.add_argument('--strategy', choices=['simple', 'comprehensive', 'intelligent'], 
                       default='comprehensive', help='Deduplication strategy')
    parser.add_argument('--analyze-only', action='store_true', 
                       help='Only analyze duplicates without creating deduplicated file')
    parser.add_argument('--output', default='data/NHA_Master_deduplicated.csv',
                       help='Output file path for deduplicated dataset')
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("NHA Healthcare Facilities Dataset Deduplication")
    logger.info("=" * 60)
    
    # Initialize data loader
    data_loader = DataLoader()
    
    # Load dataset
    logger.info("Loading dataset...")
    df = data_loader.load_master_dataset()
    
    if df is None:
        logger.error("Failed to load dataset. Exiting.")
        return 1
    
    logger.info(f"Dataset loaded: {len(df):,} total records")
    
    # Analyze duplicates
    logger.info("\nAnalyzing duplicate patterns...")
    duplicate_analysis = data_loader.analyze_duplicates(df)
    
    print_duplicate_analysis(duplicate_analysis)
    
    if args.analyze_only:
        logger.info("Analysis complete. Exiting without deduplication.")
        return 0
    
    # Perform deduplication
    logger.info(f"\nStarting deduplication using '{args.strategy}' strategy...")
    
    deduplicated_df = data_loader.deduplicate_by_name(df, strategy=args.strategy)
    
    # Compare before and after
    original_count = len(df)
    final_count = len(deduplicated_df)
    removed_count = original_count - final_count
    removal_percentage = (removed_count / original_count) * 100
    
    logger.info("\n" + "=" * 60)
    logger.info("DEDUPLICATION RESULTS")
    logger.info("=" * 60)
    logger.info(f"Original records:      {original_count:,}")
    logger.info(f"Deduplicated records:  {final_count:,}")
    logger.info(f"Removed duplicates:    {removed_count:,}")
    logger.info(f"Reduction percentage:  {removal_percentage:.2f}%")
    
    # Save deduplicated dataset
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"\nSaving deduplicated dataset to: {output_path}")
    deduplicated_df.to_csv(output_path, index=False)
    
    # Generate deduplication report
    generate_deduplication_report(df, deduplicated_df, duplicate_analysis, args.strategy, output_path)
    
    logger.info("Deduplication process completed successfully!")
    return 0


def print_duplicate_analysis(analysis):
    """Print detailed duplicate analysis"""
    summary = analysis['summary']
    
    print("\n" + "=" * 60)
    print("DUPLICATE ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"Total records:        {summary['total_records']:,}")
    print(f"Unique names:         {summary['unique_names']:,}")
    print(f"Duplicate records:    {summary['duplicate_records']:,}")
    print(f"Duplication rate:     {summary['duplication_rate']:.2f}%")
    
    print("\nTOP DUPLICATE FACILITIES:")
    print("-" * 40)
    for name, count in list(analysis['top_duplicates'].items())[:15]:
        print(f"{count:>3} × {name}")
    
    print("\nDUPLICATE DISTRIBUTION:")
    print("-" * 40)
    for occurrences, facility_count in sorted(analysis['duplicate_distribution'].items()):
        print(f"{facility_count:>3} facilities appear {occurrences} times")
    
    if 'geographic_patterns' in analysis:
        print("\nGEOGRAPHIC DUPLICATE PATTERNS:")
        print("-" * 40)
        for name, info in list(analysis['geographic_patterns'].items())[:10]:
            likely = "YES" if info['likely_duplicates'] else "NO"
            lat_spread = info['coordinate_spread']['latitude']
            lon_spread = info['coordinate_spread']['longitude']
            print(f"{name[:40]:<40} | Count: {info['count']:>2} | "
                  f"Spread: {lat_spread:.4f}°,{lon_spread:.4f}° | Likely: {likely}")


def generate_deduplication_report(original_df, deduplicated_df, analysis, strategy, output_path):
    """Generate a comprehensive deduplication report"""
    
    report_path = output_path.parent / f"deduplication_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    
    with open(report_path, 'w') as f:
        f.write("# NHA Healthcare Facilities Dataset Deduplication Report\n\n")
        f.write(f"**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Deduplication Strategy:** {strategy}\n")
        f.write(f"**Output File:** {output_path}\n\n")
        
        # Summary statistics
        f.write("## Summary Statistics\n\n")
        f.write("| Metric | Original | Deduplicated | Change |\n")
        f.write("|--------|----------|--------------|--------|\n")
        
        original_count = len(original_df)
        final_count = len(deduplicated_df)
        removed_count = original_count - final_count
        
        f.write(f"| Total Records | {original_count:,} | {final_count:,} | -{removed_count:,} |\n")
        f.write(f"| Unique Names | {analysis['summary']['unique_names']:,} | {deduplicated_df['Name'].nunique():,} | - |\n")
        f.write(f"| Reduction | - | - | {(removed_count/original_count)*100:.2f}% |\n\n")
        
        # Facility type comparison
        f.write("## Facility Type Distribution\n\n")
        f.write("| Facility Type | Original | Deduplicated | Change |\n")
        f.write("|---------------|----------|--------------|--------|\n")
        
        original_types = original_df['Facility Type'].value_counts()
        dedup_types = deduplicated_df['Facility Type'].value_counts()
        
        for ftype in original_types.index:
            orig_count = original_types.get(ftype, 0)
            dedup_count = dedup_types.get(ftype, 0)
            change = dedup_count - orig_count
            f.write(f"| {ftype} | {orig_count:,} | {dedup_count:,} | {change:+,} |\n")
        
        # Top duplicates removed
        f.write("\n## Top Duplicate Facilities Removed\n\n")
        f.write("| Facility Name | Original Count | After Deduplication | Removed |\n")
        f.write("|---------------|----------------|--------------------|---------|\n")
        
        for name, orig_count in list(analysis['top_duplicates'].items())[:20]:
            dedup_count = len(deduplicated_df[deduplicated_df['Name'] == name])
            removed = orig_count - dedup_count
            f.write(f"| {name[:50]} | {orig_count} | {dedup_count} | {removed} |\n")
        
        # Geographic impact
        if 'geographic_patterns' in analysis:
            f.write("\n## Geographic Impact Analysis\n\n")
            f.write("Facilities with high geographic spread are less likely to be true duplicates:\n\n")
            f.write("| Facility Name | Count | Lat Spread | Lon Spread | Likely Duplicates |\n")
            f.write("|---------------|-------|------------|------------|-------------------|\n")
            
            for name, info in list(analysis['geographic_patterns'].items())[:15]:
                likely = "Yes" if info['likely_duplicates'] else "No"
                lat_spread = info['coordinate_spread']['latitude']
                lon_spread = info['coordinate_spread']['longitude']
                f.write(f"| {name[:40]} | {info['count']} | {lat_spread:.4f}° | {lon_spread:.4f}° | {likely} |\n")
        
        # Recommendations
        f.write("\n## Recommendations\n\n")
        f.write("### Data Quality Improvements\n")
        f.write("- Implement standardized naming conventions for facility registration\n")
        f.write("- Add unique facility identifiers beyond names\n")
        f.write("- Validate geographic coordinates during data entry\n")
        f.write("- Regular deduplication processes in data pipeline\n\n")
        
        f.write("### Further Analysis\n")
        f.write("- Manual review of high-count duplicates for data quality\n")
        f.write("- Cross-reference with official facility registries\n")
        f.write("- Implement fuzzy matching for similar but not identical names\n")
        f.write("- Consider additional deduplication criteria (phone, address)\n\n")
        
        f.write("### Usage Notes\n")
        f.write("- Deduplicated dataset is suitable for aggregate analysis\n")
        f.write("- Individual facility analysis may require original dataset\n")
        f.write("- Geographic visualizations will be cleaner with deduplicated data\n")
        f.write("- Dashboard performance will improve with reduced dataset size\n")
    
    logger.info(f"Deduplication report saved to: {report_path}")


def compare_strategies():
    """Compare different deduplication strategies"""
    logger.info("Comparing deduplication strategies...")
    
    data_loader = DataLoader()
    df = data_loader.load_master_dataset()
    
    if df is None:
        logger.error("Failed to load dataset")
        return
    
    original_count = len(df)
    strategies = ['simple', 'comprehensive', 'intelligent']
    
    print("\n" + "=" * 80)
    print("DEDUPLICATION STRATEGY COMPARISON")
    print("=" * 80)
    print(f"Original dataset: {original_count:,} records")
    print()
    
    results = {}
    
    for strategy in strategies:
        logger.info(f"Testing {strategy} strategy...")
        deduplicated = data_loader.deduplicate_by_name(df.copy(), strategy=strategy)
        final_count = len(deduplicated)
        removed = original_count - final_count
        percentage = (removed / original_count) * 100
        
        results[strategy] = {
            'final_count': final_count,
            'removed': removed,
            'percentage': percentage
        }
        
        print(f"{strategy.upper():>12} strategy: {final_count:>7,} records ({removed:>6,} removed, {percentage:>5.2f}%)")
    
    print("\nRecommendation: 'comprehensive' strategy provides good balance of deduplication and data preservation.")


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] == 'compare':
            compare_strategies()
        else:
            exit_code = main()
            sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
