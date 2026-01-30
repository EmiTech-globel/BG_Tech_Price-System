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
import re
import xml.etree.ElementTree as ET
import ezdxf
from ezdxf.math import Vec2
import math
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv
from functools import wraps
from flask import Response, request
from functools import wraps
from flask import request, jsonify, session, redirect, url_for
from supabase import create_client, Client
import os
from datetime import timedelta

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION & PATH SETUP ---

# 2. Define Paths
basedir = os.path.abspath(os.path.dirname(__file__))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 'instance' is the persistent storage area
INSTANCE_PATH = os.path.join(BASE_DIR, 'instance')
# 'data' is where the original shipping files live
DATA_PATH = os.path.join(BASE_DIR, 'data')

# Ensure instance directory exists
os.makedirs(INSTANCE_PATH, exist_ok=True)

# Initialize Supabase client
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configure Flask session for auth tokens
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=4)

# ========================================
# AUTH DECORATOR FOR PROTECTED ROUTES
# ========================================

def requires_auth(f):
    """
    Decorator to protect admin routes
    Validates Supabase JWT token from session or Authorization header
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for token in session (browser-based)
        token = session.get('access_token')
        
        # If not in session, check Authorization header (API calls)
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.replace('Bearer ', '')
        
        if not token:
            # No token found - redirect to login for browser, return 401 for API
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required', 'redirect': '/admin/login'}), 401
            return redirect('/admin/login')
        
        try:
            # Verify token with Supabase
            user_response = supabase.auth.get_user(token)
            
            if not user_response or not user_response.user:
                session.clear()
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Invalid or expired token', 'redirect': '/admin/login'}), 401
                return redirect('/admin/login')
            
            # Token is valid - store user info in request context
            request.current_user = user_response.user
            return f(*args, **kwargs)
            
        except Exception as e:
            print(f"Auth error: {e}")
            session.clear()
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication failed', 'redirect': '/admin/login'}), 401
            return redirect('/admin/login')
    
    return decorated_function

# --- DATABASE CONFIGURATION ---
database_url = os.environ.get('DATABASE_URL')

if not database_url:
    # Safety Check: If no URL is found, warn the user instead of silently falling back to SQLite
    raise ValueError("No DATABASE_URL found! Please create a .env file locally or set the var on Render.")

# Fix for SQLAlchemy compatibility (Render/Supabase use 'postgres://', SQLAlchemy needs 'postgresql://')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODEL LOADING LOGIC ---

MODEL_FILENAME = 'cnc_laser_pricing_model.pkl'
DATASET_FILENAME = 'cnc_historical_jobs.csv'

# Logic: Check Persistent Storage (instance/) first. If missing, use Default (data/).
if os.path.exists(os.path.join(INSTANCE_PATH, MODEL_FILENAME)):
    MODEL_PATH = os.path.join(INSTANCE_PATH, MODEL_FILENAME)
    print(f"Loading model from Persistent Storage: {MODEL_PATH}")
else:
    # Fallback to the files you shipped with the code
    MODEL_PATH = os.path.join(DATA_PATH, MODEL_FILENAME)
    print(f"Loading default model from: {MODEL_PATH}")

# Same logic for the training dataset
if os.path.exists(os.path.join(INSTANCE_PATH, DATASET_FILENAME)):
    DATASET_PATH = os.path.join(INSTANCE_PATH, DATASET_FILENAME)
else:
    DATASET_PATH = os.path.join(DATA_PATH, DATASET_FILENAME)

# Load the model safely
try:
    with open(MODEL_PATH, 'rb') as f:
        model_data = pickle.load(f)
        # Handle case where pickle contains just the model or a dict of metadata
        if isinstance(model_data, dict) and 'model' in model_data:
            model = model_data['model']
        else:
            model = model_data
except Exception as e:
    print(f"CRITICAL ERROR loading model: {e}")
    model = None

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
    customer_whatsapp = db.Column(db.String(20))
    
    # Job details
    material = db.Column(db.String(50), nullable=False)
    material_color = db.Column(db.String(50))
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

    # Discount details
    discount_applied = db.Column(db.Boolean, default=False)
    discount_percentage = db.Column(db.Float, default=0)
    discount_amount = db.Column(db.Float, default=0)
    original_price = db.Column(db.Float)  # Price before discount
    
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
            'customer_whatsapp': self.customer_whatsapp,
            'material': self.material,
            'material_color': self.material_color,
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
            'discount_applied': self.discount_applied,
            'discount_percentage': self.discount_percentage,
            'discount_amount': self.discount_amount,
            'original_price': self.original_price,
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
    material_color = db.Column(db.String(50))
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
    
class TrainingData(db.Model):
    __tablename__ = 'training_data'
    id = db.Column(db.Integer, primary_key=True)
    material = db.Column(db.String(100), nullable=False)
    thickness_mm = db.Column(db.Float, nullable=False)
    num_letters = db.Column(db.Integer, nullable=False)
    num_shapes = db.Column(db.Integer, nullable=False)
    complexity_score = db.Column(db.Integer, nullable=False)
    has_intricate_details = db.Column(db.Integer, nullable=False) # 0 or 1
    width_mm = db.Column(db.Float, nullable=False)
    height_mm = db.Column(db.Float, nullable=False)
    cutting_type = db.Column(db.String(100), nullable=False)
    cutting_time_minutes = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    rush_job = db.Column(db.Integer, nullable=False) # 0 or 1
    price = db.Column(db.Float, nullable=False) # The 'target' for the AI
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        """Converts the database row to a dictionary for Pandas/ML"""
        return {
            "material": self.material,
            "thickness_mm": self.thickness_mm,
            "num_letters": self.num_letters,
            "num_shapes": self.num_shapes,
            "complexity_score": self.complexity_score,
            "has_intricate_details": self.has_intricate_details,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "cutting_type": self.cutting_type,
            "cutting_time_minutes": self.cutting_time_minutes,
            "quantity": self.quantity,
            "rush_job": self.rush_job,
            "price": self.price
        }

class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column(db.Integer, primary_key=True)
    material_name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(50), nullable=True)
    thickness_mm = db.Column(db.Float, nullable=False)
    sheet_width_mm = db.Column(db.Float, nullable=False)
    sheet_height_mm = db.Column(db.Float, nullable=False)
    quantity_on_hand = db.Column(db.Integer, default=0)
    price_per_sq_ft = db.Column(db.Float, nullable=False)
    price_per_sheet = db.Column(db.Float, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    transactions = db.relationship('InventoryTransaction', backref='item', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "material": self.material_name,
            "color": self.color or "N/A",
            "thickness": self.thickness_mm,
            "size": f"{self.sheet_width_mm}x{self.sheet_height_mm}",
            "stock": self.quantity_on_hand,
            "price_sq_ft": self.price_per_sq_ft,
            "price_sheet": self.price_per_sheet  # NEW FIELD
        }

class InventoryTransaction(db.Model):
    __tablename__ = 'inventory_transaction'
    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)
    change_amount = db.Column(db.Integer, nullable=False)    # +10 (In) or -5 (Out)
    transaction_type = db.Column(db.String(20), nullable=False) # 'stock_in' or 'stock_out'
    note = db.Column(db.String(200)) # e.g. "Restock" or "Used for Job #102"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "date": self.created_at.strftime('%Y-%m-%d %H:%M'),
            "type": self.transaction_type,
            "change": self.change_amount,
            "note": self.note
        }

# ========================================
# LOAD TRAINED MODEL (already loaded above at lines 106-116)
# ========================================

# Use DATASET_PATH (set at lines 100-103) for CSV operations
CSV_PATH = DATASET_PATH

# Extract columns from the already-loaded model
try:
    if model is not None:
        # Try to get columns from saved model data
        with open(MODEL_PATH, 'rb') as f:
            saved_data = pickle.load(f)
            if isinstance(saved_data, dict) and 'columns' in saved_data:
                columns = saved_data['columns']
            else:
                columns = None
    else:
        columns = None
except Exception as e:
    print(f"Error extracting columns: {e}")
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
# DXF HELPER FUNCTIONS
# ========================================

def get_dxf_unit_factor(unit_code):
    """Convert DXF unit code to millimeter factor"""
    unit_factors = {
        0: 1.0,    # Unitless - assume mm
        1: 25.4,   # Inches → mm
        2: 304.8,  # Feet → mm
        4: 1.0,    # Millimeters
        5: 10.0,   # Centimeters → mm  
        6: 1000.0, # Meters → mm
    }
    return unit_factors.get(unit_code, 1.0)

def is_meaningful_entity(entity):
    """Check if entity should be considered for spatial analysis"""
    entity_type = entity.dxftype()
    
    # Include ALL meaningful entity types
    meaningful_types = [
        'LINE', 'LWPOLYLINE', 'POLYLINE', 'CIRCLE', 'ARC', 
        'ELLIPSE', 'SPLINE', 'INSERT', 'TEXT', 'MTEXT'
    ]
    return entity_type in meaningful_types

def create_default_dxf_item(name):
    """Create default DXF item"""
    return {
        'name': name,
        'width_mm': 100,
        'height_mm': 100,
        'num_shapes': 1,
        'num_letters': 0,
        'complexity_score': 2,
        'has_intricate_details': 0,
        'cutting_time_minutes': 10
    }

def get_entity_bounding_box(entity, unit_factor):
    """Calculate bounding box - IMPROVED TEXT DETECTION"""
    try:
        entity_type = entity.dxftype()
        points = []
        
        if entity_type == 'LINE':
            if hasattr(entity.dxf, 'start') and hasattr(entity.dxf, 'end'):
                start = entity.dxf.start
                end = entity.dxf.end
                points.extend([
                    (start.x if hasattr(start, 'x') else start[0], 
                     start.y if hasattr(start, 'y') else start[1]),
                    (end.x if hasattr(end, 'x') else end[0], 
                     end.y if hasattr(end, 'y') else end[1])
                ])
                
        elif entity_type == 'LWPOLYLINE':
            if hasattr(entity, 'vertices'):
                for v in entity.vertices():
                    points.append((v[0], v[1]))
                    
        elif entity_type == 'POLYLINE':
            if hasattr(entity, 'vertices'):
                for vertex in entity.vertices:
                    if hasattr(vertex.dxf, 'location'):
                        loc = vertex.dxf.location
                        points.append((loc.x if hasattr(loc, 'x') else loc[0], 
                                     loc.y if hasattr(loc, 'y') else loc[1]))
                
        elif entity_type == 'CIRCLE':
            if hasattr(entity.dxf, 'center') and hasattr(entity.dxf, 'radius'):
                center = entity.dxf.center
                radius = entity.dxf.radius
                cx = center.x if hasattr(center, 'x') else center[0]
                cy = center.y if hasattr(center, 'y') else center[1]
                points.extend([
                    (cx - radius, cy - radius),
                    (cx + radius, cy + radius)
                ])
                
        elif entity_type == 'ARC':
            if hasattr(entity.dxf, 'center') and hasattr(entity.dxf, 'radius'):
                center = entity.dxf.center
                radius = entity.dxf.radius
                cx = center.x if hasattr(center, 'x') else center[0]
                cy = center.y if hasattr(center, 'y') else center[1]
                points.extend([
                    (cx - radius, cy - radius),
                    (cx + radius, cy + radius)
                ])
                
        elif entity_type == 'ELLIPSE':
            if hasattr(entity.dxf, 'center') and hasattr(entity.dxf, 'major_axis'):
                center = entity.dxf.center
                major_axis = entity.dxf.major_axis
                cx = center.x if hasattr(center, 'x') else center[0]
                cy = center.y if hasattr(center, 'y') else center[1]
                radius = abs(major_axis.x if hasattr(major_axis, 'x') else major_axis[0])
                points.extend([
                    (cx - radius, cy - radius),
                    (cx + radius, cy + radius)
                ])
                
        elif entity_type in ['TEXT', 'MTEXT']:
            if hasattr(entity.dxf, 'insert'):
                insert_point = entity.dxf.insert
                ix = insert_point.x if hasattr(insert_point, 'x') else insert_point[0]
                iy = insert_point.y if hasattr(insert_point, 'y') else insert_point[1]
                
                # Better text size estimation
                text_height = getattr(entity.dxf, 'height', 3)  # Default 3mm
                
                # Get actual text for better width estimation
                text_content = ""
                if entity_type == 'TEXT' and hasattr(entity.dxf, 'text'):
                    text_content = str(entity.dxf.text)
                elif entity_type == 'MTEXT' and hasattr(entity, 'text'):
                    text_content = str(entity.text)
                
                text_length = len(text_content) if text_content else 3
                estimated_width = text_height * 0.7 * text_length  # Char width ~70% of height
                
                points.extend([
                    (ix, iy),
                    (ix + estimated_width, iy + text_height)
                ])
                
        elif entity_type == 'INSERT':
            if hasattr(entity.dxf, 'insert'):
                insert_point = entity.dxf.insert
                ix = insert_point.x if hasattr(insert_point, 'x') else insert_point[0]
                iy = insert_point.y if hasattr(insert_point, 'y') else insert_point[1]
                
                block_size = 20
                points.extend([
                    (ix - block_size/2, iy - block_size/2),
                    (ix + block_size/2, iy + block_size/2)
                ])
        
        elif entity_type == 'SPLINE':
            if hasattr(entity, 'control_points'):
                for cp in entity.control_points:
                    points.append((cp[0], cp[1]))
        
        # Convert to millimeters and calculate bounding box
        if points:
            xs = [p[0] * unit_factor for p in points]
            ys = [p[1] * unit_factor for p in points]
            
            return {
                'min_x': min(xs),
                'min_y': min(ys),
                'max_x': max(xs),
                'max_y': max(ys),
                'width': max(xs) - min(xs),
                'height': max(ys) - min(ys)
            }
        
        return None
        
    except Exception as e:
        print(f"Error calculating bbox for {entity.dxftype()}: {e}")
        return None

def calculate_cluster_bounding_box(cluster):
    """Calculate overall bounding box for a cluster of entities"""
    if not cluster:
        return None
    
    min_x = min(entity['bbox']['min_x'] for entity in cluster)
    min_y = min(entity['bbox']['min_y'] for entity in cluster)
    max_x = max(entity['bbox']['max_x'] for entity in cluster)
    max_y = max(entity['bbox']['max_y'] for entity in cluster)
    
    return {
        'min_x': min_x,
        'min_y': min_y,
        'max_x': max_x,
        'max_y': max_y,
        'width': max_x - min_x,
        'height': max_y - min_y
    }

def calculate_entity_distance(entity1, entity2):
    """Calculate minimum distance between two entity bounding boxes"""
    # Simple center-to-center distance
    dx = entity1['center_x'] - entity2['center_x']
    dy = entity1['center_y'] - entity2['center_y']
    return (dx**2 + dy**2)**0.5

def should_merge_clusters(cluster1, cluster2, threshold):
    """Check if two clusters should be merged based on bounding box proximity"""
    # Calculate combined bounding box for each cluster
    bbox1 = calculate_cluster_bounding_box(cluster1)
    bbox2 = calculate_cluster_bounding_box(cluster2)
    
    # Check if bounding boxes overlap or are close
    horizontal_gap = max(0, bbox1['min_x'] - bbox2['max_x'], bbox2['min_x'] - bbox1['max_x'])
    vertical_gap = max(0, bbox1['min_y'] - bbox2['max_y'], bbox2['min_y'] - bbox1['max_y'])
    
    max_gap = max(horizontal_gap, vertical_gap)
    return max_gap < threshold

def merge_close_clusters(clusters, merge_threshold):
    """Merge clusters that are close to each other"""
    if len(clusters) <= 1:
        return clusters
    
    merged = True
    while merged and len(clusters) > 1:
        merged = False
        new_clusters = []
        used = set()
        
        for i in range(len(clusters)):
            if i in used:
                continue
                
            current_cluster = clusters[i]
            merged_this_round = False
            
            for j in range(i + 1, len(clusters)):
                if j in used:
                    continue
                    
                # Check if clusters should be merged
                if should_merge_clusters(current_cluster, clusters[j], merge_threshold):
                    current_cluster.extend(clusters[j])
                    used.add(j)
                    merged = True
                    merged_this_round = True
            
            new_clusters.append(current_cluster)
            used.add(i)
        
        # Add any unused clusters
        for i in range(len(clusters)):
            if i not in used:
                new_clusters.append(clusters[i])
        
        clusters = new_clusters
    
    return clusters

def spatial_cluster_entities(entity_boxes, cluster_threshold=50):
    """
    Cluster entities based on spatial proximity
    cluster_threshold: distance in mm to consider entities part of same job
    """
    if not entity_boxes:
        return []
    
    clusters = []
    
    for entity_box in entity_boxes:
        added_to_cluster = False
        
        for cluster in clusters:
            # Check if entity is close to any entity in the cluster
            for cluster_entity in cluster:
                distance = calculate_entity_distance(entity_box, cluster_entity)
                if distance < cluster_threshold:
                    cluster.append(entity_box)
                    added_to_cluster = True
                    break
            if added_to_cluster:
                break
        
        if not added_to_cluster:
            # Start new cluster
            clusters.append([entity_box])
    
    # Merge clusters that are close to each other
    clusters = merge_close_clusters(clusters, cluster_threshold * 1.5)
    
    return clusters

def count_connected_line_groups(line_segments, tolerance=0.5):
    """
    Group connected line segments into shapes using connectivity tracking.
    Lines that share endpoints (within tolerance) are part of the same shape.
    
    Example: 4 connected lines forming a square = 1 shape, NOT 4 entities
    """
    if not line_segments:
        return 0
    
    from collections import defaultdict
    
    print(f"  Smart connectivity analysis: {len(line_segments)} line segments")
    
    # Extract endpoints from all line segments
    endpoints = defaultdict(list)
    line_data = []
    
    for idx, line in enumerate(line_segments):
        try:
            start = line.dxf.start
            end = line.dxf.end
            
            # Convert to tuples, rounding to tolerance for matching
            start_tuple = (round(start[0], 1), round(start[1], 1))
            end_tuple = (round(end[0], 1), round(end[1], 1))
            
            line_data.append({
                'idx': idx,
                'start': start_tuple,
                'end': end_tuple,
                'entity': line
            })
            
            # Map endpoints to line indices
            endpoints[start_tuple].append(idx)
            endpoints[end_tuple].append(idx)
            
        except Exception as e:
            print(f"  ⚠ Could not extract endpoints: {e}")
            continue
    
    # Build connectivity graph using Union-Find
    parent = list(range(len(line_data)))
    
    def find(i):
        if parent[i] != i:
            parent[i] = find(parent[i])
        return parent[i]
    
    def union(i, j):
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_i] = root_j
    
    # Connect lines that share endpoints
    for endpoint, line_indices in endpoints.items():
        for i in range(len(line_indices) - 1):
            union(line_indices[i], line_indices[i + 1])
    
    # Count unique connected groups
    unique_groups = len(set(find(i) for i in range(len(line_data))))
    
    print(f"  ✓ Found {unique_groups} connected line group(s)")
    
    # Debug: Show group composition
    groups_by_root = defaultdict(list)
    for idx in range(len(line_data)):
        root = find(idx)
        groups_by_root[root].append(idx)
    
    for group_num, (root, indices) in enumerate(sorted(groups_by_root.items()), 1):
        print(f"    Group {group_num}: {len(indices)} connected lines")
    
    return max(1, unique_groups)

def calculate_improved_complexity(shape_count, text_count, width, height):
    """
    Calculate complexity with density + element count ranges.
    Total elements = shape_count + (text_count / 10)
    Density = elements per 10,000mm²
    
    Element count ranges (primary):
      1-20   → complexity 1 (Very simple)
      21-40  → complexity 2 (Simple)
      41-60  → complexity 3 (Moderate)
      61-80  → complexity 4 (Complex)
      81+    → complexity 5 (Very complex)
    """
    # Avoid division by zero
    area = max(width * height, 1)
    
    # Calculate density (entities per 10,000mm²)
    density = (shape_count + text_count/10) / (area / 10000)
    
    # Total cutting elements (text counts less toward complexity)
    total_elements = shape_count + (text_count / 10)
    
    print(f"  Complexity calc: {total_elements:.1f} elements, density: {density:.3f}")
    
    # Element count-based thresholds (primary logic)
    if total_elements <= 20:
        complexity = 1  # Very simple: 1-20 elements
    elif total_elements <= 40:
        complexity = 2  # Simple: 21-40 elements
    elif total_elements <= 60:
        complexity = 3  # Moderate: 41-60 elements
    elif total_elements <= 80:
        complexity = 4  # Complex: 61-80 elements
    else:
        complexity = 5  # Very complex: 81+ elements
    
    print(f"  → Complexity score: {complexity}/5 (elements: {total_elements:.1f}, density: {density:.3f})")
    
    return complexity

def estimate_improved_cutting_time(shape_count, text_count, width, height):
    """
    Estimate cutting time with realiable parameters
    """
    # Base time on total cutting distance
    perimeter = (width + height) * 2
    
    # Time factors (minutes)
    setup_time = 2  # Setup and material loading
    perimeter_time = perimeter * 0.008  # ~0.5 minutes per 100mm perimeter
    shape_time = shape_count * 0.8  # ~48 seconds per shape
    text_time = text_count * 0.1  # ~6 seconds per character
    
    # Add complexity factor for intricate designs
    if shape_count > 30:
        complexity_multiplier = 1.3
    elif shape_count > 15:
        complexity_multiplier = 1.15
    else:
        complexity_multiplier = 1.0
    
    total_time = (setup_time + perimeter_time + shape_time + text_time) * complexity_multiplier
    
    # Minimum 5 minutes, maximum 120 minutes for reasonable jobs
    final_time = max(5, min(120, total_time))
    
    print(f"  Time estimate: {final_time:.1f} minutes (setup: {setup_time}, cutting: {final_time-setup_time:.1f})")
    
    return round(final_time, 1)

def analyze_entity_cluster(cluster, job_name, unit_factor):
    """Analyze a cluster of entities as a single job - HIGHLY IMPROVED VERSION"""
    try:
        shape_count = 0
        text_count = 0
        line_segments = []
        text_entities = []
        
        for entity_data in cluster:
            entity = entity_data['entity']
            entity_type = entity.dxftype()
            
            # Count text entities and their characters
            if entity_type in ['TEXT', 'MTEXT']:
                text_content = None
                
                if entity_type == 'TEXT':
                    if hasattr(entity.dxf, 'text'):
                        text_content = entity.dxf.text
                    elif hasattr(entity, 'dxf') and hasattr(entity.dxf, 'text'):
                        text_content = entity.dxf.text
                        
                elif entity_type == 'MTEXT':
                    if hasattr(entity, 'text'):
                        text_content = entity.text
                    elif hasattr(entity, 'plain_text'):
                        text_content = entity.plain_text()
                
                if text_content:
                    # Clean and count actual visible characters
                    clean_text = str(text_content).strip()
                    # Remove formatting codes if present
                    import re
                    clean_text = re.sub(r'\\[A-Za-z][^;]*;', '', clean_text)
                    # Count only alphanumeric characters and spaces
                    char_count = len([c for c in clean_text if c.isalnum() or c.isspace()])
                    text_count += char_count
                    text_entities.append(entity_type)
                    print(f"  Found {entity_type}: '{clean_text}' = {char_count} chars")
            
            # Count shape entities
            elif entity_type in ['LINE', 'LWPOLYLINE', 'POLYLINE', 'CIRCLE', 
                                'ARC', 'ELLIPSE', 'SPLINE', 'INSERT']:
                
                # Special handling for lines - group connected lines as single shapes
                if entity_type == 'LINE':
                    line_segments.append(entity)
                else:
                    shape_count += 1
        
        # Intelligently count lines as shapes (connected lines = 1 shape)
        grouped_line_shapes = count_connected_line_groups(line_segments)
        shape_count += grouped_line_shapes
        
        print(f"  Analysis: {shape_count} shapes, {text_count} letters, {len(text_entities)} text entities")
        
        # Use cluster bounding box for dimensions
        cluster_bbox = calculate_cluster_bounding_box(cluster)
        
        if cluster_bbox:
            width = cluster_bbox['width']
            height = cluster_bbox['height']
        else:
            width = height = 100
        
        # Calculate complexity and time
        complexity = calculate_improved_complexity(shape_count, text_count, width, height)
        cutting_time = estimate_improved_cutting_time(shape_count, text_count, width, height)
        
        return {
            'name': job_name,
            'width_mm': round(width, 2),
            'height_mm': round(height, 2),
            'num_shapes': shape_count,
            'num_letters': text_count,
            'complexity_score': complexity,
            'has_intricate_details': 1 if complexity >= 4 else 0,
            'cutting_time_minutes': round(cutting_time, 1),
            'cluster_size': len(cluster)
        }
        
    except Exception as e:
        print(f"Error analyzing entity cluster: {e}")
        import traceback
        print(traceback.format_exc())
        return create_default_dxf_item(job_name)

def detect_spatial_jobs(entities, unit_factor):
    """Detect separate jobs by spatial clustering of entities - WITH BETTER LOGGING"""
    # Step 1: Calculate bounding boxes for all entities
    entity_boxes = []
    
    print(f"\n=== Entity Type Breakdown ===")
    entity_type_counts = {}
    
    for entity in entities:
        entity_type = entity.dxftype()
        entity_type_counts[entity_type] = entity_type_counts.get(entity_type, 0) + 1
        
        bbox = get_entity_bounding_box(entity, unit_factor)
        if bbox and bbox['width'] > 0.1 and bbox['height'] > 0.1:  # Even smaller threshold
            entity_boxes.append({
                'entity': entity,
                'bbox': bbox,
                'center_x': bbox['min_x'] + bbox['width'] / 2,
                'center_y': bbox['min_y'] + bbox['height'] / 2
            })
    
    # Print entity type summary
    for etype, count in sorted(entity_type_counts.items()):
        print(f"  {etype}: {count}")
    
    print(f"\nEntities with valid bounding boxes: {len(entity_boxes)}/{len(entities)}")
    
    if not entity_boxes:
        return [create_default_dxf_item("Design")]
    
    # Step 2: Cluster entities by spatial proximity
    clusters = spatial_cluster_entities(entity_boxes)
    print(f"Spatial clusters found: {len(clusters)}")
    
    # Step 3: Analyze each cluster as a separate job
    jobs = []
    for i, cluster in enumerate(clusters):
        job_name = f"Job {i + 1}" if len(clusters) > 1 else "Design"
        print(f"\n--- Analyzing {job_name} ({len(cluster)} entities) ---")
        job_analysis = analyze_entity_cluster(cluster, job_name, unit_factor)
        jobs.append(job_analysis)
        print(f"✓ {job_name}: {job_analysis['width_mm']}x{job_analysis['height_mm']}mm, "
              f"{job_analysis['num_shapes']} shapes, {job_analysis['num_letters']} letters, "
              f"complexity {job_analysis['complexity_score']}/5")
    
    return jobs

# ========================================
# DXF FILE ANALYZER FUNCTIONS
# ========================================

def analyze_dxf_file(file_content):
    """Analyze DXF file using spatial detection - Fixed bytes handling"""
    try:
        print(f"=== DXF Spatial Analysis Started ===")
        print(f"File content type: {type(file_content)}")
        print(f"File content length: {len(file_content) if file_content else 0}")
        
        # Ensure we have bytes (handle both string and bytes input)
        if isinstance(file_content, str):
            print("Converting string to bytes...")
            file_content = file_content.encode('utf-8')
        
        if not file_content:
            return {
                'success': False,
                'error': 'Empty file content',
                'file_type': 'dxf'
            }
        
        # Read DXF file with better error handling
        import io
        import tempfile
        import os
        
        # Method 1: Try BytesIO first
        try:
            dxf_stream = io.BytesIO(file_content)
            import ezdxf
            doc = ezdxf.read(dxf_stream)
            print("✓ Successfully read DXF via BytesIO")
            
        except Exception as e1:
            print(f"BytesIO method failed: {e1}")
            
            # Method 2: Try temporary file
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.dxf', mode='wb') as temp_file:
                    temp_file.write(file_content)
                    temp_path = temp_file.name
                
                import ezdxf
                doc = ezdxf.readfile(temp_path)
                print("✓ Successfully read DXF via temporary file")
                
                # Clean up temp file
                os.unlink(temp_path)
                
            except Exception as e2:
                print(f"Temporary file method failed: {e2}")
                return {
                    'success': False, 
                    'error': f'Cannot read DXF file. File may be corrupted. Errors: {str(e1)}, {str(e2)}',
                    'file_type': 'dxf'
                }
        
        # Now analyze the DXF document
        msp = doc.modelspace()
        
        print(f"DXF Version: {doc.dxfversion}")
        print(f"Total entities: {len(msp)}")
        
        # Get units
        unit_code = doc.header.get('$INSUNITS', 0)
        unit_factor = get_dxf_unit_factor(unit_code)
        print(f"Units: {unit_code} → Factor: {unit_factor}")
        
        # Extract all meaningful entities
        all_entities = []
        for entity in msp:
            if is_meaningful_entity(entity):
                all_entities.append(entity)
        
        print(f"Meaningful entities found: {len(all_entities)}")
        
        if not all_entities:
            return {
                'success': False,
                'error': 'No meaningful design elements found in DXF file',
                'file_type': 'dxf'
            }
        
        # Detect separate jobs using spatial clustering
        jobs = detect_spatial_jobs(all_entities, unit_factor)
        print(f"Spatial detection found {len(jobs)} separate jobs")
        
        # Return appropriate response
        if len(jobs) > 1:
            return {
                'success': True,
                'file_type': 'dxf',
                'multiple_items': True,
                'items': jobs,
                'total_items': len(jobs),
                'detection_method': 'spatial',
                'message': f'Found {len(jobs)} separate jobs based on spatial arrangement'
            }
        else:
            return {
                'success': True,
                'file_type': 'dxf',
                'multiple_items': False,
                'items': jobs,
                'total_items': 1,
                'detection_method': 'spatial_single',
                'message': 'Single job detected'
            }
            
    except Exception as e:
        print(f"DXF spatial analysis error: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return {
            'success': False, 
            'error': f'DXF analysis failed: {str(e)}',
            'file_type': 'dxf'
        }

# ========================================
# PRICING FUNCTION
# ========================================

def round_price_smartly(price):
    """
    Round prices to neat whole numbers
    Examples:
    - 10,769.13 → 10,800
    - 5,432.67 → 5,450
    - 15,123.45 → 15,150
    - 999.99 → 1,000
    - 450.25 → 500
    """
    import math
    
    if price < 100:
        # Under ₦100: round to nearest 10
        return math.ceil(price / 10) * 10
    
    elif price < 1000:
        # ₦100-999: round to nearest 50
        return math.ceil(price / 50) * 50
    
    elif price < 10000:
        # ₦1,000-9,999: round to nearest 100
        return math.ceil(price / 100) * 100
    
    elif price < 100000:
        # ₦10,000-99,999: round to nearest 500
        return math.ceil(price / 500) * 500
    
    else:
        # ₦100,000+: round to nearest 1,000
        return math.ceil(price / 1000) * 1000

def predict_price(job_data):
    """Predict price using trained model - WITH SMART ROUNDING"""
    if model is None or columns is None:
        return None
    
    try:
        job_df = pd.DataFrame([job_data])
        job_df = pd.get_dummies(job_df, columns=['material', 'cutting_type'], 
                                prefix=['mat', 'cut'])
        
        for col in columns:
            if col not in job_df.columns:
                job_df[col] = 0
        
        job_df = job_df[columns]
        raw_price = model.predict(job_df)[0]
        
        # Apply smart rounding
        final_price = round_price_smartly(raw_price)
        
        print(f"Raw price: ₦{raw_price:,.2f} → Rounded: ₦{final_price:,.2f}")
        
        return final_price
        
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
# PDF GENERATION FUNCTION
# ========================================
def generate_quote_pdf(quote):
    """Generate PDF for a quote"""
    buffer = BytesIO()
    
    # Create PDF
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                           rightMargin=10*mm, leftMargin=10*mm,
                           topMargin=10*mm, bottomMargin=10*mm)
    
    # Container for PDF elements
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#E89D3C'),
        spaceAfter=15,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#333333'),
        spaceAfter=10,
        fontName='Helvetica-Bold'
    )
    
    # Add logo if exists
    logo_path = os.path.join(basedir, 'static', 'images', 'logo.png')
    if os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=50*mm, height=50*mm, kind='proportional')
            elements.append(logo)
            elements.append(Spacer(1, 10*mm))
        except:
            pass
    
    # Title
    elements.append(Paragraph("PRICE QUOTATION", title_style))
    elements.append(Spacer(1, 5*mm))
    
    # Company name
    company_style = ParagraphStyle(
        'Company',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#9B9B9B')
    )
    elements.append(Paragraph("BrainGain Tech Innovation Solutions", company_style))
    elements.append(Spacer(1, 10*mm))
    
    # Quote details box
    quote_info_data = [
        ['Quote Number:', quote.quote_number],
        ['Date:', quote.created_at.strftime('%B %d, %Y')],
        ['Status:', 'RUSH JOB' if quote.rush_job else 'Standard'],
    ]
    
    quote_info_table = Table(quote_info_data, colWidths=[50*mm, 90*mm])
    quote_info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F5F5F5')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(quote_info_table)
    elements.append(Spacer(1, 10*mm))
    
    # Customer Information
    if quote.customer_name or quote.customer_email:
        elements.append(Paragraph("Customer Information", heading_style))
        
        customer_data = []
        if quote.customer_name:
            customer_data.append(['Name:', quote.customer_name])
        if quote.customer_email:
            customer_data.append(['Email:', quote.customer_email])
        if quote.customer_phone:
            customer_data.append(['Phone:', quote.customer_phone])
        
        customer_table = Table(customer_data, colWidths=[50*mm, 90*mm])
        customer_table.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(customer_table)
        elements.append(Spacer(1, 10*mm))
    
    # Job Specifications
    elements.append(Paragraph("Job Specifications", heading_style))
    
    spec_data = [
        ['Material', 'Dimensions', 'Cutting Type', 'Quantity'],
        [
            f"{quote.material}\n({quote.thickness_mm}mm)",
            f"{quote.width_mm} × {quote.height_mm} mm",
            quote.cutting_type,
            str(quote.quantity)
        ]
    ]
    
    spec_table = Table(spec_data, colWidths=[45*mm, 45*mm, 45*mm, 35*mm])
    spec_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E89D3C')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(spec_table)
    elements.append(Spacer(1, 5*mm))
    
    # Additional Details
    detail_data = [
        ['Complexity:', f"{quote.complexity_score}/5"],
        ['Shapes:', str(quote.num_shapes)],
        ['Letters/Text:', str(quote.num_letters)],
        ['Estimated Time:', f"{quote.cutting_time_minutes} minutes"],
    ]
    
    detail_table = Table(detail_data, colWidths=[50*mm, 90*mm])
    detail_table.setStyle(TableStyle([
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(detail_table)
    elements.append(Spacer(1, 10*mm))
    
    # If this quote has multiple items, render an itemized table
    if hasattr(quote, 'items') and quote.items:
        elements.append(Paragraph("Items", heading_style))

        # Table header
        items_table_data = [[
            'Item', 'Material (thickness)', 'Dimensions (mm)', 'Qty', 'Unit Price', 'Subtotal'
        ]]

        # Add each item as a row
        total_calc = 0.0
        for item in quote.items:
            dims = f"{item.width_mm} × {item.height_mm}"
            unit_price = item.item_price
            subtotal = unit_price * (item.quantity or 1)
            total_calc += subtotal
            items_table_data.append([
                item.item_name or 'Item',
                f"{item.material} ({item.thickness_mm}mm)",
                dims,
                str(item.quantity),
                f"₦{unit_price:,.2f}",
                f"₦{subtotal:,.2f}"
            ])

        # Add a totals row
        items_table_data.append(['', '', '', '', 'TOTAL', f"₦{total_calc:,.2f}"])

        items_table = Table(items_table_data, colWidths=[45*mm, 40*mm, 40*mm, 20*mm, 30*mm, 30*mm])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E89D3C')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
            ('GRID', (-2, -1), (-1, -1), 1, colors.HexColor('#E89D3C')),
            ('SPAN', (0, -1), (3, -1)),
            ('ALIGN', (4, -1), (5, -1), 'RIGHT'),
            ('FONTNAME', (4, -1), (5, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FFF8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        elements.append(items_table)
        elements.append(Spacer(1, 8*mm))

        # If there is any note, show beneath items
        if quote.notes:
            elements.append(Paragraph("Additional Notes", heading_style))
            notes_style = ParagraphStyle(
                'Notes',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#666666')
            )
            elements.append(Paragraph(quote.notes, notes_style))
            elements.append(Spacer(1, 6*mm))

        # Final Price box for bulk
        elements.append(Paragraph("Pricing", heading_style))
        if quote.discount_applied:
            price_data = [
                ['Subtotal', f"N{quote.original_price:,.2f}"],
                [f'Discount ({quote.discount_percentage}%)', f"-N{quote.discount_amount:,.2f}"],
                ['TOTAL AMOUNT', f"N{quote.quoted_price:,.2f}"]
            ]
        else:
            price_data = [
                ['TOTAL AMOUNT', f"N{quote.quoted_price:,.2f}"]
            ]
        price_table = Table(price_data, colWidths=[120*mm, 50*mm])
        price_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFF8F0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#E89D3C')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('GRID', (0, 0), (-1, -1), 2, colors.HexColor('#E89D3C')),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(price_table)

    else:
        # Pricing Section
        elements.append(Paragraph("Pricing", heading_style))
    
    if quote.discount_applied:
        # Show discount breakdown
        price_data = [
            ['Subtotal', f"N{quote.original_price:,.2f}"],
            [f'Discount ({quote.discount_percentage}%)', f"-N{quote.discount_amount:,.2f}"],
            ['TOTAL AMOUNT', f"N{quote.quoted_price:,.2f}"]
        ]
    else:
        # No discount
        price_data = [
            ['TOTAL AMOUNT', f"N{quote.quoted_price:,.2f}"]
        ]
    
    price_table = Table(price_data, colWidths=[120*mm, 50*mm])
    
    # Styling
    if quote.discount_applied:
        price_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 1), colors.HexColor('#FFFFFF')),
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#FFF8F0')),
            ('TEXTCOLOR', (0, 0), (-1, 1), colors.HexColor('#333333')),
            ('TEXTCOLOR', (0, 2), (-1, 2), colors.HexColor('#E89D3C')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 1), 12),
            ('FONTSIZE', (0, 2), (-1, 2), 14),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E89D3C')),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
    else:
        price_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFF8F0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#E89D3C')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('GRID', (0, 0), (-1, -1), 2, colors.HexColor('#E89D3C')),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
    
    elements.append(price_table)
    elements.append(Spacer(1, 10*mm))
    
    # Notes
    if quote.notes:
        elements.append(Paragraph("Additional Notes", heading_style))
        notes_style = ParagraphStyle(
            'Notes',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666')
        )
        elements.append(Paragraph(quote.notes, notes_style))
        elements.append(Spacer(1, 10*mm))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#999999'),
        alignment=TA_CENTER
    )
    elements.append(Spacer(1, 15*mm))
    elements.append(Paragraph("This quote is valid for 7 days from the date of issue.", footer_style))
    elements.append(Paragraph("Generated by BrainGain Tech CNC/Laser Pricing System", footer_style))
    
    # Build PDF
    doc.build(elements)
    
    # Get PDF data
    pdf_data = buffer.getvalue()
    buffer.close()
    
    return pdf_data

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

# ========================================
# AUTH ROUTES
# ========================================

@app.route('/admin/login')
def admin_login():
    """Admin login page"""
    # If already logged in, redirect to dashboard
    if session.get('access_token'):
        return redirect('/admin/dashboard')
    return render_template('admin_login.html')

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """Handle login via Supabase"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        # Authenticate with Supabase
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if auth_response.user:
            # Store tokens in session
            session.permanent = True
            session['access_token'] = auth_response.session.access_token
            session['refresh_token'] = auth_response.session.refresh_token
            session['user_email'] = auth_response.user.email
            
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'redirect': '/admin/dashboard'
            })
        else:
            return jsonify({'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        error_message = str(e)
        # Handle common Supabase auth errors
        if 'Invalid login credentials' in error_message:
            return jsonify({'error': 'Invalid email or password'}), 401
        elif 'Email not confirmed' in error_message:
            return jsonify({'error': 'Please verify your email first'}), 401
        else:
            print(f"Login error: {e}")
            return jsonify({'error': 'Login failed. Please try again.'}), 500

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """Handle logout"""
    try:
        token = session.get('access_token')
        if token:
            # Sign out from Supabase
            supabase.auth.sign_out()
        
        # Clear session
        session.clear()
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully',
            'redirect': '/admin/login'
        })
    except Exception as e:
        print(f"Logout error: {e}")
        session.clear()  # Clear session anyway
        return jsonify({
            'success': True,
            'redirect': '/admin/login'
        })

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    """Check if user is authenticated (for frontend to verify session)"""
    token = session.get('access_token')
    
    if not token:
        return jsonify({'authenticated': False}), 401
    
    try:
        user_response = supabase.auth.get_user(token)
        if user_response and user_response.user:
            return jsonify({
                'authenticated': True,
                'user': {
                    'email': user_response.user.email,
                    'id': user_response.user.id
                }
            })
        else:
            session.clear()
            return jsonify({'authenticated': False}), 401
    except:
        session.clear()
        return jsonify({'authenticated': False}), 401

