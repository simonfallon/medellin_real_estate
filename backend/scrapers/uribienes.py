import asyncio
import re
from typing import List, Tuple
from playwright.async_api import Page, BrowserContext

from .base import BaseScraper
from .types import Property

# Constants for Uribienes
URIBIENES_BASE_URL = "https://uribienes.com"

# Search URL template
# Example: https://uribienes.com/inmuebles/arriendo?city=5266&type=1&pcmin=2500000&pcmax=3500000&neighborhood=Jardines+&minarea=50&maxarea=100
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
    def __init__(self):
        super().__init__(name="Uribienes", concurrency=3)

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

    async def process_search_inputs(
        self, context: BrowserContext, inputs: List[Tuple[str, str]]
    ) -> List[Tuple[str, str]]:
        all_links = []
        sem = asyncio.Semaphore(5)

        async def process_single_search(url, barrio_name):
            async with sem:
                page = await context.new_page()
                try:
                    links = await self._extract_links_from_search_page(page, url)
                    return [(link, barrio_name) for link in links]
                except Exception as e:
                    print(f"[{self.name}] Error searching {barrio_name}: {e}")
                    return []
                finally:
                    await page.close()

        tasks = [process_single_search(url, barrio) for url, barrio in inputs]
        results = await asyncio.gather(*tasks)

        seen = set()
        for r_list in results:
            for link, barrio in r_list:
                if link not in seen:
                    all_links.append((link, barrio))
                    seen.add(link)

        return all_links

    async def _extract_links_from_search_page(
        self, page: Page, search_url: str
    ) -> List[str]:
        await page.goto(search_url)

        # Wait for page to be fully loaded
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except:
            pass

        # Wait for property cards to load (they load dynamically)
        try:
            await page.wait_for_selector('a[href^="/inmuebles/"]', timeout=5000)
            # Give extra time for all content to render
            await page.wait_for_timeout(2000)
        except:
            # No results found
            return []

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
        await page.goto(link)
        await page.wait_for_load_state("domcontentloaded")

        # Wait for main content to load
        try:
            await page.wait_for_selector("h1", timeout=10000)
        except:
            pass

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

        # Extract property details using full-page text (more reliable than JS selectors)
        # This approach is used by other scrapers like escala_inmobiliaria
        try:
            full_text = await page.locator("body").inner_text()

            # Extract bedrooms - look for "X Habitaciones" or "X Ha."
            bedrooms_match = re.search(
                r"(\d+)\s*(?:Habitaciones|Ha\.)", full_text, re.IGNORECASE
            )
            if bedrooms_match:
                bedrooms = bedrooms_match.group(1)

            # Extract bathrooms - look for "X Baños" or "X Ba."
            # Use findall and take the first occurrence from the shortest match
            bathrooms_matches = re.findall(
                r"(\d+)\s*(?:Baños|Ba\.)", full_text, re.IGNORECASE
            )
            if bathrooms_matches:
                bathrooms = bathrooms_matches[
                    0
                ]  # Take first match which should be main property

            # Extract parking - look for "X Parqueadero" or variations
            parking_match = re.search(
                r"(\d+)\s*(?:Parqueadero|Garaje)", full_text, re.IGNORECASE
            )
            if parking_match:
                parking = parking_match.group(1)

            # Extract area - look for "X m²" or "X m2"
            area_match = re.search(r"(\d+)\s*(?:m²|m2)", full_text, re.IGNORECASE)
            if area_match:
                area = area_match.group(1)

            # Extract estrato
            estrato_match = re.search(r"Estrato\s*:?\s*(\d+)", full_text, re.IGNORECASE)
            if estrato_match:
                estrato = estrato_match.group(1)

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
            # If regex extraction fails, keep defaults
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
            # Look for description section
            desc_el = page.locator(".text-neutral-600.text-base").first
            if await desc_el.count() > 0:
                description = await desc_el.inner_text()
            else:
                # Fallback: find long paragraph
                paragraphs = await page.locator("p").all()
                for p in paragraphs:
                    text = await p.inner_text()
                    if len(text) > 50:
                        description = text
                        break
        except:
            pass

        # Images - extract from #detail-images container
        try:
            # Wait for images to load
            await page.wait_for_selector("#detail-images img", timeout=5000)

            img_elements = await page.locator("#detail-images img").all()
            for img in img_elements:
                src = await img.get_attribute("src")
                if src:
                    # Filter out logos and non-property images
                    src_lower = src.lower()
                    if (
                        "logo" not in src_lower
                        and "icon" not in src_lower
                        and "whatsapp" not in src_lower
                        and "facebook" not in src_lower
                    ):
                        # Ensure it's from the CDN
                        if "pictures.domus.la" in src or src.startswith("http"):
                            if src not in images:
                                images.append(src)
        except:
            pass

        if images:
            image_url = images[0]

        # Extract GPS coordinates from Mapbox link
        latitude, longitude = None, None
        try:
            # Look for Mapbox feedback link which contains coordinates
            # Pattern: https://apps.mapbox.com/feedback/...#/-75.58847/6.17802/15
            page_content = await page.content()
            mapbox_match = re.search(
                r"apps\.mapbox\.com/feedback/[^#]+#/(-?\d+\.\d+)/(-?\d+\.\d+)",
                page_content,
            )
            if mapbox_match:
                longitude = float(mapbox_match.group(1))
                latitude = float(mapbox_match.group(2))
        except Exception:
            # GPS extraction failed
            pass

        # If Mapbox link didn't work, try JavaScript window variables
        if not latitude or not longitude:
            try:
                coords = await page.evaluate(
                    """() => {
                    // Check for common coordinate variable names
                    if (window.latitude && window.longitude) {
                        return { lat: window.latitude, lon: window.longitude };
                    }
                    if (window.lat && window.lng) {
                        return { lat: window.lat, lon: window.lng };
                    }
                    return null;
                }"""
                )
                if coords and coords.get("lat") and coords.get("lon"):
                    latitude = float(coords["lat"])
                    longitude = float(coords["lon"])
            except:
                pass

        data = {
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

        return data
