#!/usr/bin/env python3
"""
Quick Dataset Deduplication Summary Script

This script provides a quick summary of the deduplication results.
"""

import pandas as pd
import os
from pathlib import Path

def main():
    """Display deduplication summary"""
    print("🏥 NHA Healthcare Facilities Dataset Deduplication Summary")
    print("=" * 60)
    
    # File paths
    data_dir = Path("data")
    original_file = data_dir / "NHA_Master_merged_TEST.csv"
    dedup_file = data_dir / "NHA_Master_deduplicated.csv"
    
    # Check original dataset
    if not original_file.exists():
        print("❌ Original dataset not found!")
        return
    
    print(f"📁 Original dataset: {original_file}")
    df_original = pd.read_csv(original_file, low_memory=False)
    original_count = len(df_original)
    original_unique_names = df_original['Name'].nunique()
    
    print(f"   Total records: {original_count:,}")
    print(f"   Unique names: {original_unique_names:,}")
    print(f"   Duplicate records: {original_count - original_unique_names:,}")
    print(f"   Duplication rate: {((original_count - original_unique_names) / original_count) * 100:.2f}%")
    
    # Check deduplicated dataset
    if dedup_file.exists():
        print(f"\n📁 Deduplicated dataset: {dedup_file}")
        df_dedup = pd.read_csv(dedup_file, low_memory=False)
        dedup_count = len(df_dedup)
        dedup_unique_names = df_dedup['Name'].nunique()
        
        print(f"   Total records: {dedup_count:,}")
        print(f"   Unique names: {dedup_unique_names:,}")
        
        # Comparison
        removed = original_count - dedup_count
        reduction_percentage = (removed / original_count) * 100
        
        print(f"\n🔄 Deduplication Results:")
        print(f"   Records removed: {removed:,}")
        print(f"   Reduction percentage: {reduction_percentage:.2f}%")
        print(f"   Data quality improvement: {reduction_percentage:.1f}% less duplicates")
        
        # File sizes
        original_size = original_file.stat().st_size / (1024 * 1024)  # MB
        dedup_size = dedup_file.stat().st_size / (1024 * 1024)  # MB
        size_reduction = ((original_size - dedup_size) / original_size) * 100
        
        print(f"\n💾 File Size Comparison:")
        print(f"   Original: {original_size:.1f} MB")
        print(f"   Deduplicated: {dedup_size:.1f} MB")
        print(f"   Size reduction: {size_reduction:.1f}%")
        
        print(f"\n✅ Deduplication Status: COMPLETE")
        print(f"   Both datasets are available for dashboard use")
        
    else:
        print(f"\n❌ Deduplicated dataset not found at: {dedup_file}")
        print("   Run: python3 deduplicate_dataset.py --strategy comprehensive")
    
    # Top duplicates in original
    print(f"\n🔍 Top Duplicate Facility Names (Original Dataset):")
    top_duplicates = df_original['Name'].value_counts().head(10)
    for name, count in top_duplicates.items():
        if count > 1:
            print(f"   {count:>3}× {name}")
    
    print(f"\n💡 Recommendation:")
    if dedup_file.exists():
        print("   ✅ Use deduplicated dataset for cleaner analytics")
        print("   ✅ Use original dataset when individual records matter")
    else:
        print("   🔄 Run deduplication to improve data quality")
    
    print(f"\n🚀 Dashboard Usage:")
    print("   streamlit run dashboard.py")
    if dedup_file.exists():
        print("   (Dashboard can now choose between original and deduplicated data)")

if __name__ == "__main__":
    main()