# ========================================
# ADMIN ROUTES (PROTECTED)
# ========================================

@app.route('/admin')
def admin_redirect():
    """Redirect /admin to /admin/dashboard"""
    return redirect('/admin/dashboard')

@app.route('/admin/dashboard')
@requires_auth
def admin_dashboard():
    """Admin dashboard - protected route"""
    user_email = session.get('user_email', 'Admin')
    return render_template('admin_dashboard.html', user_email=user_email)

# ========================================
# DXF ANALYSIS ROUTE
# ========================================

@app.route('/analyze_dxf_file', methods=['POST'])
def analyze_dxf_file_route():
    """Analyze uploaded DXF file"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})
    
    if not file.filename.lower().endswith('.dxf'):
        return jsonify({'success': False, 'error': 'Only DXF files supported'})
    
    try:
        dxf_content = file.read()
        analysis = analyze_dxf_file(dxf_content)
        return jsonify(analysis)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})
    
@app.route('/debug_upload', methods=['POST'])
def debug_upload():
    """Debug route to check file upload issues"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})
    
    debug_info = {
        'filename': file.filename,
        'content_type': file.content_type,
        'content_length': 0,
        'file_type': 'unknown'
    }
    
    try:
        file_content = file.read()
        debug_info['content_length'] = len(file_content)
        debug_info['file_type'] = 'dxf' if file.filename.lower().endswith('.dxf') else 'svg'
        debug_info['content_type_received'] = type(file_content).__name__
        
        # Check first few bytes for DXF signature
        if len(file_content) > 10:
            debug_info['first_10_bytes'] = file_content[:10].hex()
            debug_info['first_20_chars'] = file_content[:20].decode('utf-8', errors='ignore')
        
        return jsonify({'success': True, 'debug_info': debug_info})
        
    except Exception as e:
        debug_info['error'] = str(e)
        return jsonify({'success': False, 'debug_info': debug_info})

