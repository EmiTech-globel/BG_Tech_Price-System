# AI Coding Agent Instructions

## Project Overview

**BG_Tech_Price-System** is a Flask-based web application for generating dynamic pricing quotes for CNC/laser cutting jobs. It combines SVG file analysis, machine learning (RandomForest model), and a database of historical jobs to predict accurate prices based on job characteristics.

### Key Components
- **Backend**: Flask app (`app.py`) with SQLite database via SQLAlchemy
- **Frontend**: Multi-tab HTML/CSS/JS interface for quote generation and management  
- **ML Model**: Trained RandomForest model saved as pickle (`data/cnc_laser_pricing_model.pkl`)
- **Training Data**: CSV file with historical job records (`data/cnc_historical_jobs.csv`)

---

## Architecture & Data Flow

### 1. **File Analysis Pipeline (SVG & DXF)**

#### SVG Analysis
When users upload SVG files, the system extracts job parameters automatically:
- Parse SVG XML to extract width/height, count geometric shapes (paths, circles, rects, polygons, lines)
- Count text elements for letter estimation
- Convert SVG units (mm, cm, in, pt, px) to millimeters using `parse_svg_length()`
- Calculate complexity score (1-5) based on shape count and paths: <3 shapes→score 1, <8→score 2, etc.
- Estimate cutting time: `(path_length / 5mm_per_sec + setup_time) / 60` → result in minutes

**Key functions**: `analyze_svg_file()`, `extract_svg_dimensions()`, `calculate_complexity_from_shapes()`, `estimate_cutting_time()`

#### DXF Analysis (NEW)
Advanced spatial clustering for complex CAD designs:
- Read DXF files using ezdxf library with dual fallback (BytesIO → temporary file)
- Extract unit conversion factor from DXF header (`$INSUNITS`: 0=unitless, 1=inches, 4=mm, 6=meters, etc.)
- Detect meaningful entities (LINE, LWPOLYLINE, CIRCLE, ARC, TEXT, MTEXT, etc.)
- **Spatial clustering**: Groups entities into separate jobs based on proximity (50mm threshold)
- Analyze each cluster independently for dimensions, shape count, text content, complexity
- Returns either single job or multi-item array for bulk quote processing

**Key functions**: `analyze_dxf_file()`, `detect_spatial_jobs()`, `get_entity_bounding_box()`, `spatial_cluster_entities()`, `analyze_entity_cluster()`

**Critical**: DXF helper functions MUST be defined before `analyze_dxf_file()` is called (order matters in app.py)

### 2. **Pricing Engine**
Price prediction flow:
1. Collect job parameters: material, thickness, dimensions, complexity, cutting type, quantity, rush job flag
2. Create DataFrame and apply one-hot encoding for categorical columns (material, cutting_type)
3. Align features with model's expected columns (from saved pickle metadata)
4. Predict using RandomForest: outputs single float price in Naira (₦)
5. **Smart rounding** via `round_price_smartly()`: <₦100→10s, <₦1k→50s, <₦10k→100s, <₦100k→500s, else 1000s

**Critical**: Model features must match exactly—missing columns are filled with 0. See `predict_price()` and `sendPriceRequest()` in `script.js`.

### 3. **PDF Generation & Quote Download (NEW)**
Quote documents generated on-demand as professional PDFs:
- Uses ReportLab (reportlab>=4.0.7) for creation
- Includes: quote number, date, customer info, job specs, complexity, price with Naira formatting
- Generated PDF stored in BytesIO buffer (in-memory, no disk writes)
- Route `/download_quote_pdf/<quote_id>` returns PDF with attachment headers
- Function: `generate_quote_pdf(quote)` returns bytes, integrated with `/download_quote_pdf` route

**Dependencies**: reportlab.lib (colors, units, pagesizes), reportlab.platypus (tables, styles)

### 4. **Quote Management**
Two database models handle single and bulk quotes:
- `Quote`: Main quote record with aggregated job data + customer info
- `QuoteItem`: Individual items for bulk orders, linked to Quote via foreign key
- Quote numbering: `Q{YYYYMMDD}{###}` format (e.g., Q20231115001) generated daily

### 5. **Model Retraining**
Training workflow (restricted):
- Load historical jobs from CSV, clean numeric columns, drop null rows
- Encode categorical features, split 80/20 train/test
- Train RandomForest with `n_estimators=150, max_depth=20`
- Calculate R² and MAE metrics, save to pickle with metadata (total_jobs, r2_score, training_date)
- **Gating logic**: Requires 20+ NEW jobs since last model OR 20+ total jobs if first training

**File**: `data/cnc_laser_pricing_model.pkl` contains: model, columns (feature names), total_jobs, r2_score, mae, training_date

---

## Developer Workflows

### Running the Application
```bash
python app.py
```
- Starts Flask dev server on `http://0.0.0.0:5000` with debug=True
- Auto-creates `instance/` (database) and `data/` directories if missing
- Initializes SQLite database tables on first run

### Adding Training Data
1. Use "Add Training Job" tab to submit completed jobs with actual prices
2. Data appended to CSV maintaining column order: `data/cnc_historical_jobs.csv`
3. Jobs must include: material, thickness, dimensions, shapes/letters, complexity, cutting time, cutting type, quantity, rush flag, actual price charged
4. After 20+ new jobs added, retrain model via "Retrain Model Now" button

