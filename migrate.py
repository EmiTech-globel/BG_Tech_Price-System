from app import app, db
from sqlalchemy import text

def run_migration():
    """Add discount tracking fields to Quote table"""
    
    with app.app_context():
        print("Starting Phase 2 (Discount System) migration...")
        
        try:
            # Check if columns already exist
            inspector = db.inspect(db.engine)
            quote_columns = [col['name'] for col in inspector.get_columns('quote')]
            
            migrations = []
            
            # 1. Add discount_applied field
            if 'discount_applied' not in quote_columns:
                print("Adding discount_applied to Quote table...")
                db.session.execute(text(
                    "ALTER TABLE quote ADD COLUMN discount_applied BOOLEAN DEFAULT FALSE"
                ))
                migrations.append('discount_applied')
            else:
                print("⚠️ discount_applied already exists, skipping")
            
            # 2. Add discount_percentage field
            if 'discount_percentage' not in quote_columns:
                print("Adding discount_percentage to Quote table...")
                db.session.execute(text(
                    "ALTER TABLE quote ADD COLUMN discount_percentage FLOAT DEFAULT 0"
                ))
                migrations.append('discount_percentage')
            else:
                print("⚠️ discount_percentage already exists, skipping")
            
            # 3. Add discount_amount field
            if 'discount_amount' not in quote_columns:
                print("Adding discount_amount to Quote table...")
                db.session.execute(text(
                    "ALTER TABLE quote ADD COLUMN discount_amount FLOAT DEFAULT 0"
                ))
                migrations.append('discount_amount')
            else:
                print("⚠️ discount_amount already exists, skipping")
            
            # 4. Add original_price field
            if 'original_price' not in quote_columns:
                print("Adding original_price to Quote table...")
                db.session.execute(text(
                    "ALTER TABLE quote ADD COLUMN original_price FLOAT"
                ))
                migrations.append('original_price')
            else:
                print("⚠️ original_price already exists, skipping")
            
            # Commit all changes
            db.session.commit()
            
            print("\n" + "="*50)
            print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
            print("="*50)
            
            if migrations:
                print("\nNew columns added to Quote table:")
                for col in migrations:
                    print(f"  • {col}")
            else:
                print("\nAll columns already exist. No changes made.")
            
            print("\nDiscount system database ready!")
            
        except Exception as e:
            db.session.rollback()
            print("\n" + "="*50)
            print("❌ MIGRATION FAILED!")
            print("="*50)
            print(f"Error: {e}")
            import traceback
            print(traceback.format_exc())

if __name__ == "__main__":
    run_migration()