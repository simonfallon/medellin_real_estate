import unittest
import asyncio
from backend.scrapers.escala_inmobiliaria import EscalaInmobiliariaScraper


class TestEscalaInmobiliariaScraper(unittest.TestCase):
    def setUp(self):
        self.scraper = EscalaInmobiliariaScraper()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_search_results(self):
        """
        Verifies that the scraper can find links on a search page.
        """

        async def run_test():
            inputs = await self.scraper.get_search_inputs()
            self.assertTrue(len(inputs) > 0, "Should return at least one search input")

            # Use the first input (it's the concatenated one)
            url, meta = inputs[0]
            print(f"Testing search URL: {url}")

            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()

                links = await self.scraper._extract_links_from_search_page(page, url)
                await browser.close()

                print(f"Found {len(links)} links")
                self.assertTrue(len(links) > 0, "Should find property links")
                for link in links:
                    self.assertTrue(
                        link.startswith("http"), f"Link should be absolute: {link}"
                    )
                    self.assertIn("inmueble", link, "Link should check for 'inmueble'")

        self.loop.run_until_complete(run_test())

    def test_single_property(self):
        """
        Verifies strict data extraction from a sample URL.
        """
        # Sample URL from requirements
        url = "https://escalainmobiliaria.com.co/inmueble/apartamento-en-arriendo-las-flores-envigado_1272-1048/"

        async def run_test():
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # We pass 'Unknown' or any barrio, the scraper should ideally extract the correct one
                # or rely on what we pass. But my implementation tries to extract it from URL/Page.
                result = await self.scraper.extract_property_details(
                    page, url, "Unknown"
                )
                await browser.close()

                self.assertIsNotNone(result, "Should return a result object")
                print(f"Scraped Data: {result}")

                # Assertions
                self.assertTrue(result["title"], "Title should not be empty")
                self.assertTrue(result["price"], "Price should not be empty")
                self.assertTrue(result["area"], "Area should not be empty")

                # Code check
                self.assertTrue(result["code"], "Code should be extracted")

                # Location check (Strict)
                # The URL contains 'las-flores', so we expect 'Las Flores'
                self.assertEqual(
                    result["location"],
                    "Las Flores",
                    "Location should be extracted correctly as 'Las Flores'",
                )

                # Image validation
                self.assertIsInstance(result["images"], list)
                self.assertTrue(len(result["images"]) > 0, "Should have images")
                for img in result["images"]:
                    self.assertTrue(
                        img.startswith("http"), "Image URL must be absolute"
                    )
                    self.assertNotIn(
                        "logo", img.lower(), "Images should not contain logos"
                    )

                # Uniqueness
                self.assertEqual(
                    len(result["images"]),
                    len(set(result["images"])),
                    "Images must be unique",
                )

        self.loop.run_until_complete(run_test())


if __name__ == "__main__":
    unittest.main()
