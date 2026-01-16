import unittest
import sys
import os
import asyncio
from playwright.async_api import async_playwright

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.scrapers import proteger
from backend.tests.test_utils import validate_property

class TestProteger(unittest.IsolatedAsyncioTestCase):
    
    async def test_single_property(self):
        url = "https://inmobiliariaproteger.com/apartamento-alquiler-la-magnolia-envigado/9420502"
        print(f"\nTesting single property scrape: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            scraper = proteger.ProtegerScraper()
            result = await scraper.extract_property_details(page, url, "La Magnolia")
            
            await browser.close()
            
            print(f"Result: {result}")
            validate_property(self, result, expected_source="proteger")
            
            # Specific assertions based on known data (if available)
            self.assertEqual(result['code'], '9420502')
            self.assertEqual(result['bedrooms'], '3')
            self.assertTrue('m' in result['area']) # Area should be captured (e.g. 68 m²)

    async def test_search_results(self):
        # Using La Magnolia (377213) as it has properties
        url = "https://inmobiliariaproteger.com/s?id_country=1&id_region=2&id_city=291&id_zone=377213&business_type%5B%5D=for_rent&min_price=2.500.000&max_price=4.500.000"
        print(f"\nTesting search results scrape: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            scraper = proteger.ProtegerScraper()
            links = await scraper._extract_links_from_search_page(page, url)
            
            print(f"Found {len(links)} links")
            self.assertTrue(len(links) > 0)
            
            await browser.close()

if __name__ == "__main__":
    unittest.main()
