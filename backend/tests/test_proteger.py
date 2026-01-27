import unittest
import sys
import os
from playwright.async_api import async_playwright

# Add backend to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from backend.scrapers import proteger
from backend.tests.test_utils import validate_property


class TestProteger(unittest.IsolatedAsyncioTestCase):
    async def test_single_property(self):
        # This property has a swiper gallery with many images
        url = "https://inmobiliariaproteger.com/apartamento-alquiler-el-portal-envigado/9666971"
        print(f"\nTesting single property scrape: {url}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            scraper = proteger.ProtegerScraper()
            result = await scraper.extract_property_details(page, url, "El Portal")

            await browser.close()

            print(f"Result: {result}")
            validate_property(self, result, expected_source="proteger")

            # Specific assertions
            self.assertEqual(result["code"], "9666971")
            self.assertEqual(result["bedrooms"], "3")
            self.assertTrue("3.600.000" in result["price"])

            # GPS Validation
            self.assertIsNotNone(result.get("latitude"), "Latitude should be extracted")
            self.assertIsNotNone(
                result.get("longitude"), "Longitude should be extracted"
            )
            self.assertIsInstance(result["latitude"], float)
            self.assertIsInstance(result["longitude"], float)

            # Stricter Image Validation
            self.assertIsInstance(result["images"], list)
            # We know there are exactly 18 images in this gallery.
            # Let's ensure we get at least most of them.
            self.assertTrue(
                len(result["images"]) >= 5,
                f"Should capture most images (found {len(result['images'])})",
            )

            # Validate ALL images
            for img in result["images"]:
                self.assertTrue(img.startswith("http"), f"Invalid image URL: {img}")
                self.assertTrue(
                    "wasi.co" in img, f"Image should be from wasi.co: {img}"
                )

            # Ensure no duplicates
            self.assertEqual(
                len(result["images"]),
                len(set(result["images"])),
                "All captured images should be unique",
            )

            self.assertEqual(
                result["image_url"],
                result["images"][0],
                "Main image_url should match first image",
            )

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
