import asyncio
import sys
import os

# Add the current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend import database, scraper

async def main():
    database.init_db()
    db = next(database.get_db())
    
    print("Running consolidated scraper...")
    result = await scraper.scrape_and_save_all(db)
    
    print(f"Finished. Saved/Updated {result['total_processed']} properties. {result['new_properties']} were brand new.")

if __name__ == "__main__":
    asyncio.run(main())
