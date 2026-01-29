import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from backend.scrapers.livinmobiliaria import LivinmobiliariaScraper
from backend.scrapers.types import Property

class TestLivinmobiliariaScraper(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.scraper = LivinmobiliariaScraper()
        # Mock base methods to focus on specific scraper logic
        self.scraper.navigate_and_wait = AsyncMock()
        self.scraper.extract_gps_coordinates = AsyncMock(return_value=(None, None))
        
    async def test_search_results(self):
        """Test parsing of search results with URL-based barrio filtering"""
        mock_page = AsyncMock()
        
        # Mock evaluate to return candidate dicts with realistic URLs
        mock_page.evaluate.return_value = [
            {
                "href": "https://www.livinmobiliaria.com/detalle-propiedad/apartamento-enarriendo-en-la-magnolia-20167",
                "text": ""  # Text is not used anymore, we extract from URL
            },
            {
                "href": "https://www.livinmobiliaria.com/detalle-propiedad/apartamento-enarriendo-en-las-antillas-48288",
                "text": ""  # Should be filtered out (not in target barrios)
            },
            {
                "href": "https://www.livinmobiliaria.com/detalle-propiedad/apartamento-enarriendo-en-otra-parte-48389",
                "text": ""  # Should match "Otra Parte"
            }
        ]
        
        links = await self.scraper._extract_links_from_search_page(mock_page, "http://mock-search")
        
        # Should contain La Magnolia and Otra Parte, but not Las Antillas
        self.assertEqual(len(links), 2)
        self.assertIn("https://www.livinmobiliaria.com/detalle-propiedad/apartamento-enarriendo-en-la-magnolia-20167", links)
        self.assertIn("https://www.livinmobiliaria.com/detalle-propiedad/apartamento-enarriendo-en-otra-parte-48389", links)

    async def test_single_property_features(self):
        """Test extraction of property details"""
        mock_page = AsyncMock()
        mock_page.locator = MagicMock()
        
        # Helper to dispatch locators based on selector
        def side_effect(selector):
            mock = MagicMock()
            if selector == "h1":
                # Title
                mock.first.count = AsyncMock(return_value=1)
                mock.first.inner_text = AsyncMock(return_value="Apartamento en Arriendo La Magnolia")
            elif selector == "body":
                # Body text
                mock.inner_text = AsyncMock(return_value="""
                Precio: $ 2.300.000
                Area: 87m2
                3 Alcobas
                2 Baños
                1 Parqueaderos
                Estrato: 4
                Código: 20167
                """)
            elif ".gallery img" in selector or ".carousel img" in selector:
                # Images
                img = AsyncMock()
                img.get_attribute.return_value = "http://img.com/1.jpg"
                mock.all = AsyncMock(return_value=[img])
            else:
                # Default empty/not found
                mock.first.count = AsyncMock(return_value=0)
                mock.all = AsyncMock(return_value=[])
                mock.inner_text = AsyncMock(return_value="")
            return mock
            
        mock_page.locator.side_effect = side_effect

        link = "https://www.livinmobiliaria.com/detalle-propiedad/apartamento-enarriendo-en-la-magnolia-20167"
        result = await self.scraper.extract_property_details(mock_page, link, "Envigado")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "livinmobiliaria")
        self.assertEqual(result["location"], "La Magnolia")
        self.assertEqual(result["bedrooms"], "3")
        self.assertEqual(result["bathrooms"], "2")
        self.assertEqual(result["code"], "LIV-20167")
        self.assertIn("2.300.000", result["price"])

    async def test_single_property_unmatched_barrio(self):
        """Test that properties without a matching barrio are ignored (return None)"""
        mock_page = AsyncMock()
        mock_page.locator = MagicMock()
        
        # Mock title and body with a non-target barrio
        def side_effect(selector):
            mock = MagicMock()
            if selector == "h1":
                mock.first.count = AsyncMock(return_value=1)
                mock.first.inner_text = AsyncMock(return_value="Apartamento en Arriendo - Las Antillas")
            elif selector == "body":
                mock.inner_text = AsyncMock(return_value="Ubicado en Las Antillas, Envigado")
            # Default empty
            mock.first.count = AsyncMock(return_value=0)
            mock.all = AsyncMock(return_value=[])
            return mock
            
        mock_page.locator.side_effect = side_effect

        link = "https://www.livinmobiliaria.com/detalle-propiedad/apartamento-las-antillas-48288"
        result = await self.scraper.extract_property_details(mock_page, link, "Envigado")
        
        self.assertIsNone(result, "Should return None for properties in barrios not in UNIFIED_BARRIOS")
