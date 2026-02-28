# NHA Healthcare Master Data Dashboard

Merges **9 government healthcare datasets** (~404K records) into a single deduplicated master dataset of **393K unique healthcare facilities** across India, with an interactive Streamlit dashboard for analysis.

## Source Datasets

| Dataset | Records | Description |
|---------|---------|-------------|
| NHA | 323,460 | National Health Authority — national facility registry |
| PHC | 31,958 | Primary Health Centres |
| PMGSY | 13,702 | Pradhan Mantri Gram Sadak Yojana — rural health infrastructure |
| PMJAY | 11,284 | Ayushman Bharat — empanelled hospitals with specialties |
| NIN | 10,530 | National Inventory for Non-Communicable Diseases |
| CDAC_BB | 5,679 | CDAC Blood Banks |
| CHC | 4,237 | Community Health Centres |
| CGHS | 1,983 | Central Government Health Scheme |
| NHP | 999 | National Health Portal — medical colleges |

## How It Works

1. **`master_merger.py`** — Merges all 9 CSVs using geo-proximity (BallTree within 500m) + fuzzy name matching (rapidfuzz) to deduplicate while preserving all unique information.
2. **`master_dashboard.py`** — Streamlit dashboard with 7 tabs for interactive analysis.

## Dashboard Features

- **Overview** — KPIs, facility type & ownership distributions, state-wise counts
- **Geographic Map** — Interactive Folium map with clustering, color-coded markers, heatmap
- **Analytics** — Cross-tabulations, ABDM/24x7 coverage, specialty analysis, coverage gaps
- **Cross-Dataset Analysis** — Source overlap matrix, multi-source records, enrichment analysis
- **Data Explorer** — Searchable, filterable table with CSV export
- **District Deep Dive** — State → district drill-down with maps and charts
- **Full Dataset & Columns** — Complete 147-column dataset browser with column dictionary

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Place your 9 source CSV files in the project directory, then run the merger:
python master_merger.py

# Launch the dashboard:
streamlit run master_dashboard.py
```

## Data Files

CSV data files are excluded from the repository due to size (218MB master dataset). To reproduce:
1. Place the 9 source CSV files listed above in the project root
2. Run `python master_merger.py` to generate `healthcare_master_dataset.csv`

## Output Files

- `healthcare_master_dataset.csv` — 393K-row master dataset (generated)
- `merge_report.json` — per-dataset merge statistics
- `sample_matches.csv` — 200 sample matched pairs for quality review