### Debugging Common Issues

**Model fails to load**:
- Check `data/cnc_laser_pricing_model.pkl` exists and is valid pickle
- Verify feature names in model metadata match current expected columns (material types, cutting types must be consistent)

**Price calculation returns None**:
- Inspect `predict_price()` error handling—likely feature mismatch or missing model
- Ensure all job data fields are populated in request

**SVG/DXF analysis fails**:
- **SVG**: Verify XML is valid UTF-8; check for namespace issues (handle both `svg:` and non-namespaced elements)
- **DXF**: DXF helper functions must be defined BEFORE `analyze_dxf_file()` call; check ezdxf library is installed

**PDF generation errors**:
- Verify `reportlab>=4.0.7` is installed
- Check logo path exists: `static/images/logo.png` (gracefully skipped if missing)
- BytesIO buffer management: ensure PDF is properly closed before sending

---

## Project-Specific Patterns & Conventions

### Error Handling & User Feedback
- **Backend**: Return `{'success': True/False, ...}` JSON for all API endpoints
- **Frontend**: Use `fetch()` with try-catch, display errors in `alert()` or inline divs
- **Validation**: Check required fields client-side before sending; backend validates again

### Data Flow Conventions
- **Numbers**: Prices in Naira (₦), dimensions in mm, time in minutes, thickness decimal (e.g., 1.5mm)
- **Categorical fields**: Material (Acrylic, Wood, Metal, MDF, Plywood, Foam, Cardboard, ACP), Cutting Type (Laser Cutting, CNC Router)
- **Complexity scale**: 1–5 integer (1=very simple, 5=very complex)
- **Rush job flag**: Boolean (0/1) for priority processing surcharge

### Frontend State Management
- `script.js` uses global variables to track state: `currentJobData`, `currentPrice`, `bulkItems[]`
- Tab switching via `showTab()` resets visibility of `.tab-content` divs
- Result box (`#resultBox`) toggles visibility and scrolls into view on price calculation
- Bulk order accumulates items in memory until saved (no persistence except on submit)

### Database Design Notes
- SQLAlchemy uses SQLite file at `instance/quotes.db`
- Quote.items relationship uses cascade delete for cleanup
- QuoteItem.to_dict() and Quote.to_dict() handle serialization for API responses
- Quote number uniqueness enforced via unique constraint + natural incrementing within day

---

## Key File References

| File | Purpose |
|------|---------|
| `app.py` | Flask routes, SQLAlchemy models, SVG analysis, pricing logic, model retraining |
| `templates/index.html` | Multi-tab UI: Upload, Manual Entry, Bulk Order, Saved Quotes, Add Job |
| `static/js/script.js` | Tab management, file upload handling, fetch calls, form validation, bulk item state |
| `static/css/style.css` | Responsive layout, tab styling, result box animations |
| `data/cnc_historical_jobs.csv` | Training dataset for ML model (appended by "Add Job" feature) |
| `data/cnc_laser_pricing_model.pkl` | Serialized RandomForest model + metadata |

---

## Integration Points & External Dependencies

- **Flask 2.x**: Web framework (routes, templating)
- **SQLAlchemy**: ORM for quote persistence
- **Pandas**: CSV I/O, data encoding for model
- **scikit-learn**: RandomForest model, train/test split, metrics (MAE, R²)
- **ezdxf**: DXF file reading with spatial entity analysis
- **ReportLab 4.0.7**: PDF generation for quote documents (tables, styles, images)
- **XML parsing**: `xml.etree.ElementTree` for SVG analysis (no external SVG library)
- **Frontend**: Vanilla JavaScript (no jQuery/React), CSS Grid for layouts
- **File handling**: `io.BytesIO` for in-memory DXF/PDF processing, `tempfile` as DXF fallback

---

## Common Modification Patterns

### Adding a New Material or Cutting Type
1. Add option to `<select>` elements in `index.html` (all relevant tabs)
2. One-hot encoding in `predict_price()` and `retrain_model()` automatically handles new categorical values
3. Retrain model to learn pricing for new category

### Changing Price Calculation Logic
- Modify `predict_price()` if adjusting feature pipeline
- Update `sendPriceRequest()` in `script.js` if changing job data structure
- **Always** retrain model after logic changes to maintain consistency

### Adjusting SVG Analysis
- Tune complexity thresholds in `calculate_complexity_from_shapes()` (currently 3, 8, 15, 30 shape counts)
- Adjust cutting speed constant in `estimate_cutting_time()` (currently 5mm/sec)
- Test with `analyze_svg_file()` endpoint using curl or Postman

### Database Migrations
- Modify `Quote` or `QuoteItem` class in `app.py`
- SQLAlchemy auto-creates tables on `db.create_all()` but does NOT auto-migrate existing data
- For schema changes on live database, manual SQL or alembic setup required (not currently implemented)

---

## Testing & Validation

**Unit-level**: Test SVG parsing with various file formats (viewBox, explicit width/height, unit variations)  
**Integration**: Submit job via UI, verify quote saves, check database record, retrain and confirm model updates  
**Regression**: After model retraining, compare R² score and MAE against historical runs  

No formal test suite exists—use manual testing via web UI or curl commands to `/health`, `/analyze_file`, `/calculate_price` endpoints.
