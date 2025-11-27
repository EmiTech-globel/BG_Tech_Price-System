import sqlite3
import os

db_path = os.path.join('instance', 'quotes.db')

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if customer_whatsapp column exists
    cursor.execute("PRAGMA table_info(quote)")
    columns = cursor.fetchall()
    col_names = [col[1] for col in columns]
    
    print("Current columns in quote table:")
    for col in col_names:
        print(f"  - {col}")
    
    # Check if customer_whatsapp exists
    if 'customer_whatsapp' in col_names:
        print("\n✓ customer_whatsapp column already exists")
    else:
        print("\n✗ customer_whatsapp column is MISSING - adding it now...")
        cursor.execute("ALTER TABLE quote ADD COLUMN customer_whatsapp VARCHAR(20)")
        conn.commit()
        print("✓ Column added successfully!")
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
