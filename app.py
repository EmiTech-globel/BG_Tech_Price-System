"""
CNC/Laser Cutting Pricing System - Flask Backend
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
import os
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
            'notes': self.notes
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
    
    print("\n" + "="*60)
    print("CNC/LASER CUTTING PRICING SYSTEM")
    print("="*60)
    print("\n Server starting...")
    print("Database initialized")
    print("Open your browser and go to: http://localhost:5000")
    print("\n Press CTRL+C to stop the server")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)