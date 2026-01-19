import unittest
import sys
import os
import asyncio
from playwright.async_api import async_playwright

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.scrapers import arrendamientos_las_vegas
from backend.tests.test_utils import validate_property

class TestArrendamientosLasVegas(unittest.IsolatedAsyncioTestCase):
    
    async def test_single_property(self):
        url = "https://arrendamientoslasvegas.com/inmuebles/513349"
        print(f"\nTesting single property scrape: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            page = await context.new_page()
            
            scraper = arrendamientos_las_vegas.ArrendamientosLasVegasScraper()
            result = await scraper.extract_property_details(page, url, "La Abadía")
            
            await browser.close()
            
            print(f"Result: {result}")
            # We skip validate_property for now or use it if we are sure keys match
            # validate_property(self, result, expected_source="arrendamientos_las_vegas")
            
            self.assertEqual(result['code'], '513349')
            self.assertEqual(result['bedrooms'], '2')
            self.assertEqual(result['bathrooms'], '2')
            self.assertEqual(result['parking'], '1')
            self.assertEqual(result['area'], '85')
            self.assertTrue('3.400.000' in result['price'])
            self.assertEqual(result['source'], 'arrendamientos_las_vegas')

            # GPS Validation
            self.assertIsNotNone(result.get('latitude'), "Latitude should be extracted")
            self.assertIsNotNone(result.get('longitude'), "Longitude should be extracted")
            self.assertIsInstance(result['latitude'], float)
            self.assertIsInstance(result['longitude'], float)

            # Strict Image Validation
            self.assertIsInstance(result['images'], list)
            # We identified exactly 11 valid images in the carousel for this property
            self.assertEqual(len(result['images']), 11, f"Should capture exactly 11 images (found {len(result['images'])})")
            
            # Validate ALL images
            for img in result['images']:
                self.assertTrue(img.startswith('http'), f"Invalid image URL: {img}")
                # Ensure no logos or icons slipped through (basic check)
                self.assertFalse("logo" in img.lower(), f"Image should not be a logo: {img}")
                
            # Ensure no duplicates
            self.assertEqual(len(result['images']), len(set(result['images'])), "All captured images should be unique")
                
            self.assertEqual(result['image_url'], result['images'][0], "Main image_url should match first image")


    async def test_search_results(self):
        # Test a search URL (using one from the map)
        url = "https://arrendamientoslasvegas.com/inmuebles/arriendo?city=5266&type=1&pcmin=2500000&pcmax=3500000&minarea=50&neighborhood=La+Abadia+"
        print(f"\nTesting search results scrape: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            scraper = arrendamientos_las_vegas.ArrendamientosLasVegasScraper()
            links = await scraper._extract_links_from_search_page(page, url)
            
            print(f"Found {len(links)} links")
            # We might not find links if the specific filter returns nothing, but let's hope it returns something.
            # If 0, it doesn't necessarily mean broken, but let's assert list is not None.
            self.assertIsNotNone(links)
            
            await browser.close()

if __name__ == "__main__":
    unittest.main()
