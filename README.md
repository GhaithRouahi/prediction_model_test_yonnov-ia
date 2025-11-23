# Automated Real Estate Price Prediction System

This project implements an end-to-end automated system for predicting real estate prices (both rental and sale) using machine learning models deployed in an Odoo environment. The system includes data scraping, cleaning, prediction automation, and comprehensive evaluation with visualizations.

##  Project Overview

The system automates the entire workflow from data collection to model evaluation for real estate price predictions in French cities. It handles both **location** (rental) and **vente** (sale) price predictions through a series of interconnected scripts and notebooks.

##  Process Automation Components

### 1. **Model Endpoint Extraction** 
*Automated testing process discovery*

Using browser DevTools, I reverse-engineered the Odoo module interface to extract the exact API endpoints and payload structures needed for predictions:

- **Method**: Intercepted network requests in browser DevTools during manual UI interactions
- **Extracted endpoints**: JSON-RPC calls to Odoo models (`prediction.rent.request`, `prediction.request`)
- **API Flow**: 
  1. `web_save` - Creates a new record
  2. `action_get_prediction` - Triggers model computation 
  3. `web_read` - Retrieves the predicted price
- **Result**: Complete automation of the manual testing process

### 2. **Data Scraping System**  `/Scrape/`
*Comprehensive web scraping with data quality assurance*

**Files:**
- `scrape.py` - Main scraping engine
- `locations.txt` - Target cities list
- `page.html` - Sample page structure for debugging

**Process:**
- **Target**: French real estate websites for both rental and sale listings
- **Data Quality**: Implemented extensive validation to ensure scraped data integrity
- **Challenges Addressed**:
  - Rate limiting and anti-bot measures
  - Data format inconsistencies across different listing formats
  - Missing or malformed price/surface/location data
  - Duplicate listing detection and removal
- **Output**: Clean, structured datasets ready for prediction

### 3. **Data Cleaning Pipeline**
*Robust data preprocessing and normalization*

**Key Features:**
- **Decimal Format Conversion**: French comma decimals (68,4) → standard dots (68.4)
- **Missing Data Handling**:
  - Surface missing → Drop row (critical feature)
  - Chambres missing → `chambres = max(0, pièces - 1)`
  - Pièces missing → `pièces = chambres + 1`
  - Étage missing → `étage = 0` (ground floor default)
- **Outlier Filtering**: Remove corrupted/extreme values that distort analysis
- **City Normalization**: Standardize city names (lowercase, trim spaces)

### 4. **Automated Prediction Scripts**  `/Predict/`
*Line-by-line price prediction automation*

**Files:**
- `predict_script.py` - Rental price predictions
- `predict_vente.py` - Sale price predictions  
- `clean.py` - Data preprocessing utilities

**Automation Features:**
- **Batch Processing**: Processes entire CSV files row by row
- **API Integration**: Seamless interaction with Odoo prediction models
- **Error Handling**: Robust JSON parsing and network error recovery
- **Data Normalization**: Applies cleaning rules before sending to model
- **Output Generation**: Creates prediction CSVs with original data + `prix_predicté` column

**Technical Implementation:**
```python
# Example workflow for each property
row_normalized = normalize_row(row)  # Apply cleaning rules
record_id = web_save(row_normalized)  # Create record in Odoo
action_get_prediction(record_id)     # Trigger prediction
prediction = web_read(record_id)     # Retrieve result
```

### 5. **Model Evaluation System**  `/location/` & `/vente/`
*Comprehensive prediction accuracy assessment*

**Components:**
- **Global Metrics**: MAE, RMSE, R² across all predictions
- **City-Level Analysis**: Performance breakdown by geographical location
- **Statistical Validation**: Sample size filtering for reliable city metrics

**Files:**
- `evaluate_vente.py` - Sale prediction evaluation (standalone script)
- `data_before_pred.csv` & `data_after_pred.csv` - Input/output datasets

