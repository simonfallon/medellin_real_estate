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
            
            scraper = arrendamientos_envigado.ArrendamientosEnvigadoScraper()
            # scrape_page_details equivalent is extract_property_details
            result = await scraper.extract_property_details(page, url, "TestBarrio")
            
            await browser.close()
            
            validate_property(self, result, expected_source="arrendamientos_envigado")

            # Stricter Image Validation
            self.assertIsInstance(result['images'], list)
            self.assertTrue(len(result['images']) > 1, "Should capture images")
            
            # Verify image URLs
            for img in result['images']:
                self.assertTrue(img.startswith('http'), f"Invalid image URL: {img}")
                
            # Ensure no duplicates
            self.assertEqual(len(result['images']), len(set(result['images'])), "All captured images should be unique")
            
            # Check main image matches
            if result['images']:
                 self.assertEqual(result['image_url'], result['images'][0], "Main image_url should match first image")

            print("Successfully scraped and validated single property data.")

    async def test_search_results(self):
        """
        Test scraping a search results page.
        """
        url = "https://www.arrendamientosenvigadosa.com.co/busqueda.html?servicio=Arriendo&tipo=1&ciudad=25999&barrio=1113771&valmin=2000000&valmax=3000000"
        print(f"\nTesting search results scrape: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            scraper = arrendamientos_envigado.ArrendamientosEnvigadoScraper()
            
            # Mimic the old process_search_page logic using class methods
            # 1. Get links
            links = await scraper._extract_links_from_search_page(page, url)
            
            # 2. Process links (mocking the loop from the facade)
            results = []
            for link in links:
                try:
                    detail_page = await context.new_page()
                    prop = await scraper.extract_property_details(detail_page, link, "TestSearch")
                    if prop:
                        results.append(prop)
                    await detail_page.close()
                except Exception as e:
                    print(f"Error scraping {link}: {e}")
            
            await browser.close()
            
            # Assertion logic remains the same
            self.assertIsInstance(results, list)
            if len(results) == 0:
                print("Warning: No results found on search page. This might be due to market changes.")
            else:
                print(f"Found {len(results)} properties. Validating all...")
                self.assertTrue(len(results) > 0)
                for result in results:
                     validate_property(self, result, expected_source="arrendamientos_envigado")

if __name__ == "__main__":
    unittest.main()
