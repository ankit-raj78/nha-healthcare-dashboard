# NHA Healthcare Facilities Dataset Deduplication Report

**Report Generated:** 2025-07-23 09:44:51
**Deduplication Strategy:** comprehensive
**Output File:** data/NHA_Master_deduplicated.csv

## Summary Statistics

| Metric | Original | Deduplicated | Change |
|--------|----------|--------------|--------|
| Total Records | 429,346 | 330,694 | -98,652 |
| Unique Names | 280,001 | 279,967 | - |
| Reduction | - | - | 22.98% |

## Facility Type Distribution

| Facility Type | Original | Deduplicated | Change |
|---------------|----------|--------------|--------|
| Sub Centre | 133,792 | 118,020 | -15,772 |
| Hospital | 74,421 | 46,546 | -27,875 |
| Pharmacy | 66,460 | 42,379 | -24,081 |
| Primary Health Centre | 34,925 | 27,382 | -7,543 |
| Clinic/ Dispensary | 32,813 | 27,578 | -5,235 |
| Health and Wellness Centre | 26,672 | 23,522 | -3,150 |
| Diagnostic Laboratory | 19,405 | 12,521 | -6,884 |
| Ayurveda Dispensary/ Clinic/ Polyclinic (OPD only) | 12,183 | 10,725 | -1,458 |
| Community Health Centre | 10,345 | 6,910 | -3,435 |
| Dental Clinic | 5,211 | 4,516 | -695 |
| Homeopathy Dispensary/ Clinic/ Polyclinic (OPD only) | 4,959 | 4,568 | -391 |
| Medical College | 1,852 | 1,107 | -745 |
| Imaging Center | 1,598 | 1,286 | -312 |
| Ayurveda Hospital/ Nursing Home | 1,399 | 945 | -454 |
| Unani Dispensary/ Clinic/ Polyclinic (OPD only) | 977 | 846 | -131 |
| Physiotherapy Clinic | 362 | 320 | -42 |
| Dialysis Center | 351 | 268 | -83 |
| Homeopathy Hospital/ Nursing Home | 297 | 224 | -73 |
| Blood Bank | 253 | 223 | -30 |
| Cath Laboratory | 244 | 182 | -62 |
| Ayurveda College | 211 | 150 | -61 |
| Dental Hospital | 171 | 138 | -33 |
| Unani Hospital/ Nursing Home | 112 | 80 | -32 |
| Dental College | 79 | 57 | -22 |
| Siddha Dispensary/ Clinic/ Polyclinic (OPD only) | 63 | 57 | -6 |
| Homeopathy College | 60 | 42 | -18 |
| Physiotherapy Hospital | 26 | 22 | -4 |
| Day Care center | 23 | 19 | -4 |
| Siddha Hospital/ Nursing Home | 22 | 15 | -7 |
| Unani College | 19 | 14 | -5 |
| Sowa-Rigpa Dispensary/ Clinic/ Polyclinic (OPD only) | 13 | 10 | -3 |
| Physiotherapy College | 8 | 6 | -2 |
| Sanatorium | 7 | 5 | -2 |
| Siddha College | 6 | 5 | -1 |
| Sowa-Rigpa College | 3 | 3 | +0 |
| Sowa-Rigpa Hospital/ Nursing Home | 2 | 2 | +0 |
| Palliative Care | 1 | 0 | -1 |
| Infertility Clinic | 1 | 1 | +0 |

## Top Duplicate Facilities Removed

| Facility Name | Original Count | After Deduplication | Removed |
|---------------|----------------|--------------------|---------|
| HEALTH AND WELLNESS CENTER | 312 | 218 | 94 |
| HOSPITAL | 306 | 162 | 144 |
| DR CHOPRAS PATH CLINIC | 220 | 1 | 219 |
| PHARMACY | 194 | 142 | 52 |
| CITY HOSPITAL | 192 | 113 | 79 |
| INDIRA IVF HOSPITAL PRIVATE LIMITED | 181 | 70 | 111 |
| PRADHAN MANTRI BHARTIYA JANAUSHADHI KENDRA | 165 | 75 | 90 |
| SANJEEVINI CLINIC | 158 | 104 | 54 |
| HEALTH AND WELLNESS CENTRE | 135 | 107 | 28 |
| ASHWINI CLINIC | 133 | 98 | 35 |
| SHREE CLINIC | 123 | 84 | 39 |
| APOLLO PHARMACY  A UNIT OF APOLLO HOSPITALS ENTERP | 118 | 51 | 67 |
| LIFE CARE HOSPITAL | 111 | 63 | 48 |
| SUB HEALTH CENTER | 103 | 61 | 42 |
| PRIMARY HEALTH CENTER | 99 | 69 | 30 |
| DENTAL CLINIC | 99 | 76 | 23 |
| LIFE LINE HOSPITAL | 98 | 59 | 39 |
| SANJEEVANI HOSPITAL | 98 | 59 | 39 |
| BALAJI MEDICAL STORE | 95 | 63 | 32 |
| KRISHNA HOSPITAL | 93 | 54 | 39 |

## Geographic Impact Analysis

Facilities with high geographic spread are less likely to be true duplicates:

| Facility Name | Count | Lat Spread | Lon Spread | Likely Duplicates |
|---------------|-------|------------|------------|-------------------|
| HEALTH AND WELLNESS CENTER | 312 | 24.1796° | 25.0777° | No |
| HOSPITAL | 306 | 25.6462° | 63.4927° | No |
| DR CHOPRAS PATH CLINIC | 220 | 0.0000° | 0.0000° | Yes |
| PHARMACY | 194 | 16.9610° | 24.7247° | No |
| CITY HOSPITAL | 192 | 23.7580° | 15.4315° | No |
| INDIRA IVF HOSPITAL PRIVATE LIMITED | 181 | 20.4163° | 18.4370° | No |
| PRADHAN MANTRI BHARTIYA JANAUSHADHI KEND | 165 | 16.1774° | 3.9273° | No |
| SANJEEVINI CLINIC | 158 | 16.4002° | 3.6508° | No |
| HEALTH AND WELLNESS CENTRE | 135 | 25.7100° | 27.0077° | No |
| ASHWINI CLINIC | 133 | 16.4854° | 15.3761° | No |

## Recommendations

### Data Quality Improvements
- Implement standardized naming conventions for facility registration
- Add unique facility identifiers beyond names
- Validate geographic coordinates during data entry
- Regular deduplication processes in data pipeline

### Further Analysis
- Manual review of high-count duplicates for data quality
- Cross-reference with official facility registries
- Implement fuzzy matching for similar but not identical names
- Consider additional deduplication criteria (phone, address)

### Usage Notes
- Deduplicated dataset is suitable for aggregate analysis
- Individual facility analysis may require original dataset
- Geographic visualizations will be cleaner with deduplicated data
- Dashboard performance will improve with reduced dataset size
