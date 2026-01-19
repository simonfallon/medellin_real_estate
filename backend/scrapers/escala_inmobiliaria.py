import asyncio
import re
from typing import List, Tuple, Optional
from playwright.async_api import Page, BrowserContext

from .base import BaseScraper
from .types import Property

# Constants
BASE_URL = "https://escalainmobiliaria.com.co/"
SEARCH_URL_TEMPLATE = "https://escalainmobiliaria.com.co/inmuebles/g/arriendo/t/apartamentos/c/envigado/n/{barrios_slug}/?precioMin={min_price}&precioMax={max_price}"

# Mapped from arrendamientos_envigado.py
# Normalized keys to standardized display names if needed, or just used for slug generation
BARRIOS_LIST = [
    "El Portal",
    "Jardines",
    "La Abadia",
    "La Frontera",
    "La Magnolia",
    "Las Flores",
    "Las Vegas",
    "Loma Benedictinos",
    "Pontevedra",
    "San Marcos",
    "Villagrande",
    "Zuñiga",
]


class EscalaInmobiliariaScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="Escala Inmobiliaria", concurrency=3)

    async def get_search_inputs(self) -> List[Tuple[str, str]]:
        """
        Generates the single concatenated search URL.
        Returns a list with one item: (url, "Mixed")
        The specific barrio for each property will be extracted later.
        """
        # Create slug: replace spaces with _, join with -o-
        # User example suggests lowercase: las_vegas-o-las_flores
        slugs = [b.lower().replace(" ", "_") for b in BARRIOS_LIST]
        barrios_slug = "-o-".join(slugs)

        inputs = []
        for price_range in self.PRICE_RANGES:
            url = SEARCH_URL_TEMPLATE.format(
                barrios_slug=barrios_slug,
                min_price=price_range["min"],
                max_price=price_range["max"],
            )
            inputs.append((url, "Mixed"))

        return inputs

    async def process_search_inputs(
        self, context: BrowserContext, inputs: List[Tuple[str, str]]
    ) -> List[Tuple[str, str]]:
        """
        Visits each search URL and extracts property links.
        """
        sem = asyncio.Semaphore(5)

        async def process_single_search(url, _):
            async with sem:
                page = await context.new_page()
                try:
                    links = await self._extract_links_from_search_page(page, url)
                    # We pass 'Unknown' as barrio, to be resolved in extract_property_details
                    return [(link, "Unknown") for link in links]
                except Exception as e:
                    print(f"[{self.name}] Error processing search {url}: {e}")
                    return []
                finally:
                    await page.close()

        tasks = [process_single_search(url, meta) for url, meta in inputs]
        results_lists = await asyncio.gather(*tasks)

        # Flatten and dedup
        all_links = []
        seen_links = set()
        for r_list in results_lists:
            for link, barrio in r_list:
                if link not in seen_links:
                    seen_links.add(link)
                    all_links.append((link, barrio))

        return all_links

    async def _extract_links_from_search_page(
        self, page: Page, search_url: str
    ) -> List[str]:
        await page.goto(search_url)
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass

        try:
            # Selector for property cards/links identified by subagent
            await page.wait_for_selector("a.inmueblelink", timeout=10000)
        except:
            print(f"[{self.name}] No results or timeout for {search_url}")
            return []

        links = []
        # Use the specific selector found
        property_links = await page.locator("a.inmueblelink").all()

        for link_el in property_links:
            href = await link_el.get_attribute("href")
            if href:
                if not href.startswith("http"):
                    href = (
                        BASE_URL.rstrip("/") + href
                        if href.startswith("/")
                        else BASE_URL + href
                    )
                links.append(href)

        return list(set(links))

    async def extract_property_details(
        self, page: Page, link: str, _meta_barrio: str
    ) -> Optional[Property]:
        await page.goto(link)
        await page.wait_for_load_state("domcontentloaded")

        # 1. Extract Details
        title = ""
        try:
            # Try specific class or h1
            title_el = page.locator("h1").first
            if await title_el.count() > 0:
                title = await title_el.inner_text()
            else:
                title = await page.title()
        except:
            pass

        # 2. Location logic
        location = "Envigado"  # Default
        normalized_link = link.lower()
        found_barrio = ""
        for barrio in BARRIOS_LIST:
            slug = barrio.lower().replace(" ", "-")
            slug_underscore = barrio.lower().replace(" ", "_")
            if slug in normalized_link or slug_underscore in normalized_link:
                found_barrio = barrio
                break
        if found_barrio:
            location = found_barrio

        # 3. Attributes using simple text search for labels provided by user
        # Labels: Área cons, Baños, Alcobas, Garaje, Estrato

        price = ""
        area = ""
        bedrooms = ""
        bathrooms = ""
        parking = ""
        estrato = ""
        description = ""

        # Price often has specific class or unique formatting
        try:
            price_el = page.locator(".precio-inmueble, .price").first
            if await price_el.count() > 0:
                price = await price_el.inner_text()
        except:
            pass

        # Helper to find value text near a label
        async def get_value_for_label(label_pattern):
            try:
                # Locator for an element containing the label
                # We often need the sibling or parent's other child.
                # Let's try finding the element with text, then looking at siblings/children.
                element = page.locator(f"text=/{label_pattern}/i").first
                if await element.count() > 0:
                    # Case 1: Value is in a sibling span or div
                    # Case 2: Value is in the same element text
                    # Let's try getting text of parent or self
                    text = await element.inner_text()
                    # If text contains value, extract it.
                    # If text is just label, look at next sibling.
                    clean_text = text.strip()
                    # If just label, get sibling
                    if len(clean_text) < len(label_pattern) + 5:  # heuristic
                        # Try next sibling
                        sibling = element.locator("xpath=following-sibling::*[1]")
                        if await sibling.count() > 0:
                            return await sibling.inner_text()
                        # Try parent's text if it's a list item
                        parent = element.locator("xpath=..")
                        return await parent.inner_text()
                    return text
            except:
                pass
            return ""

        # Or simpler: get full text content and use regex which is often more robust for simple sites
        # Strip html tags for cleaner regex? Or just search raw.
        # Let's use page.inner_text('body') which gives visible text
        full_text = await page.locator("body").inner_text()

        def extract_with_regex(pattern, text):
            match = re.search(pattern, text, re.IGNORECASE)
            return match.group(1) if match else ""

        if not price:
            # $ 2.500.000
            price = extract_with_regex(r"\$\s*([\d\.\,]+)", full_text)

        area = extract_with_regex(
            r"Área\s*(?:cons|privada)?\s*:\s*(\d+[\.,]?\d*)\s*m", full_text
        )
        if not area:
            area = extract_with_regex(r"(\d+[\.,]?\d*)\s*m2", full_text)

        bedrooms = extract_with_regex(
            r"(?:Alcobas|Habitaciones)\s*:\s*(\d+)", full_text
        )
        bathrooms = extract_with_regex(r"Baños\s*:\s*(\d+)", full_text)
        parking = extract_with_regex(r"(?:Garaje|Parqueadero)s?\s*:\s*(\d+)", full_text)
        estrato = extract_with_regex(r"Estrato\s*:?\s*(\d+)", full_text)

        # Description
        try:
            # Try multiple selectors
            desc_el = page.locator(
                "#descripcion, .descripcion, .description, .detalle-inmueble"
            ).first
            if await desc_el.count() > 0:
                description = await desc_el.inner_text()
            else:
                # Fallback: finding text block after "Descripción"
                # Use a broader text search for the header
                desc_label = (
                    page.locator("h2, h3, strong, b")
                    .filter(has_text="Descripción")
                    .first
                )
                if await desc_label.count() > 0:
                    # Get the next sibling p or div
                    description = await desc_label.locator(
                        "xpath=following-sibling::*[1]"
                    ).inner_text()
        except:
            pass

        # 5. Images
        images = []
        try:
            # Subagent identified .itemslider as the specific class for gallery images
            # Wait for it to appear (carousel might be lazy loaded)
            try:
                await page.wait_for_selector(".itemslider", timeout=4000)
            except:
                pass

            imgs = await page.locator(".itemslider").all()
            for img in imgs:
                src = await img.get_attribute("src")
                if src and src.startswith("http"):
                    lower = src.lower()
                    if any(
                        x in lower
                        for x in [
                            "logo",
                            "icon",
                            "whatsapp",
                            "facebook",
                            "twitter",
                            "openstreetmap",
                            "psenuevo",
                            "simicrm",
                        ]
                    ):
                        continue
                    if src not in images:
                        images.append(src)
        except:
            pass

        # Code extraction
        code = ""
        match = re.search(
            r"[_-](\d+-\d+|\d+)$", link.rstrip("/")
        )  # Common pattern ending in ID
        if match:
            code = match.group(1)

        # 6. GPS Location
        latitude = None
        longitude = None

        # Method 1: JS Variable (if available via page evaluation)
        # Note: page.evaluate might fail if variable not defined, wrap in try/except
        try:
            # Check if variable exists
            js_data = await page.evaluate(
                "() => window.VISUALINMUEBLE_INMUEBLE || null"
            )
            if js_data:
                latitude = js_data.get("latitud")
                longitude = js_data.get("longitud")
        except:
            pass

        # Method 2: Regex in page content (fallback)
        if latitude is None or longitude is None:
            match_lat = re.search(r'"latitud":\s*([\d.-]+)', full_text)
            match_lng = re.search(r'"longitud":\s*([\d.-]+)', full_text)
            if match_lat and match_lng:
                latitude = float(match_lat.group(1))
                longitude = float(match_lng.group(1))

        # Method 3: Google Maps link (fallback)
        if latitude is None or longitude is None:
            try:
                maps_link = page.locator("a[href*='google.com/maps']").first
                if await maps_link.count() > 0:
                    href = await maps_link.get_attribute("href")
                    # href format often: ...?destination=6.17426,-75.5862
                    match_link = re.search(r"destination=([\d.-]+),([\d.-]+)", href)
                    if match_link:
                        latitude = float(match_link.group(1))
                        longitude = float(match_link.group(2))
            except:
                pass

        return {
            "code": code,
            "title": title.strip(),
            "location": location,
            "price": price.strip(),
            "area": area.strip(),
            "estrato": estrato.strip(),
            "bedrooms": bedrooms.strip(),
            "bathrooms": bathrooms.strip(),
            "parking": parking.strip(),
            # Clean description if it contains the label
            "description": description.replace("Descripción", "").strip(),
            "images": images[:15],  # Limit
            "image_url": images[0] if images else "",
            "link": link,
            "source": "escala_inmobiliaria",
            "latitude": latitude,
            "longitude": longitude,
        }


if __name__ == "__main__":
    # Local test
    scraper = EscalaInmobiliariaScraper()

    async def run_test():
        print("Testing Search Inputs...")
        inputs = await scraper.get_search_inputs()
        print(inputs)

        # Test one search
        # async with async_playwright() as p:
        #     browser = await p.chromium.launch(headless=False)
        #     context = await browser.new_context()
        #     links = await scraper.process_search_inputs(context, inputs)
        #     print(f"Found {len(links)} links")
        #     if links:
        #         print("Testing First Link extraction...")
        #         details = await scraper.extract_property_details(await context.new_page(), links[0][0], links[0][1])
        #         print(details)
        #     await browser.close()

    asyncio.run(run_test())
