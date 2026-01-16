from .scrapers.arrendamientos_envigado import ArrendamientosEnvigadoScraper
from .scrapers.alberto_alvarez import AlbertoAlvarezScraper
from . import storage
import asyncio

# Scrapers for specific sites
async def scrape_arrendamientos_envigado_batch():
    scraper = ArrendamientosEnvigadoScraper()
    return await scraper.scrape()

async def scrape_alberto_alvarez_batch():
    scraper = AlbertoAlvarezScraper()
    return await scraper.scrape()

async def scrape_all_batch():
    # Run both scrapers concurrently
    envigado_scraper = ArrendamientosEnvigadoScraper()
    alberto_scraper = AlbertoAlvarezScraper()
    
    envigado_results, alberto_results = await asyncio.gather(
        envigado_scraper.scrape(),
        alberto_scraper.scrape()
    )
    return envigado_results + alberto_results

async def scrape_and_save_all(db):
    """
    Orchestrates the scraping of all sources and saves to DB.
    """
    print("Starting concurrent scrape...")
    all_properties = await scrape_all_batch()
    print(f"Scraped total: {len(all_properties)}")
    
    # Filter loose price as requested in original script (keep it consistent)
    # Or should we? The user asked to reduce duplication.
    # The original script had it. Let's keep it but make it optional or just part of the flow.
    # storage.parse_price is available.
    
    return storage.save_properties(db, all_properties)