# ========================================
# SMART PRICING WITH INVENTORY INTEGRATION
# ========================================

def check_material_availability(material, thickness, width_mm, height_mm, color=None):
    """
    Check if material is available in inventory (with color matching)
    """
    try:
        # Build query with color filter
        query = Inventory.query.filter(
            db.func.lower(Inventory.material_name) == material.lower(),
            Inventory.thickness_mm == thickness
        )
        
        # Add color filter if specified
        if color:
            query = query.filter(db.func.lower(Inventory.color) == color.lower())
        
        inventory_item = query.first()
        
        if not inventory_item:
            # Check if material exists in other colors
            alternatives = Inventory.query.filter(
                db.func.lower(Inventory.material_name) == material.lower(),
                Inventory.thickness_mm == thickness
            ).all()
            
            if alternatives:
                alt_colors = [
                    f"{item.color} ({item.quantity_on_hand} sheets)" 
                    for item in alternatives 
                    if item.quantity_on_hand > 0
                ]
                
                return {
                    'available': False,
                    'in_stock': False,
                    'stock_count': 0,
                    'material_cost': 0,
                    'message': f'{material} {thickness}mm in {color} not found',
                    'alternatives': alt_colors,
                    'warning': f'Available in: {", ".join(alt_colors)}' if alt_colors else 'Material not in inventory'
                }
            else:
                return {
                    'available': False,
                    'in_stock': False,
                    'stock_count': 0,
                    'material_cost': 0,
                    'message': f'{material} ({thickness}mm) not found in inventory',
                    'warning': 'Material not tracked in inventory'
                }
        
        # Calculate area needed in square feet
        area_sq_mm = width_mm * height_mm
        area_sq_ft = area_sq_mm / 92903
        
        # Calculate material cost
        material_cost = area_sq_ft * inventory_item.price_per_sq_ft
        
        # Check if enough stock
        in_stock = inventory_item.quantity_on_hand > 0
        
        result = {
            'available': True,
            'in_stock': in_stock,
            'stock_count': inventory_item.quantity_on_hand,
            'material_cost': round(material_cost, 2),
            'price_per_sq_ft': inventory_item.price_per_sq_ft,
            'price_per_sheet': inventory_item.price_per_sheet,
            'area_sq_ft': round(area_sq_ft, 4),
            'color': inventory_item.color,
            'inventory_id': inventory_item.id
        }
        
        if in_stock:
            result['message'] = f'✅ In Stock ({inventory_item.quantity_on_hand} sheets available)'
        else:
            result['message'] = f'❌ Out of Stock - Need to reorder'
            result['warning'] = 'Material currently unavailable'
        
        return result
        
    except Exception as e:
        print(f"Error checking inventory: {e}")
        return {
            'available': False,
            'in_stock': False,
            'stock_count': 0,
            'material_cost': 0,
            'message': 'Error checking inventory',
            'error': str(e)
        }