### 6. **Interactive Visualization Notebooks**
*Visual analysis and results presentation*

**Notebooks:**
- `location/evaluate_location.ipynb` - Rental prediction analysis
- `vente/evaluate_vente.ipynb` - Sale prediction analysis

**Visualizations:**
- **Actual vs Predicted Scatter Plots**: Perfect prediction line with data distribution
- **Residuals Analysis**: Error distribution patterns
- **City Performance Comparisons**: MAE and R² rankings by city
- **Statistical Summaries**: Comprehensive metrics tables

**Key Features:**
- Interactive plots with matplotlib/seaborn
- Automated report generation (CSV exports)
- Outlier detection and filtering for meaningful visualizations
- City-level filtering (minimum sample sizes for statistical significance)

##  Project Structure

```
prediction_test/
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── clean_listings.py                  # Main data cleaning script
│
├── Scrape/                           # Web scraping system
│   ├── scrape.py                     # Main scraping engine
│   ├── locations.txt                 # Target cities
│   └── page.html                     # Page structure reference
│
├── Predict/                          # Prediction automation
│   ├── predict_script.py             # Rental predictions
│   ├── predict_vente.py              # Sale predictions
│   ├── clean.py                      # Data preprocessing
│   ├── Test_Data/                    # Input datasets
│   │   ├── listings.csv              # Raw scraped data
│   │   └── listings_cleaned.csv      # Preprocessed data
│   └── Predictions/                  # Output results
│       ├── output_prediction_location.csv
│       └── output_prediction_vente.csv
│
├── location/                         # Rental analysis
│   ├── evaluate_model.ipynb          # Interactive evaluation
│   ├── data_before_pred.csv          # Input data
│   └── data_after_pred.csv           # Results with predictions
│
└── vente/                           # Sale analysis
    ├── evaluate_vente.ipynb          # Interactive evaluation
    ├── evaluate_vente.py             # Standalone evaluation
    ├── data_before_pred.csv          # Input data
    └── data_after_pred.csv           # Results with predictions
```

##  Usage Instructions

### 1. **Data Scraping**
```bash
cd Scrape/
python scrape.py
```

### 2. **Data Cleaning**
```bash
python clean_listings.py
```

### 3. **Generate Predictions**
```bash
# Rental predictions
cd Predict/
python predict_script.py

# Sale predictions  
python predict_vente.py
```

### 4. **Evaluate Results**
```bash
# Standalone evaluation
cd vente/
python evaluate_vente.py --input data_after_pred.csv --outdir evaluation_results

# Interactive notebook evaluation
jupyter notebook location/evaluate_model.ipynb
jupyter notebook vente/evaluate_vente.ipynb
```

##  Key Results & Insights

- **Automated Testing**: Eliminated manual UI interactions, enabling batch processing of thousands of properties
- **Data Quality**: Robust scraping and cleaning pipeline ensures reliable model inputs  
- **Prediction Accuracy**: Comprehensive evaluation across multiple French cities with statistical significance testing
- **Visual Analysis**: Clear, interpretable charts showing model performance patterns and geographical variations

##  Technical Stack

- **Python 3.x** - Core language
- **pandas, numpy** - Data manipulation and analysis
- **matplotlib, seaborn** - Visualization and plotting
- **scikit-learn** - Model evaluation metrics (MAE, RMSE, R²)
- **requests** - API communication with Odoo
- **Jupyter Notebook** - Interactive analysis environment

##  Learning Outcomes

This project demonstrates:
- **API Reverse Engineering**: Extracting endpoints from browser DevTools
- **Web Scraping at Scale**: Handling real-world data quality challenges
- **ML Pipeline Automation**: End-to-end prediction system implementation
- **Statistical Analysis**: Comprehensive model evaluation methodology
- **Data Visualization**: Clear communication of analytical results

---

*This automated system transforms a manual, time-consuming prediction process into a scalable, reproducible workflow suitable for production deployment.*
