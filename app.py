"""
CNC/Laser Cutting Pricing System - Flask Backend
BrainGain Tech Innovation Solutions
Local web application for automatic job pricing
"""

from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import pickle
import os
import xml.etree.ElementTree as ET
import re
import math

app = Flask(__name__)

# Database configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "instance", "quotes.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ========================================
# DATABASE MODEL
# ========================================

class Quote(db.Model):
    """Model for storing price quotes"""
    id = db.Column(db.Integer, primary_key=True)
    quote_number = db.Column(db.String(20), unique=True, nullable=False)
    customer_name = db.Column(db.String(100))
    customer_email = db.Column(db.String(100))
    customer_phone = db.Column(db.String(20))
    
    # Job details
    material = db.Column(db.String(50), nullable=False)
    thickness_mm = db.Column(db.Float, nullable=False)
    width_mm = db.Column(db.Float, nullable=False)
    height_mm = db.Column(db.Float, nullable=False)
    num_letters = db.Column(db.Integer, default=0)
    num_shapes = db.Column(db.Integer, default=1)
    complexity_score = db.Column(db.Integer, default=3)
    has_intricate_details = db.Column(db.Integer, default=0)
    cutting_type = db.Column(db.String(50), nullable=False)
    cutting_time_minutes = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=1)
    rush_job = db.Column(db.Integer, default=0)
    
    # Pricing
    quoted_price = db.Column(db.Float, nullable=False)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    
    def to_dict(self):
        """Convert quote to dictionary"""
        return {
            'id': self.id,
            'quote_number': self.quote_number,
            'customer_name': self.customer_name,
            'customer_email': self.customer_email,
            'customer_phone': self.customer_phone,
            'material': self.material,
            'thickness_mm': self.thickness_mm,
            'width_mm': self.width_mm,
            'height_mm': self.height_mm,
            'num_letters': self.num_letters,
            'num_shapes': self.num_shapes,
            'complexity_score': self.complexity_score,
            'cutting_type': self.cutting_type,
            'cutting_time_minutes': self.cutting_time_minutes,
            'quantity': self.quantity,
            'rush_job': self.rush_job,
            'quoted_price': self.quoted_price,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'notes': self.notes,
            'items': [item.to_dict() for item in self.items] if hasattr(self, 'items') else []
        }

class QuoteItem(db.Model):
    """Model for individual items in a quote"""
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quote.id'), nullable=False)
    
    # Job details for this item
    item_name = db.Column(db.String(200))
    material = db.Column(db.String(50), nullable=False)
    thickness_mm = db.Column(db.Float, nullable=False)
    width_mm = db.Column(db.Float, nullable=False)
    height_mm = db.Column(db.Float, nullable=False)
    num_letters = db.Column(db.Integer, default=0)
    num_shapes = db.Column(db.Integer, default=1)
    complexity_score = db.Column(db.Integer, default=3)
    has_intricate_details = db.Column(db.Integer, default=0)
    cutting_type = db.Column(db.String(50), nullable=False)
    cutting_time_minutes = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=1)
    rush_job = db.Column(db.Integer, default=0)
    
    # Pricing for this item
    item_price = db.Column(db.Float, nullable=False)
    
    # Relationship
    quote = db.relationship('Quote', backref=db.backref('items', lazy=True, cascade='all, delete-orphan'))
    
    def to_dict(self):
        """Convert item to dictionary"""
        return {
            'id': self.id,
            'item_name': self.item_name,
            'material': self.material,
            'thickness_mm': self.thickness_mm,
            'width_mm': self.width_mm,
            'height_mm': self.height_mm,
            'num_letters': self.num_letters,
            'num_shapes': self.num_shapes,
            'complexity_score': self.complexity_score,
            'cutting_type': self.cutting_type,
            'cutting_time_minutes': self.cutting_time_minutes,
            'quantity': self.quantity,
            'rush_job': self.rush_job,
            'item_price': self.item_price
        }
# ========================================
# LOAD TRAINED MODEL
# ========================================

MODEL_PATH = 'data/cnc_laser_pricing_model.pkl'
CSV_PATH = 'data/cnc_historical_jobs.csv'

try:
    with open(MODEL_PATH, 'rb') as f:
        saved_data = pickle.load(f)
        model = saved_data['model']
        columns = saved_data['columns']
    print("✅ Model loaded successfully!")
except Exception as e:
    print(f"❌ Error loading model: {e}")
    model = None
    columns = None

