import asyncio
import re
from typing import List, Tuple
from playwright.async_api import Page, BrowserContext

from .base import BaseScraper
from .types import Property

# Constants
BASE_URL = "https://arrendamientoslasvegas.com"
SEARCH_URL_TEMPLATE = (
    "https://arrendamientoslasvegas.com/inmuebles/arriendo?"
    "city=5266&type=1&pcmin={min_price}&pcmax={max_price}&"
    "minarea=50&neighborhood={neighborhood}"
)

# Neighborhood Mapping
# Neighborhood Mapping (Search Parameters)
BARRIOS = {
    "Abadia": "La+Abadia+",
    "Beneditinos": "Loma+Benedictinos",
    "La Abadía": "La+Abadia+",
    "El Portal": "El+Portal",
    "La Magnolia": "La+Magnolia",
    "Otra Parte": "Otra+Parte",
    "Pontevedra": "Pontevedra",
    "San Marcos": "San+Marcos",
    "Zuñiga": "Bosques+De+Zuñiga+",
}

# Mapping to Centralized/Unified Barrio Names
UNIFIED_BARRIOS = {
    "Abadia": "La Abadia",
    "Beneditinos": "Loma Benedictinos",
    "La Abadía": "La Abadia",
    "El Portal": "El Portal",
    "La Magnolia": "La Magnolia",
    "Otra Parte": "Otra Parte",
    "Pontevedra": "Pontevedra",
    "San Marcos": "San Marcos",
    "Zuñiga": "Zuñiga",
}


class ArrendamientosLasVegasScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="Arrendamientos Las Vegas", concurrency=3)

    async def get_search_inputs(self) -> List[Tuple[str, str]]:
        inputs = []
        for barrio_name, query_param in BARRIOS.items():
            for price_range in self.PRICE_RANGES:
                min_p = str(price_range["min"])
                max_p = str(price_range["max"])

                url = SEARCH_URL_TEMPLATE.format(
                    min_price=min_p, max_price=max_p, neighborhood=query_param
                )

                # Use unified name if available, else original
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
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass

        links = []
        anchors = await page.locator("a").all()
        for a in anchors:
            href = await a.get_attribute("href")
            if href:
                if "inmuebles/" in href and re.search(r"/\d+$", href):
                    if not href.startswith("http"):
                        href = (
                            BASE_URL + href
                            if href.startswith("/")
                            else f"{BASE_URL}/{href}"
                        )

                    if href not in links:
                        links.append(href)
        return list(set(links))

    async def extract_property_details(
        self, page: Page, link: str, barrio_name: str
    ) -> Property:
        await page.goto(link)
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass

        # Defaults
        title = "Apartamento en Arriendo"
        code = ""
        price = ""
        bedrooms = ""
        bathrooms = ""
        parking = ""
        area = ""
        estrato = ""
        description = ""
        image_url = ""
        images = []

        # Debug info if needed later
        # print(f"Processing: {link}")

        # Title
        try:
            title_el = page.locator("span.text-xl.font-bold").first
            if await title_el.count() > 0:
                title = await title_el.inner_text()
        except:
            pass

        # Code
        try:
            code_label = page.locator("span", has_text="Código del inmueble:")
            if await code_label.count() > 0:
                code_val = code_label.locator("xpath=following-sibling::span[1]")
                if await code_val.count() > 0:
                    code = await code_val.inner_text()
        except:
            pass

        # Features Extraction
        try:
            # Wait for feature chips to appear
            await page.wait_for_selector(
                "span.rounded-lg.bg-neutral-200", state="visible", timeout=10000
            )

            feature_spans = await page.locator("span.rounded-lg.bg-neutral-200").all()

            for span in feature_spans:
                txt = await span.inner_text()
                txt_lower = txt.lower()

                def get_num(s):
                    match = re.search(r"([\d.,]+)", s)
                    if match:
                        return match.group(1).replace(".", "").replace(",", "")
                    return ""

                if "habitacion" in txt_lower or "alcoba" in txt_lower:
                    bedrooms = get_num(txt)
                elif "baño" in txt_lower or "baño" in txt_lower:
                    bathrooms = get_num(txt)
                elif "parqueadero" in txt_lower or "garaje" in txt_lower:
                    parking = get_num(txt)
                elif "m²" in txt_lower or "mts" in txt_lower or "metro" in txt_lower:
                    area = get_num(txt)
                elif "estrato" in txt_lower:
                    estrato = get_num(txt)
                elif "$" in txt:
                    pass

            if not bedrooms and not bathrooms:
                print(f"DEBUG: Features not found for {link}")
                print(f"DEBUG: Page Title: {await page.title()}")
                try:
                    print("DEBUG: Body Text Snippet:")
                    body_text = await page.inner_text("body")
                    print(body_text[:1000])  # Print first 1000 chars
                except:
                    print("Could not get body text")

        except Exception as e:
            print(f"Error parsing features: {e}")
            # Ensure we print debug info even on timeout
            if not bedrooms:
                print(f"DEBUG: Features extraction failed/timed out. URL: {page.url}")
                try:
                    print("DEBUG: Body Text Snippet:")
                    body_text = await page.inner_text("body")
                    print(body_text[:1000])
                except:
                    pass

        # Price
        try:
            price_label = page.locator(
                "span", has_text=re.compile("Precio total:", re.IGNORECASE)
            )
            if await price_label.count() > 0:
                price_val = price_label.locator("xpath=following-sibling::span[1]")
                if await price_val.count() > 0:
                    price = await price_val.inner_text()
        except:
            pass

        # Fallback price search
        if not price:
            try:
                potential_prices = await page.locator("span", has_text="$").all()
                for p_el in potential_prices:
                    txt = await p_el.inner_text()
                    if "$" in txt and any(c.isdigit() for c in txt):
                        if len(txt) < 50:
                            price = txt
                            break
            except:
                pass

        # Description
        try:
            desc_header = page.locator(
                "h3, h4, strong, span", has_text=re.compile("descripci", re.IGNORECASE)
            ).first
            if await desc_header.count() > 0:
                desc_content = desc_header.locator("xpath=following::p[1]")
                if await desc_content.count() > 0:
                    description = await desc_content.first.inner_text()
                else:
                    parent = desc_header.locator("xpath=..")
                    desc_content = parent.locator("xpath=following-sibling::*[1]")
                    if await desc_content.count() > 0:
                        description = await desc_content.first.inner_text()
        except:
            pass

        # Images
        try:
            # Get images only from the main carousel container
            # The container has class "no-scroll" based on debug analysis
            # We target the .first one as debug showed the first one is the main carousel, second is suggestions
            container = page.locator(".no-scroll").first
            imgs = await container.locator("img").all()

            for img in imgs:
                src = await img.get_attribute("src")
                if not src or not src.startswith("http"):
                    continue

                src_lower = src.lower()

                # Exclusion keywords
                if any(
                    x in src_lower
                    for x in [
                        "logo",
                        "icon",
                        "whatsapp",
                        "facebook",
                        "twitter",
                        "instagram",
                        "button",
                        "arrow",
                    ]
                ):
                    continue

                # Check for duplicate
                if src not in images:
                    images.append(src)

            # If we found many images, maybe try to filter for specific high-res domains if identified
            # In the test, we saw "pictures.domus.la".
            # If we have images from domus.la, we might want to prioritize them or ensure we don't miss them.
            # Convert to set for uniqueness
            images = list(dict.fromkeys(images))

        except:
            pass

        if images:
            image_url = images[0]

        # Final cleanup / fallback
        if not code:
            match = re.search(r"/(\d+)$", link)
            if match:
                code = match.group(1)

        # GPS Extraction (Mapbox)
        latitude = None
        longitude = None
        try:
            # The coordinates are often in the "Improve this map" link
            # format: https://www.mapbox.com/map-feedback/#/-75.57592/6.1766/15
            mapbox_link = page.locator("a.mapbox-improve-map").first
            if await mapbox_link.count() > 0:
                href = await mapbox_link.get_attribute("href")
                if href and "#" in href:
                    # href might be like https://apps.mapbox.com/feedback/#/-75.57592/6.1766/15
                    parts = href.split("#")[-1].split("/")
                    # parts might be ['', '-75.57592', '6.1766', '15'] or similar
                    # Filter out empty strings
                    coords = [p for p in parts if p]
                    if len(coords) >= 2:
                        # Usually it is /lng/lat/zoom
                        lon_val = float(coords[0])
                        lat_val = float(coords[1])

                        # Sanity check for Medellin/Envigado area
                        # Lat approx 6.0 to 6.3, Lon approx -75.6 to -75.5
                        if 6.0 <= lat_val <= 6.4 and -76.0 <= lon_val <= -75.0:
                            latitude = lat_val
                            longitude = lon_val
        except Exception as e:
            print(f"Error extracting GPS: {e}")

        return {
            "code": code,
            "title": title,
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
            "source": "arrendamientos_las_vegas",
            "description": description,
            "latitude": latitude,
            "longitude": longitude,
        }
