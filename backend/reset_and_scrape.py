import asyncio
import database
import json
from datetime import datetime
from scrapers import alberto_alvarez, arrendamientos_envigado

async def save_results(data, db):
    count = 0
    # Deduplicate input data ensures we don't try to insert the same link twice in this batch
    unique_data = {item['link']: item for item in data}.values()
    
    # Get model columns
    model_columns = {c.name for c in database.Property.__table__.columns}
    
    for item in unique_data:
        # Check duplicates
        existing = db.query(database.Property).filter(database.Property.link == item['link']).first()
        if not existing:
            # Map fields
            db_item = item.copy()
            # Handle list of images if present
            if "images" in db_item:
                images_list = db_item["images"]
                if images_list and len(images_list) > 0:
                    db_item["image_url"] = images_list[0]
                    db_item["images"] = json.dumps(images_list)
                else:
                    db_item["images"] = "[]"
            
            
            # Filter only keys that exist in model
            filtered_item = {k: v for k, v in db_item.items() if k in model_columns}
            
            prop = database.Property(**filtered_item)
            db.add(prop)
            count += 1
        else:
            # Update existing record
            existing.location = item.get('location', existing.location)
            existing.title = item.get('title', existing.title)
            existing.image_url = item.get('image_url', existing.image_url)
            existing.code = item.get('code', existing.code)
            existing.price = item.get('price', existing.price)
            existing.area = item.get('area', existing.area)
            existing.bedrooms = item.get('bedrooms', existing.bedrooms)
            existing.bathrooms = item.get('bathrooms', existing.bathrooms)
            existing.parking = item.get('parking', existing.parking)
            existing.estrato = item.get('estrato', existing.estrato)
            existing.updated_at = datetime.utcnow()
            
    db.commit()
    return {"message": "Batch scraping completed", "new_properties": count, "total_found": len(data)}

async def reset_and_scrape():
    print("Deleting all properties from database...")
    # Drop all tables to ensure schema update
    database.Base.metadata.drop_all(bind=database.engine)
    # Initialize DB (create tables)
    database.init_db()
    db = next(database.get_db())
    
    try:
        # Delete all properties
        db.query(database.Property).delete()
        db.commit()
        print("Database cleared.")
        
        print(f"Starting scrape at {datetime.now()}...")
        
        # Run both scrapers concurrently
        envigado_results, alberto_results = await asyncio.gather(
            arrendamientos_envigado.scrape(),
            alberto_alvarez.scrape()
        )
        
        print(f"Got {len(envigado_results)} items from Arrendamientos Envigado")
        print(f"Got {len(alberto_results)} items from Alberto Alvarez")
        
        all_results = envigado_results + alberto_results
        
        print("Saving to DB...")
        res = await save_results(all_results, db)
        print(res)
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(reset_and_scrape())