# ========================================
# SVG FILE ANALYZER FUNCTIONS
# ========================================

def analyze_svg_file(svg_content):
    """Extract job details from SVG file content"""
    try:
        root = ET.fromstring(svg_content)
        ns = {'svg': 'http://www.w3.org/2000/svg'}
        
        # Extract dimensions
        width_mm, height_mm = extract_svg_dimensions(root, ns)
        
        # Count elements
        num_paths = len(root.findall('.//svg:path', ns)) + len(root.findall('.//path'))
        num_circles = len(root.findall('.//svg:circle', ns)) + len(root.findall('.//circle'))
        num_rects = len(root.findall('.//svg:rect', ns)) + len(root.findall('.//rect'))
        num_polygons = len(root.findall('.//svg:polygon', ns)) + len(root.findall('.//polygon'))
        num_lines = len(root.findall('.//svg:line', ns)) + len(root.findall('.//line'))
        
        total_shapes = num_paths + num_circles + num_rects + num_polygons + num_lines
        
        # Count text
        text_elements = root.findall('.//svg:text', ns) + root.findall('.//text')
        num_letters = sum(len(text.text or '') for text in text_elements)
        
        # Calculate complexity
        complexity_score = calculate_complexity_from_shapes(total_shapes, num_paths)
        
        # Detect intricate details
        has_intricate = 1 if total_shapes > 20 or num_paths > 10 else 0
        
        # Estimate cutting time
        total_path_length = estimate_path_length(total_shapes, width_mm, height_mm)
        cutting_time = estimate_cutting_time(total_path_length, width_mm, height_mm)
        
        return {
            'success': True,
            'width_mm': round(width_mm, 2),
            'height_mm': round(height_mm, 2),
            'num_shapes': total_shapes,
            'num_letters': num_letters,
            'complexity_score': complexity_score,
            'has_intricate_details': has_intricate,
            'cutting_time_minutes': round(cutting_time, 1)
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def extract_svg_dimensions(root, ns):
    """Extract width and height from SVG"""
    width_str = root.get('width', '0')
    height_str = root.get('height', '0')
    
    width = parse_svg_length(width_str)
    height = parse_svg_length(height_str)
    
    if width == 0 or height == 0:
        viewbox = root.get('viewBox', '0 0 0 0')
        parts = viewbox.split()
        if len(parts) == 4:
            width = float(parts[2])
            height = float(parts[3])
    
    return width, height

def parse_svg_length(length_str):
    """Convert SVG length to millimeters"""
    length_str = str(length_str).strip()
    match = re.match(r'([\d.]+)\s*(\w*)', length_str)
    if not match:
        return 0
    
    value = float(match.group(1))
    unit = match.group(2).lower()
    
    conversions = {
        'mm': 1, 'cm': 10, 'm': 1000, 'in': 25.4,
        'pt': 0.3528, 'px': 0.2646, '': 0.2646
    }
    
    return value * conversions.get(unit, 0.2646)

def calculate_complexity_from_shapes(total_shapes, num_paths):
    """Calculate complexity score 1-5"""
    if total_shapes < 3 and num_paths < 5:
        return 1
    elif total_shapes < 8 and num_paths < 15:
        return 2
    elif total_shapes < 15 and num_paths < 30:
        return 3
    elif total_shapes < 30 and num_paths < 60:
        return 4
    else:
        return 5

def estimate_path_length(total_shapes, width, height):
    """Rough estimate of cutting path length"""
    avg_shape_perimeter = (width + height) / 2
    return total_shapes * avg_shape_perimeter * 0.5

def estimate_cutting_time(path_length_mm, width_mm, height_mm):
    """Estimate cutting time in minutes"""
    cutting_speed_mm_per_sec = 5
    cutting_time_sec = path_length_mm / cutting_speed_mm_per_sec
    setup_time_sec = max(120, cutting_time_sec * 0.2)
    total_time_min = (cutting_time_sec + setup_time_sec) / 60
    return max(5, total_time_min)

# ========================================
# PRICING FUNCTION
# ========================================

def predict_price(job_data):
    """Predict price using trained model"""
    if model is None:
        return None
    
    try:
        job_df = pd.DataFrame([job_data])
        job_df = pd.get_dummies(job_df, columns=['material', 'cutting_type'], 
                                prefix=['mat', 'cut'])
        
        for col in columns:
            if col not in job_df.columns:
                job_df[col] = 0
        
        job_df = job_df[columns]
        price = model.predict(job_df)[0]
        
        return round(price, 2)
        
    except Exception as e:
        print(f"Error predicting price: {e}")
        return None

# ========================================
# HELPER FUNCTIONS
# ========================================

def clean_number(value):
    """Remove commas, currency symbols and convert to string for safe parsing"""
    if value is None:
        return '0'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        cleaned = value.replace(',', '').replace('₦', '').replace('$', '').strip()
        return cleaned if cleaned else '0'
    return str(value)

# ========================================
# FLASK ROUTES
# ========================================

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/analyze_file', methods=['POST'])
def analyze_file():
    """Analyze uploaded SVG file"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})
    
    if not file.filename.lower().endswith('.svg'):
        return jsonify({'success': False, 'error': 'Only SVG files supported'})
    
    try:
        svg_content = file.read().decode('utf-8')
        analysis = analyze_svg_file(svg_content)
        return jsonify(analysis)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/calculate_price', methods=['POST'])
def calculate_price():
    """Calculate price for a job"""
    try:
        data = request.get_json()
        
        job_data = {
            'material': data['material'],
            'thickness_mm': float(data['thickness']),
            'num_letters': int(data.get('letters', 0)),
            'num_shapes': int(data.get('shapes', 1)),
            'complexity_score': int(data.get('complexity', 3)),
            'has_intricate_details': int(data.get('details', 0)),
            'width_mm': float(data['width']),
            'height_mm': float(data['height']),
            'cutting_type': data['cuttingType'],
            'cutting_time_minutes': float(data['time']),
            'quantity': int(data.get('quantity', 1)),
            'rush_job': int(data.get('rush', 0))
        }
        
        price = predict_price(job_data)
        
        if price is None:
            return jsonify({'success': False, 'error': 'Could not calculate price'})
        
        return jsonify({'success': True, 'price': price})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/save_quote', methods=['POST'])
def save_quote():
    """Save a quote to database"""
    try:
        data = request.get_json()
        
        # Generate quote number
        today = datetime.now().strftime('%Y%m%d')
        last_quote = Quote.query.filter(Quote.quote_number.like(f'Q{today}%')).order_by(Quote.id.desc()).first()
        
        if last_quote:
            last_num = int(last_quote.quote_number[-3:])
            new_num = last_num + 1
        else:
            new_num = 1
        
        quote_number = f"Q{today}{new_num:03d}"
        
        # Create new quote
        quote = Quote(
            quote_number=quote_number,
            customer_name=data.get('customer_name', ''),
            customer_email=data.get('customer_email', ''),
            customer_phone=data.get('customer_phone', ''),
            material=data['material'],
            thickness_mm=float(data['thickness']),
            width_mm=float(data['width']),
            height_mm=float(data['height']),
            num_letters=int(data.get('letters', 0)),
            num_shapes=int(data.get('shapes', 1)),
            complexity_score=int(data.get('complexity', 3)),
            has_intricate_details=int(data.get('details', 0)),
            cutting_type=data['cuttingType'],
            cutting_time_minutes=float(data['time']),
            quantity=int(data.get('quantity', 1)),
            rush_job=int(data.get('rush', 0)),
            quoted_price=float(data['price']),
            notes=data.get('notes', '')
        )
        
        db.session.add(quote)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'quote_number': quote_number,
            'message': f'Quote {quote_number} saved successfully!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get_quotes', methods=['GET'])
def get_quotes():
    """Get all quotes"""
    try:
        quotes = Quote.query.order_by(Quote.created_at.desc()).all()
        return jsonify({
            'success': True,
            'quotes': [quote.to_dict() for quote in quotes]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/search_quotes', methods=['GET'])
def search_quotes():
    """Search quotes by customer name or quote number"""
    try:
        query = request.args.get('q', '')
        
        quotes = Quote.query.filter(
            (Quote.customer_name.contains(query)) |
            (Quote.quote_number.contains(query))
        ).order_by(Quote.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'quotes': [quote.to_dict() for quote in quotes]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/delete_quote/<int:quote_id>', methods=['DELETE'])
def delete_quote(quote_id):
    """Delete a quote"""
    try:
        quote = Quote.query.get(quote_id)
        if quote:
            db.session.delete(quote)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Quote deleted'})
        else:
            return jsonify({'success': False, 'error': 'Quote not found'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/add_training_job', methods=['POST'])
def add_training_job():
    """Add a new job to training data CSV"""
    try:
        data = request.get_json()
        
        # Read existing CSV
        csv_path = CSV_PATH
        
        if not os.path.exists(csv_path):
            return jsonify({'success': False, 'error': 'CSV file not found'})
        
        df = pd.read_csv(csv_path)
        
        # Get column order from existing CSV
        column_order = df.columns.tolist()
        
        # Prepare new job data with cleaned numbers
        new_job = {
            'material': data.get('material', ''),
            'thickness_mm': float(clean_number(data.get('thickness', 0))),
            'num_letters': int(clean_number(data.get('letters', 0))),
            'num_shapes': int(clean_number(data.get('shapes', 1))),
            'complexity_score': int(clean_number(data.get('complexity', 3))),
            'has_intricate_details': int(clean_number(data.get('details', 0))),
            'width_mm': float(clean_number(data.get('width', 0))),
            'height_mm': float(clean_number(data.get('height', 0))),
            'cutting_type': data.get('cuttingType', ''),
            'cutting_time_minutes': float(clean_number(data.get('time', 0))),
            'quantity': int(clean_number(data.get('quantity', 1))),
            'rush_job': int(clean_number(data.get('rush', 0))),
            'price': float(clean_number(data.get('price', 0)))
        }
        
        # Create new row with same column order as CSV
        new_row = pd.DataFrame([new_job])
        
        # Reorder to match existing CSV columns
        new_row = new_row[column_order]
        
        # Append new row
        df = pd.concat([df, new_row], ignore_index=True)
        
        # Save back to CSV
        df.to_csv(csv_path, index=False)
        
        return jsonify({
            'success': True,
            'message': f'Job added successfully! Total jobs: {len(df)}',
            'total_jobs': len(df)
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        })

@app.route('/get_training_stats', methods=['GET'])
def get_training_stats():
    """Get current training data statistics"""
    try:
        # Try to load model metadata first
        if os.path.exists(MODEL_PATH):
            with open(MODEL_PATH, 'rb') as f:
                saved_data = pickle.load(f)
                total_jobs = saved_data.get('total_jobs', 0)
                r2_score_val = saved_data.get('r2_score', 0)
        else:
            # Fallback to CSV count
            if os.path.exists(CSV_PATH):
                df = pd.read_csv(CSV_PATH)
                total_jobs = len(df)
            else:
                total_jobs = 0
            r2_score_val = 0
        
        return jsonify({
            'success': True,
            'total_jobs': total_jobs,
            'r2_score': round(r2_score_val, 3)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/retrain_model', methods=['POST'])
def retrain_model():
    """Retrain the pricing model with current data"""
    try:
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import mean_absolute_error, r2_score as calculate_r2
        from sklearn.ensemble import RandomForestRegressor
        
        # Load data
        df = pd.read_csv(CSV_PATH)
        
        # Clean price column if it contains strings
        if df['price'].dtype == 'object':
            df['price'] = df['price'].apply(lambda x: clean_number(x))
            df['price'] = pd.to_numeric(df['price'], errors='coerce')
        
        # Clean all numeric columns
        numeric_cols = ['thickness_mm', 'width_mm', 'height_mm', 'cutting_time_minutes']
        for col in numeric_cols:
            if col in df.columns and df[col].dtype == 'object':
                df[col] = df[col].apply(lambda x: clean_number(x))
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Remove rows with any missing values
        df = df.dropna()

        # Determine number of new rows since last saved model (if present)
        prev_total = 0
        if os.path.exists(MODEL_PATH):
            try:
                with open(MODEL_PATH, 'rb') as f:
                    prev_saved = pickle.load(f)
                    prev_total = int(prev_saved.get('total_jobs', 0) or 0)
            except Exception:
                prev_total = 0

        new_jobs = max(0, len(df) - prev_total)

        # If a previous model exists, require at least 20 NEW jobs since that model
        if prev_total > 0:
            if new_jobs < 20:
                return jsonify({
                    'success': False,
                    'error': f'Need at least 20 NEW jobs since last model to retrain. New jobs: {new_jobs} (total rows: {len(df)})'
                })
        else:
            # No previous model: require at least 20 total rows
            if len(df) < 20:
                return jsonify({
                    'success': False,
                    'error': f'Need at least 20 jobs to retrain effectively. Current: {len(df)} jobs'
                })
        
        # Prepare data for training
        df_encoded = df.copy()
        df_encoded = pd.get_dummies(df_encoded, columns=['material', 'cutting_type'], 
                                    prefix=['mat', 'cut'])
        
        X = df_encoded.drop('price', axis=1)
        y = df_encoded['price']
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Train new model
        new_model = RandomForestRegressor(
            n_estimators=150,
            max_depth=20,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
        
        new_model.fit(X_train, y_train)
        
        # Evaluate model
        y_pred = new_model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = calculate_r2(y_test, y_pred)
        
        # Save new model
        model_data = {
            'model': new_model,
            'columns': X.columns,
            'training_date': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_jobs': len(df),
            'r2_score': r2,
            'mae': mae
        }
        
        with open(MODEL_PATH, 'wb') as f:
            pickle.dump(model_data, f)
        
        # Update global model
        global model, columns
        model = new_model
        columns = X.columns
        
        return jsonify({
            'success': True,
            'message': 'Model retrained successfully!',
            'total_jobs': len(df),
            'r2_score': round(r2, 3),
            'mae': round(mae, 2)
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        })

@app.route('/health')
def health():
    """Check if app is running"""
    return jsonify({
        'status': 'running',
        'model_loaded': model is not None,
        'company': 'BrainGain Tech Innovation Solutions'
    })

@app.route('/save_bulk_quote', methods=['POST'])
def save_bulk_quote():
    """Save a quote with multiple items"""
    try:
        data = request.get_json()
        
        # Generate quote number
        today = datetime.now().strftime('%Y%m%d')
        last_quote = Quote.query.filter(Quote.quote_number.like(f'Q{today}%')).order_by(Quote.id.desc()).first()
        
        if last_quote:
            last_num = int(last_quote.quote_number[-3:])
            new_num = last_num + 1
        else:
            new_num = 1
        
        quote_number = f"Q{today}{new_num:03d}"
        
        # Calculate total price from all items
        items_data = data.get('items', [])
        total_price = sum(float(item['price']) for item in items_data)
        
        # Use first item's details for main quote (for backward compatibility)
        first_item = items_data[0] if items_data else {}
        
        # Create main quote
        quote = Quote(
            quote_number=quote_number,
            customer_name=data.get('customer_name', ''),
            customer_email=data.get('customer_email', ''),
            customer_phone=data.get('customer_phone', ''),
            material=first_item.get('material', ''),
            thickness_mm=float(first_item.get('thickness', 0)),
            width_mm=float(first_item.get('width', 0)),
            height_mm=float(first_item.get('height', 0)),
            num_letters=int(first_item.get('letters', 0)),
            num_shapes=int(first_item.get('shapes', 1)),
            complexity_score=int(first_item.get('complexity', 3)),
            has_intricate_details=int(first_item.get('details', 0)),
            cutting_type=first_item.get('cuttingType', ''),
            cutting_time_minutes=float(first_item.get('time', 0)),
            quantity=int(first_item.get('quantity', 1)),
            rush_job=int(first_item.get('rush', 0)),
            quoted_price=total_price,
            notes=data.get('notes', '')
        )
        
        db.session.add(quote)
        db.session.flush()  # Get the quote.id
        
        # Create quote items
        for item_data in items_data:
            quote_item = QuoteItem(
                quote_id=quote.id,
                item_name=item_data.get('name', 'Item'),
                material=item_data.get('material', ''),
                thickness_mm=float(item_data.get('thickness', 0)),
                width_mm=float(item_data.get('width', 0)),
                height_mm=float(item_data.get('height', 0)),
                num_letters=int(item_data.get('letters', 0)),
                num_shapes=int(item_data.get('shapes', 1)),
                complexity_score=int(item_data.get('complexity', 3)),
                has_intricate_details=int(item_data.get('details', 0)),
                cutting_type=item_data.get('cuttingType', ''),
                cutting_time_minutes=float(item_data.get('time', 0)),
                quantity=int(item_data.get('quantity', 1)),
                rush_job=int(item_data.get('rush', 0)),
                item_price=float(item_data.get('price', 0))
            )
            db.session.add(quote_item)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'quote_number': quote_number,
            'total_price': total_price,
            'items_count': len(items_data),
            'message': f'Bulk quote {quote_number} saved with {len(items_data)} items!'
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        })

# ========================================
# RUN APPLICATION
# ========================================

if __name__ == '__main__':
    # Ensure required directories exist
    os.makedirs('data', exist_ok=True)
    os.makedirs('instance', exist_ok=True)
    
    # Create database tables
    with app.app_context():
        db.create_all()

    app.run(debug=True, host='0.0.0.0', port=5000)