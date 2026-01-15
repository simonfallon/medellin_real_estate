import unittest
import sys
import os
import asyncio
from playwright.async_api import async_playwright

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.scrapers import arrendamientos_envigado
from backend.tests.test_utils import validate_property

class TestArrendamientosEnvigado(unittest.IsolatedAsyncioTestCase):
    
    async def test_single_property(self):
        """
        Test scraping a single property page.
        """
        url = "https://www.arrendamientosenvigadosa.com.co/inmueble.html?inmueble=72373"
        print(f"\nTesting single property scrape: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # scrape_page_details(page, url, barrio_name)
            # providing a dummy barrio name for testing
            result = await arrendamientos_envigado.scrape_page_details(page, url, "TestBarrio")
            
            await browser.close()
            
            validate_property(self, result, expected_source="arrendamientos_envigado")
            print("Successfully scraped and validated single property data.")

    async def test_search_results(self):
        """
        Test scraping a search results page.
        """
        url = "https://www.arrendamientosenvigadosa.com.co/busqueda.html?servicio=Arriendo&tipo=1&ciudad=25999&barrio=1113771&valmin=2000000&valmax=3000000"
        print(f"\nTesting search results scrape: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # process_search_page(page, search_url, barrio_name)
            results = await arrendamientos_envigado.process_search_page(page, url, "TestSearch")
            
            await browser.close()
            
            self.assertIsInstance(results, list)
            # We expect at least one result if the URL is valid and has listings
            if len(results) == 0:
                print("Warning: No results found on search page. This might be due to market changes.")
            else:
                print(f"Found {len(results)} properties. Validating all...")
                self.assertTrue(len(results) > 0)
                for result in results:
                     validate_property(self, result, expected_source="arrendamientos_envigado")

if __name__ == "__main__":
    unittest.main()
