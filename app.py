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

app = Flask(__name__)

# Database configuration - Production ready
basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, "instance")

# Ensure instance directory exists
os.makedirs(instance_path, exist_ok=True)
os.makedirs(os.path.join(basedir, 'data'), exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "quotes.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
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
    customer_whatsapp = db.Column(db.String(20))
    
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
            'customer_whatsapp': self.customer_whatsapp,
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

MODEL_PATH = os.path.join(basedir, 'data', 'cnc_laser_pricing_model.pkl')
CSV_PATH = os.path.join(basedir, 'data', 'cnc_historical_jobs.csv')

try:
    with open(MODEL_PATH, 'rb') as f:
        saved_data = pickle.load(f)
        model = saved_data['model']
        columns = saved_data['columns']
    print("Model loaded successfully!")
except Exception as e:
    print(f"Error loading model: {e}")
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

def count_connected_line_groups(line_segments, tolerance=0.1):
    """
    Group connected line segments into shapes.
    Lines that share endpoints are considered part of the same shape.
    """
    if not line_segments:
        return 0
    
    # Simple approach: assume every 4-6 connected lines form a shape (rectangle/polygon)
    # For more accuracy, we'd need to trace connections
    
    # Conservative estimate: divide total lines by average lines per shape
    num_lines = len(line_segments)
    
    # Most shapes use 3-6 lines (triangles to hexagons, curved shapes broken into segments)
    avg_lines_per_shape = 5
    
    estimated_shapes = max(1, num_lines // avg_lines_per_shape)
    
    print(f"  {num_lines} line segments grouped into ~{estimated_shapes} shapes")
    
    return estimated_shapes

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
        price_data = [
            ['TOTAL AMOUNT', f"₦{quote.quoted_price:,.2f}"]
        ]
        price_table = Table(price_data, colWidths=[120*mm, 50*mm])
        price_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFF8F0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#E89D3C')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 18),
            ('GRID', (0, 0), (-1, -1), 2, colors.HexColor('#E89D3C')),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(price_table)

    else:
        # Price Section for single-item quotes
        elements.append(Paragraph("Pricing", heading_style))
        
        price_data = [
            ['TOTAL AMOUNT', f"₦{quote.quoted_price:,.2f}"]
        ]
        
        price_table = Table(price_data, colWidths=[120*mm, 50*mm])
        price_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFF8F0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#E89D3C')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 18),
            ('GRID', (0, 0), (-1, -1), 2, colors.HexColor('#E89D3C')),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
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
        file_content = file.read()
        analysis = analyze_dxf_file(file_content)
        return jsonify(analysis)
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        })
    
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
            customer_whatsapp=data.get('customer_whatsapp', ''),
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
            'quote_id': quote.id,
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