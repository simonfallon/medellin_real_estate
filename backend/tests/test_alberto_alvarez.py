import unittest
import sys
import os
import asyncio
from playwright.async_api import async_playwright

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.scrapers import alberto_alvarez
from backend.tests.test_utils import validate_property

class TestAlbertoAlvarez(unittest.IsolatedAsyncioTestCase):
    
    async def test_single_property(self):
        """
        Test scraping a single property page.
        """
        url = "https://albertoalvarez.com/inmuebles/detalle/arrendamientos/apartamento/AA-88708/envigado-envigado/"
        print(f"\nTesting single property scrape: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            scraper = alberto_alvarez.AlbertoAlvarezScraper()
            # scrape_detail_page equivalent is extract_property_details
            result = await scraper.extract_property_details(page, url, "TestBarrio")
            
            await browser.close()
            
            validate_property(self, result, expected_source="alberto_alvarez")
            print("Successfully scraped and validated single property data.")


    async def test_search_results(self):
        """
        Test scraping a search results page and validating details.
        """
        url = "https://albertoalvarez.com/inmuebles/arrendamientos/apartamento/envigado/envigado/?o=&rentFrom=2000000&rentTo=3500000&builtAreaFrom=4&builtAreaTo=1100&roomsFrom=1&roomsTo=2"
        print(f"\nTesting search results scrape: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            scraper = alberto_alvarez.AlbertoAlvarezScraper()
            
            # get_search_results_links(page, url)
            links = await scraper._get_search_results_links(page, url)
            
            print(f"Found {len(links)} property links. Validating a subset to avoid timeout...")
            self.assertTrue(len(links) > 0)
            
            # Validate max 3 properties to keep test fast
            links_to_check = links[:3]
            
            for link in links_to_check:
                print(f"Scraping and validating: {link}")
                # We need a new page or context for each if we want to be safe, or just reuse
                # scrape_detail_page uses the passed page.
                # In scraping logic we usually close pages.
                detail_page = await browser.new_page()
                try:
                    result = await scraper.extract_property_details(detail_page, link, "SearchTestBarrio")
                    validate_property(self, result, expected_source="alberto_alvarez")
                finally:
                    await detail_page.close()
            
            await browser.close()

if __name__ == "__main__":
    unittest.main()
