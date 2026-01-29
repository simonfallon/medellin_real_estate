import re
from typing import List, Tuple
from playwright.async_api import Page

from .base import BaseScraper, ScraperConfig
from .types import Property

# Constants for Uribienes
URIBIENES_BASE_URL = "https://uribienes.com"

# Search URL template
SEARCH_URL_TEMPLATE = (
    "https://uribienes.com/inmuebles/arriendo?"
    "city=5266&type=1&"
    "pcmin={min_price}&pcmax={max_price}&"
    "neighborhood={neighborhood}&"
    "minarea=50&maxarea=100"
)

# Barrio mappings - neighborhood names with + separator and trailing +
BARRIOS = {
    "El Portal": "El+Portal+",
    "Jardines": "Jardines+",
    "La Abadia": "La+Abadia+",
    "La Frontera": "La+Frontera+",
    "La Magnolia": "La+Magnolia+",
    "Las Flores": "Las+Flores+",
    "Las Vegas": "Las+Vegas+",
    "Loma Benedictinos": "Loma+Benedictinos+",
    "Otra Parte": "Otra+Parte+",
    "Pontevedra": "Pontevedra+",
    "San Marcos": "San+Marcos+",
    "Villagrande": "Villagrande+",
    "Zuñiga": "Zuñiga+",
}

# Unified Name Mapping - map to standardized display names
UNIFIED_BARRIOS = {
    "El Portal": "El Portal",
    "Jardines": "Jardines",
    "La Abadia": "La Abadia",
    "La Frontera": "La Frontera",
    "La Magnolia": "La Magnolia",
    "Las Flores": "Las Flores",
    "Las Vegas": "Las Vegas",
    "Loma Benedictinos": "Loma Benedictinos",
    "Otra Parte": "Otra Parte",
    "Pontevedra": "Pontevedra",
    "San Marcos": "San Marcos",
    "Villagrande": "Villagrande",
    "Zuñiga": "Zuñiga",
}


class UribienesScraper(BaseScraper):
    def __init__(self, config: ScraperConfig = None):
        default_config = ScraperConfig(
            detail_concurrency=3,
            search_concurrency=5,
        )

        # Override price_ranges if custom config provided
        if config is not None:
            default_config.price_ranges = config.price_ranges

        super().__init__(name="Uribienes", config=default_config)

    async def get_search_inputs(self) -> List[Tuple[str, str]]:
        inputs = []
        for barrio_name, neighborhood_param in BARRIOS.items():
            for price_range in self.PRICE_RANGES:
                url = SEARCH_URL_TEMPLATE.format(
                    min_price=price_range["min"],
                    max_price=price_range["max"],
                    neighborhood=neighborhood_param,
                )

                unified_name = UNIFIED_BARRIOS.get(barrio_name, barrio_name)
                inputs.append((url, unified_name))
        return inputs

    # process_search_inputs() is inherited from BaseScraper

    async def _extract_links_from_search_page(
        self, page: Page, search_url: str
    ) -> List[str]:
        # Navigate and wait for property links (removed hardcoded 2s delay)
        await self.navigate_and_wait(
            page,
            search_url,
            wait_for_selector='a[href^="/inmuebles/"]',
        )

        # Extract all property links using JavaScript for better reliability
        try:
            links = await page.evaluate(
                r"""() => {
                    const anchors = Array.from(document.querySelectorAll('a[href^="/inmuebles/"]'));
                    const propertyLinks = [];

                    for (const a of anchors) {
                        const href = a.getAttribute('href');
                        // Only include links with numeric IDs: /inmuebles/215327
                        if (href && /\/inmuebles\/\d+$/.test(href)) {
                            propertyLinks.push(href);
                        }
                    }

                    // Return unique links
                    return [...new Set(propertyLinks)];
                }"""
            )

            # Convert relative URLs to absolute
            full_links = [URIBIENES_BASE_URL + link for link in links]
            return full_links
        except Exception as e:
            print(f"[{self.name}] Error extracting links with JS: {e}")
            return []

    async def extract_property_details(
        self, page: Page, link: str, barrio_name: str
    ) -> Property:
        await self.navigate_and_wait(page, link, wait_for_selector="h1")

        # Defaults
        title = ""
        price = ""
        area = ""
        bedrooms = ""
        bathrooms = ""
        parking = ""
        estrato = ""
        description = ""
        image_url = ""
        images = []
        code = ""

        # Title
        try:
            title_el = page.locator("h1").first
            if await title_el.count() > 0:
                title = await title_el.inner_text()
        except:
            pass

        # Price - look for $ symbol in bold text
        try:
            price_el = page.locator("span.font-bold, div.font-bold").first
            if await price_el.count() > 0:
                price_text = await price_el.inner_text()
                if "$" in price_text:
                    price = price_text.strip()

            # Fallback: search all elements for price
            if not price:
                all_text = await page.locator("span, div").all()
                for el in all_text:
                    text = await el.inner_text()
                    if "$" in text and any(c.isdigit() for c in text):
                        if len(text) < 50:  # Avoid long descriptions
                            price = text.strip()
                            break
        except:
            pass

        # Extract property details using full-page text
        try:
            full_text = await page.locator("body").inner_text()

            # Use base class feature extraction for common patterns
            features = self.extract_features_from_text(full_text)
            if features["bedrooms"]:
                bedrooms = features["bedrooms"]
            if features["bathrooms"]:
                bathrooms = features["bathrooms"]
            if features["parking"]:
                parking = features["parking"]
            if features["area"]:
                area = features["area"]
            if features["estrato"]:
                estrato = features["estrato"]

            # Extract code if not already found
            if not code:
                code_match = re.search(
                    r"Código\s+(?:del\s+)?inmueble\s*:?\s*(\d+)",
                    full_text,
                    re.IGNORECASE,
                )
                if code_match:
                    code = code_match.group(1)
        except Exception:
            pass

        # Property code - extract from URL if not found
        if not code:
            try:
                match = re.search(r"/inmuebles/(\d+)", link)
                if match:
                    code = match.group(1)
            except:
                pass

        # Description
        try:
            desc_el = page.locator(".text-neutral-600.text-base").first
            if await desc_el.count() > 0:
                description = await desc_el.inner_text()
            else:
                paragraphs = await page.locator("p").all()
                for p in paragraphs:
                    text = await p.inner_text()
                    if len(text) > 50:
                        description = text
                        break
        except:
            pass

        # Images - extract from #detail-images container using filter utility
        try:
            await page.wait_for_selector("#detail-images img", timeout=5000)

            raw_images = []
            img_elements = await page.locator("#detail-images img").all()
            for img in img_elements:
                src = await img.get_attribute("src")
                if src:
                    raw_images.append(src)

            images = self.filter_property_images(raw_images)
        except:
            pass

        if images:
            image_url = images[0]

        # Extract GPS coordinates using base utilities
        latitude, longitude = await self.extract_gps_from_mapbox(page)
        if latitude is None:
            latitude, longitude = await self.extract_gps_from_window_var(page)

        return {
            "code": code,
            "title": title or "Apartamento en Arriendo",
            "location": barrio_name,
            "price": price,
            "area": area,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "parking": parking,
            "estrato": estrato,
            "image_url": image_url,
            "images": images,
            "link": link,
            "source": "uribienes",
            "description": description,
            "latitude": latitude,
            "longitude": longitude,
        }
