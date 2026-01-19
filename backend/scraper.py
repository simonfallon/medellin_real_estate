from .scrapers.arrendamientos_envigado import ArrendamientosEnvigadoScraper
from .scrapers.alberto_alvarez import AlbertoAlvarezScraper
from .scrapers.proteger import ProtegerScraper
from .scrapers.arrendamientos_las_vegas import ArrendamientosLasVegasScraper
from . import storage
import asyncio


# Scrapers for specific sites
async def scrape_arrendamientos_envigado_batch():
    scraper = ArrendamientosEnvigadoScraper()
    return await scraper.scrape()


async def scrape_alberto_alvarez_batch():
    scraper = AlbertoAlvarezScraper()
    return await scraper.scrape()


async def scrape_proteger_batch():
    scraper = ProtegerScraper()
    return await scraper.scrape()


async def scrape_arrendamientos_las_vegas_batch():
    scraper = ArrendamientosLasVegasScraper()
    return await scraper.scrape()


async def scrape_all_batch():
    # Run all scrapers concurrently
    envigado_scraper = ArrendamientosEnvigadoScraper()
    alberto_scraper = AlbertoAlvarezScraper()
    proteger_scraper = ProtegerScraper()
    las_vegas_scraper = ArrendamientosLasVegasScraper()

    (
        envigado_results,
        alberto_results,
        proteger_results,
        las_vegas_results,
    ) = await asyncio.gather(
        envigado_scraper.scrape(),
        alberto_scraper.scrape(),
        proteger_scraper.scrape(),
        las_vegas_scraper.scrape(),
    )
    return envigado_results + alberto_results + proteger_results + las_vegas_results


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
