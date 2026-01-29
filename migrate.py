from app import app, db
from sqlalchemy import text

def run_migration():
    """Add color and price_per_sheet columns to existing tables"""
    
    with app.app_context():
        print("Starting Phase 1 migration...")
        
        try:
            # Check if columns already exist (prevent duplicate migration)
            inspector = db.inspect(db.engine)
            
            # 1. Add price_per_sheet to Inventory table
            inventory_columns = [col['name'] for col in inspector.get_columns('inventory')]
            
            if 'price_per_sheet' not in inventory_columns:
                print("Adding price_per_sheet to Inventory table...")
                db.session.execute(text(
                    "ALTER TABLE inventory ADD COLUMN price_per_sheet FLOAT DEFAULT 0"
                ))
                print("✅ price_per_sheet column added")
            else:
                print("⚠️ price_per_sheet already exists, skipping")
            
            # 2. Add material_color to Quote table
            quote_columns = [col['name'] for col in inspector.get_columns('quote')]
            
            if 'material_color' not in quote_columns:
                print("Adding material_color to Quote table...")
                db.session.execute(text(
                    "ALTER TABLE quote ADD COLUMN material_color VARCHAR(50)"
                ))
                print("✅ material_color column added to Quote")
            else:
                print("⚠️ material_color already exists in Quote, skipping")
            
            # 3. Add material_color to QuoteItem table
            quote_item_columns = [col['name'] for col in inspector.get_columns('quote_item')]
            
            if 'material_color' not in quote_item_columns:
                print("Adding material_color to QuoteItem table...")
                db.session.execute(text(
                    "ALTER TABLE quote_item ADD COLUMN material_color VARCHAR(50)"
                ))
                print("✅ material_color column added to QuoteItem")
            else:
                print("⚠️ material_color already exists in QuoteItem, skipping")
            
            # 4. Update existing inventory records (set default price_per_sheet if NULL)
            print("Updating existing inventory records...")
            db.session.execute(text(
                """
                UPDATE inventory 
                SET price_per_sheet = CASE 
                    WHEN price_per_sq_ft > 0 THEN (sheet_width_mm * sheet_height_mm / 92903.0) * price_per_sq_ft
                    ELSE 0 
                END
                WHERE price_per_sheet IS NULL OR price_per_sheet = 0
                """
            ))
            
            # Commit all changes
            db.session.commit()
            
            print("\n" + "="*50)
            print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
            print("="*50)
            print("\nNew columns added:")
            print("  • inventory.price_per_sheet")
            print("  • quote.material_color")
            print("  • quote_item.material_color")
            print("\nYou can now proceed with the code updates!")
            
        except Exception as e:
            db.session.rollback()
            print("\n" + "="*50)
            print("❌ MIGRATION FAILED!")
            print("="*50)
            print(f"Error: {e}")
            print("\nPlease check the error and try again.")
            import traceback
            print(traceback.format_exc())

if __name__ == "__main__":
    run_migration()