# ========================================
# UPDATED CALCULATE PRICE ROUTE
# ========================================

@app.route('/calculate_price', methods=['POST'])
def calculate_price():
    """Calculate price with inventory integration (color-aware)"""
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
        
        # Get color if provided
        color = data.get('color')
        
        # Get AI predicted price
        price = predict_price(job_data)
        
        if price is None:
            return jsonify({'success': False, 'error': 'Could not calculate price'})
        
        # Check inventory availability (with color)
        inventory_check = check_material_availability(
            job_data['material'],
            job_data['thickness_mm'],
            job_data['width_mm'],
            job_data['height_mm'],
            color  # Pass color parameter
        )
        
        # Build response
        response = {
            'success': True,
            'price': price,
            'inventory': inventory_check
        }
        
        # Add warnings if necessary
        warnings = []
        if not inventory_check['in_stock']:
            warnings.append(inventory_check['message'])
            
            # Add alternatives if available
            if inventory_check.get('alternatives'):
                warnings.append(f"Try: {inventory_check.get('warning', '')}")
        
        if warnings:
            response['warnings'] = warnings
        
        return jsonify(response)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

# ========================================
# BULK PRICING WITH INVENTORY CHECK
# ========================================

@app.route('/calculate_bulk_prices', methods=['POST'])
def calculate_bulk_prices():
    """Calculate prices for multiple items with inventory checks"""
    try:
        items = request.get_json().get('items', [])
        results = []
        
        total_material_cost = 0
        all_in_stock = True
        warnings = []
        
        for item in items:
            job_data = {
                'material': item['material'],
                'thickness_mm': float(item['thickness']),
                'num_letters': int(item.get('letters', 0)),
                'num_shapes': int(item.get('shapes', 1)),
                'complexity_score': int(item.get('complexity', 3)),
                'has_intricate_details': int(item.get('details', 0)),
                'width_mm': float(item['width']),
                'height_mm': float(item['height']),
                'cutting_type': item['cuttingType'],
                'cutting_time_minutes': float(item['time']),
                'quantity': int(item.get('quantity', 1)),
                'rush_job': int(item.get('rush', 0))
            }
            
            price = predict_price(job_data)
            inventory_check = check_material_availability(
                job_data['material'],
                job_data['thickness_mm'],
                job_data['width_mm'],
                job_data['height_mm']
            )
            
            item_result = {
                'item_id': item.get('id'),
                'price': price,
                'inventory': inventory_check,
                'material_cost': inventory_check['material_cost'] * job_data['quantity']
            }
            
            results.append(item_result)
            total_material_cost += item_result['material_cost']
            
            if not inventory_check['in_stock']:
                all_in_stock = False
                warnings.append(f"{item.get('name', 'Item')}: {inventory_check['message']}")
        
        return jsonify({
            'success': True,
            'items': results,
            'total_material_cost': round(total_material_cost, 2),
            'all_in_stock': all_in_stock,
            'warnings': warnings if warnings else None
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

# ========================================
# QUOTE MANAGEMENT ROUTES
# ========================================

# ========================================
# APPLY DISCOUNT TO QUOTE
# ========================================

@app.route('/api/quote/<int:quote_id>/apply-discount', methods=['POST'])
def apply_discount_to_quote(quote_id):
    """
    Apply discount to an existing saved quote
    Allows: 2%, 5%, 10%, or custom percentage
    Minimum amount: ₦10,500
    """
    try:
        data = request.get_json()
        discount_percent = float(data.get('discount_percentage', 0))
        
        # Validate discount percentage
        if discount_percent <= 0 or discount_percent > 100:
            return jsonify({
                'success': False,
                'error': 'Discount must be between 0 and 100%'
            }), 400
        
        # Get the quote
        quote = Quote.query.get(quote_id)
        if not quote:
            return jsonify({
                'success': False,
                'error': 'Quote not found'
            }), 404
        
        # Check if discount already applied
        if quote.discount_applied:
            return jsonify({
                'success': False,
                'error': 'Discount already applied to this quote. Cannot apply twice.'
            }), 400
        
        # Get current price (or original if already discounted somehow)
        current_price = quote.quoted_price
        
        # Check minimum amount (₦10,500)
        if current_price < 10500:
            return jsonify({
                'success': False,
                'error': f'Discount cannot be applied. Minimum amount: ₦10,500. Current: ₦{current_price:,.2f}'
            }), 400
        
        # Calculate discount
        discount_amount = current_price * (discount_percent / 100)
        new_price = current_price - discount_amount
        
        # Update quote
        quote.original_price = current_price
        quote.discount_percentage = discount_percent
        quote.discount_amount = discount_amount
        quote.quoted_price = new_price
        quote.discount_applied = True
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{discount_percent}% discount applied successfully!',
            'original_price': current_price,
            'discount_percentage': discount_percent,
            'discount_amount': discount_amount,
            'new_price': new_price,
            'quote': quote.to_dict()
        })
        
    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Invalid discount percentage'
        }), 400
    except Exception as e:
        db.session.rollback()
        print(f"Error applying discount: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========================================
# APPLY DISCOUNT TO CURRENT QUOTE (BEFORE SAVING)
# ========================================

@app.route('/api/calculate-discount', methods=['POST'])
def calculate_discount():
    """
    Calculate discount for a quote before saving
    Used in the result box discount button
    """
    try:
        data = request.get_json()
        current_price = float(data.get('current_price', 0))
        discount_percent = float(data.get('discount_percentage', 0))
        
        # Validate
        if discount_percent <= 0 or discount_percent > 100:
            return jsonify({
                'success': False,
                'error': 'Discount must be between 0 and 100%'
            }), 400
        
        # Check minimum amount
        if current_price < 10500:
            return jsonify({
                'success': False,
                'error': f'Discount cannot be applied. Minimum amount: ₦10,500. Current: ₦{current_price:,.2f}'
            }), 400
        
        # Calculate discount
        discount_amount = current_price * (discount_percent / 100)
        new_price = current_price - discount_amount
        
        return jsonify({
            'success': True,
            'original_price': current_price,
            'discount_percentage': discount_percent,
            'discount_amount': discount_amount,
            'new_price': new_price
        })
        
    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Invalid price or discount percentage'
        }), 400
    except Exception as e:
        print(f"Error calculating discount: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =======================================
# SINGLE QUOTE SAVING ROUTE WITH DISCOUNT
# =======================================

@app.route('/save_quote', methods=['POST'])
def save_quote():
    """Save a quote to database (with optional discount)"""
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
        
        # Get discount data if present
        discount_applied = data.get('discount_applied', False)
        discount_percentage = float(data.get('discount_percentage', 0))
        discount_amount = float(data.get('discount_amount', 0))
        original_price = float(data.get('original_price')) if data.get('original_price') else None
        final_price = float(data['price'])
        
        # Create new quote
        quote = Quote(
            quote_number=quote_number,
            customer_name=data.get('customer_name', ''),
            customer_email=data.get('customer_email', ''),
            customer_phone=data.get('customer_phone', ''),
            customer_whatsapp=data.get('customer_whatsapp', ''),
            material=data['material'],
            material_color=data.get('color'),
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
            quoted_price=final_price,
            discount_applied=discount_applied,
            discount_percentage=discount_percentage,
            discount_amount=discount_amount,
            original_price=original_price,
            notes=data.get('notes', '')
        )
        
        db.session.add(quote)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'quote_id': quote.id,
            'quote_number': quote_number,
            'message': f'Quote {quote_number} saved successfully!'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error saving quote: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

# =======================================
# BULK QUOTE SAVING ROUTE
# =======================================

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
        
        # Get discount data if present
        discount_applied = data.get('discount_applied', False)
        discount_percentage = float(data.get('discount_percentage', 0))
        discount_amount = float(data.get('discount_amount', 0))
        original_price = float(data.get('original_price')) if data.get('original_price') else None
        final_price = float(data.get('price', total_price)) if data.get('price') else total_price
        
        # Use first item's details for main quote (for backward compatibility)
        first_item = items_data[0] if items_data else {}
        
        # Create main quote
        quote = Quote(
            quote_number=quote_number,
            customer_name=data.get('customer_name', ''),
            customer_email=data.get('customer_email', ''),
            customer_phone=data.get('customer_phone', ''),
            customer_whatsapp=data.get('customer_whatsapp', ''),
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
            quoted_price=final_price,
            discount_applied=discount_applied,
            discount_percentage=discount_percentage,
            discount_amount=discount_amount,
            original_price=original_price,
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
@requires_auth
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

@app.route('/get_quote/<int:quote_id>')
def get_quote(quote_id):
    """Get a single quote by ID"""
    try:
        quote = Quote.query.get(quote_id)
        if quote:
            return jsonify({
                'success': True,
                'quote': quote.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Quote not found'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })
    
@app.route('/download_quote_pdf/<int:quote_id>')
def download_quote_pdf(quote_id):
    """Generate and download quote as PDF"""
    try:
        quote = Quote.query.get(quote_id)
        if not quote:
            return jsonify({'success': False, 'error': 'Quote not found'}), 404
        
        # Generate PDF
        pdf_data = generate_quote_pdf(quote)
        
        # Create response
        from flask import make_response
        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=Quote_{quote.quote_number}.pdf'
        
        return response
        
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/share_quote_whatsapp/<int:quote_id>', methods=['POST', 'GET'])
def share_quote_whatsapp(quote_id):
    """Generate WhatsApp share link with PDF - supports direct customer messaging"""
    try:
        quote = Quote.query.get(quote_id)
        if not quote:
            return jsonify({'success': False, 'error': 'Quote not found'}), 404
        
        # Get WhatsApp number if provided (from request)
        whatsapp_number = None
        if request.method == 'POST':
            data = request.get_json() or {}
            whatsapp_number = data.get('whatsapp_number', '').strip()
        elif request.method == 'GET':
            whatsapp_number = request.args.get('whatsapp_number', '').strip()
        
        # Generate the PDF download link
        base_url = request.host_url.rstrip('/')
        pdf_link = f"{base_url}/download_quote_pdf/{quote_id}"
        
        # Create a message with PDF link
        message = f"""
🔷 *PRICE QUOTATION* 🔷
_BrainGain Tech Innovation Solutions_

📋 *Quote:* {quote.quote_number}
📅 *Date:* {quote.created_at.strftime('%B %d, %Y')}

💰 *TOTAL AMOUNT: ₦{quote.quoted_price:,.2f}*

📎 *Download PDF Quote:*
{pdf_link}

_Quote valid for 7 days_
_Generated by BrainGain Tech Pricing System_
        """.strip()
        
        # Generate WhatsApp link based on whether customer number is provided
        whatsapp_link = None
        if whatsapp_number:
            # Direct message to customer (mobile deeplink format)
            # Ensure number has no special chars except +
            clean_number = ''.join(c for c in whatsapp_number if c.isdigit() or c == '+')
            # WhatsApp direct chat link: https://wa.me/{number}?text={message}
            import urllib.parse
            encoded_message = urllib.parse.quote(message)
            whatsapp_link = f"https://wa.me/{clean_number}?text={encoded_message}"
        
        return jsonify({
            'success': True,
            'message': message,
            'pdf_link': pdf_link,
            'whatsapp_link': whatsapp_link,
            'quote_number': quote.quote_number,
            'has_customer_number': bool(whatsapp_number)
        })
        
    except Exception as e:
        import traceback
        print(f"WhatsApp share error: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500  

# ========================================
# INVENTORY MANAGEMENT ROUTES
# ========================================

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    items = Inventory.query.all()
    return jsonify([i.to_dict() for i in items])

@app.route('/api/inventory/history/<int:item_id>', methods=['GET'])
@requires_auth
def get_stock_history(item_id):
    """Get the In/Out history for a specific material"""
    transactions = InventoryTransaction.query.filter_by(inventory_id=item_id).order_by(InventoryTransaction.created_at.desc()).all()
    return jsonify([t.to_dict() for t in transactions])

@app.route('/api/inventory/add', methods=['POST'])
@requires_auth
def add_inventory():
    """Updated to handle both price_per_sq_ft and price_per_sheet"""
    try:
        data = request.json
        
        # Parse Inputs
        material = data.get('material')
        color = data.get('color', 'Default')
        thickness = float(data.get('thickness', 0))
        width = float(data.get('width', 0))
        height = float(data.get('height', 0))
        qty_change = int(data.get('quantity', 0))
        price_sq_ft = float(data.get('price_sq_ft', 0))
        price_sheet = float(data.get('price_sheet', 0))  # NEW
        note = data.get('note', 'Initial Stock')

        # Check for existing item (match by material, color, AND thickness)
        existing = Inventory.query.filter_by(
            material_name=material,
            color=color,
            thickness_mm=thickness
        ).first()

        if existing:
            # Update existing item
            existing.quantity_on_hand += qty_change
            existing.price_per_sq_ft = price_sq_ft
            existing.price_per_sheet = price_sheet  # NEW
            existing.updated_at = datetime.utcnow()
            
            # Log Transaction
            trans_type = 'stock_in' if qty_change > 0 else 'stock_out'
            new_trans = InventoryTransaction(
                inventory_id=existing.id,
                change_amount=qty_change,
                transaction_type=trans_type,
                note=note
            )
            db.session.add(new_trans)
            action = "updated"
        else:
            # Create new item
            new_item = Inventory(
                material_name=material,
                color=color,
                thickness_mm=thickness,
                sheet_width_mm=width,
                sheet_height_mm=height,
                quantity_on_hand=qty_change,
                price_per_sq_ft=price_sq_ft,
                price_per_sheet=price_sheet  # NEW
            )
            db.session.add(new_item)
            db.session.flush()
            
            # Log Initial Transaction
            new_trans = InventoryTransaction(
                inventory_id=new_item.id,
                change_amount=qty_change,
                transaction_type='stock_in',
                note="New Material Created"
            )
            db.session.add(new_trans)
            action = "created"

        db.session.commit()
        return jsonify({"status": "success", "message": f"Stock {action} successfully"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/inventory/colors', methods=['GET'])
def get_available_colors():
    """
    Get all available colors for a specific material and thickness
    Query params: material, thickness
    Returns colors with stock count
    """
    try:
        material = request.args.get('material', '')
        thickness_str = request.args.get('thickness', '')
        
        if not material or not thickness_str:
            return jsonify({
                'success': False,
                'error': 'Missing material or thickness parameter'
            }), 400
        
        try:
            thickness = float(thickness_str)
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid thickness format'
            }), 400
        
        # Query inventory for matching material and thickness
        items = Inventory.query.filter_by(
            material_name=material,
            thickness_mm=thickness
        ).all()
        
        # Build color list with stock info
        colors = []
        for item in items:
            colors.append({
                'color': item.color or 'Default',
                'stock': item.quantity_on_hand,
                'in_stock': item.quantity_on_hand > 0,
                'price_sq_ft': item.price_per_sq_ft,
                'price_sheet': item.price_per_sheet
            })
        
        return jsonify({
            'success': True,
            'colors': colors
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/inventory/delete/<int:item_id>', methods=['DELETE'])
@requires_auth
def delete_inventory(item_id):
    try:
        item = Inventory.query.get(item_id)
        if item:
            db.session.delete(item)
            db.session.commit()
            return jsonify({"status": "success", "message": "Item deleted"})
        return jsonify({"status": "error", "message": "Item not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ========================================
# MODEL TRAINING ROUTES
# ========================================

@app.route('/add_training_job', methods=['POST'])
@requires_auth
def add_training_job():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        # Helper: Safely convert to float/int, returning 0 if empty or invalid
        def safe_float(val):
            try:
                if val is None or str(val).strip() == "": return 0.0
                return float(val)
            except (ValueError, TypeError):
                return 0.0

        def safe_int(val):
            try:
                if val is None or str(val).strip() == "": return 0
                return int(float(val)) # Handle "3.0" strings safely
            except (ValueError, TypeError):
                return 0

        # Create new record safely
        new_entry = TrainingData(
            material=data.get('material', 'Unknown'),
            thickness_mm=safe_float(data.get('thickness_mm')),
            num_letters=safe_int(data.get('num_letters')),
            num_shapes=safe_int(data.get('num_shapes')),
            complexity_score=safe_int(data.get('complexity_score')) or 1,
            has_intricate_details=safe_int(data.get('has_intricate_details')),
            width_mm=safe_float(data.get('width_mm')),
            height_mm=safe_float(data.get('height_mm')),
            cutting_type=data.get('cutting_type', 'Laser'),
            cutting_time_minutes=safe_float(data.get('cutting_time_minutes')),
            quantity=safe_int(data.get('quantity')) or 1,
            rush_job=safe_int(data.get('rush_job')),
            price=safe_float(data.get('price'))
        )
        
        db.session.add(new_entry)
        db.session.commit()
        
        return jsonify({"success": True, "message": "Job added to database!"})
        
    except Exception as e:
        print(f"ERROR Adding Job: {e}") 
        db.session.rollback()
        return jsonify({"success": False, "error": f"Server Error: {str(e)}"}), 500

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
@requires_auth
def retrain_model():
    """Retrain the pricing model with current data from Supabase"""
    # Declare globals at the start of the function
    global model, columns, MODEL_PATH
    
    try:
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import mean_absolute_error, r2_score as calculate_r2
        from sklearn.ensemble import RandomForestRegressor
        import pandas as pd
        import pickle
        import os

        # 1. Load data from Supabase instead of CSV
        # We query the TrainingData model and convert it to a DataFrame
        records = TrainingData.query.all()
        if not records:
             return jsonify({
                'success': False,
                'error': 'The training_data table is empty. Add some jobs first!'
            })
            
        df = pd.DataFrame([r.to_dict() for r in records])
        
        # 2. Data Cleaning (Ensuring all numeric fields are proper floats/ints)
        numeric_cols = [
            'thickness_mm', 'width_mm', 'height_mm', 'num_letters', 
            'num_shapes', 'complexity_score', 'cutting_time_minutes', 
            'quantity', 'price'
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Remove any rows that failed conversion
        df = df.dropna()

        # 3. Training Requirements Logic
        prev_total = 0
        if os.path.exists(MODEL_PATH):
            try:
                with open(MODEL_PATH, 'rb') as f:
                    prev_saved = pickle.load(f)
                    prev_total = int(prev_saved.get('total_jobs', 0) or 0)
            except Exception:
                prev_total = 0

        new_jobs = max(0, len(df) - prev_total)

        # Requirement: At least 20 total jobs, and 20 NEW jobs if a model exists
        if prev_total > 0:
            if new_jobs < 20:
                return jsonify({
                    'success': False,
                    'error': f'Need at least 20 NEW jobs since last model. New jobs: {new_jobs} (Total: {len(df)})'
                })
        else:
            if len(df) < 20:
                return jsonify({
                    'success': False,
                    'error': f'Need at least 20 total jobs to train. Current: {len(df)}'
                })
        
        # 4. Feature Engineering (One-Hot Encoding)
        # This handles 'material' and 'cutting_type' strings automatically
        df_encoded = pd.get_dummies(df, columns=['material', 'cutting_type'], prefix=['mat', 'cut'])
        
        X = df_encoded.drop(['price'], axis=1)
        y = df_encoded['price']
        
        # 5. Model Training
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        new_model = RandomForestRegressor(
            n_estimators=150,
            max_depth=20,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
        
        new_model.fit(X_train, y_train)
        
        # 6. Evaluation
        y_pred = new_model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = calculate_r2(y_test, y_pred)
        
        # 7. Save to Persistent Storage (ALWAYS save to instance/)
        # Construct the persistent storage path for the new model
        persistent_model_path = os.path.join(INSTANCE_PATH, MODEL_FILENAME)
        
        model_data = {
            'model': new_model,
            'columns': X.columns.tolist(), # Store columns as list for easier matching
            'training_date': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_jobs': len(df),
            'r2_score': r2,
            'mae': mae
        }
        
        with open(persistent_model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        print(f"Model saved to persistent storage: {persistent_model_path}")
        
        # Update global variables so the app uses the new model immediately
        model = new_model
        columns = X.columns.tolist()  # Convert to list for consistency with saved format
        MODEL_PATH = persistent_model_path  # Update to point to persistent storage
        
        return jsonify({
            'success': True,
            'message': 'Model retrained successfully using Supabase data!',
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

# =======================================
# HEALTH CHECK ROUTE
# =======================================

@app.route('/health')
@requires_auth
def health():
    """Check if app is running"""
    return jsonify({
        'status': 'running',
        'model_loaded': model is not None,
        'company': 'BrainGain Tech Innovation Solutions'
    })

# ========================================
# APPLICATION INITIALIZATION
# ========================================

def init_app():
    """Initialize application - create database and ensure data directories"""
    with app.app_context():
        # Create all database tables
        db.create_all()
        print("✅ Database tables created")
        
        # Ensure data directory exists
        os.makedirs(os.path.join(basedir, 'data'), exist_ok=True)
        
        # Create empty CSV if it doesn't exist
        if not os.path.exists(CSV_PATH):
            df = pd.DataFrame(columns=[
                'material', 'thickness_mm', 'num_letters', 'num_shapes',
                'complexity_score', 'has_intricate_details', 'width_mm',
                'height_mm', 'cutting_type', 'cutting_time_minutes',
                'quantity', 'rush_job', 'price'
            ])
            df.to_csv(CSV_PATH, index=False)
            print("Created empty training CSV")

# ========================================
# RUN APPLICATION
# ========================================

if __name__ == '__main__':
    # Local development
    init_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    # Production - run init when imported by gunicorn
    init_app()