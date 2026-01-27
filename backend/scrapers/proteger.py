import re
from typing import List, Tuple
from playwright.async_api import Page

from .base import BaseScraper, ScraperConfig
from .types import Property

# Constants for Inmobiliaria Proteger
PROTEGER_BASE_URL = "https://inmobiliariaproteger.com"

# Search URL with placeholders
# Note: min_price and max_price need dots (e.g. 2.500.000)
SEARCH_URL_TEMPLATE = (
    "https://inmobiliariaproteger.com/s?"
    "id_country=1&id_region=2&id_city=291&id_location=&"
    "id_zone={zone_id}&"
    "id_property_type=2&id_property_condition=&"
    "business_type%5B%5D=for_rent&"
    "bedrooms=&bathrooms=&"
    "min_price={min_price}&max_price={max_price}"
)

# Zone IDs discovered
BARRIOS = {
    "Abadia": "388040",
    "Beneditinos": "377268",
    "El Portal": "377212",
    "La Abadía": "388041",
    "La Magnolia": "377213",
    "Otra Parte": "667091",
    "Pontevedra": "377215",
    "San Marcos": "377214",
    "Zuniga": "377226",  # Using Zuñiga ID
}

# Unified Name Mapping
UNIFIED_BARRIOS = {
    "Abadia": "La Abadia",
    "Beneditinos": "Loma Benedictinos",
    "La Abadía": "La Abadia",
    "La Magnolia": "La Magnolia",
    "Otra Parte": "Otra Parte",
    "Pontevedra": "Pontevedra",
    "San Marcos": "San Marcos",
    "Zuniga": "Zuñiga",
}


class ProtegerScraper(BaseScraper):
    def __init__(self):
        config = ScraperConfig(
            detail_concurrency=3,
            search_concurrency=5,
        )
        super().__init__(name="Inmobiliaria Proteger", config=config)

    async def get_search_inputs(self) -> List[Tuple[str, str]]:
        inputs = []
        for barrio_name, zone_id in BARRIOS.items():
            for price_range in self.PRICE_RANGES:
                # Format prices with dots
                min_p = f"{price_range['min']:,}".replace(",", ".")
                max_p = f"{price_range['max']:,}".replace(",", ".")

                url = SEARCH_URL_TEMPLATE.format(
                    zone_id=zone_id, min_price=min_p, max_price=max_p
                )

                unified_name = UNIFIED_BARRIOS.get(barrio_name, barrio_name)
                inputs.append((url, unified_name))
        return inputs

    # process_search_inputs() is inherited from BaseScraper

    async def _extract_links_from_search_page(
        self, page: Page, search_url: str
    ) -> List[str]:
        await self.navigate_and_wait(page, search_url)

        links = []
        anchors = await page.locator("a").all()
        for a in anchors:
            href = await a.get_attribute("href")
            if href:
                # Filter valid property links
                # Must NOT contain /s/ (search), ? (query params), or other known non-property paths
                if (
                    "/s/" in href
                    or "?" in href
                    or "search?" in href
                    or "business_type" in href
                ):
                    continue

                # Must match typical property structure
                # https://inmobiliariaproteger.com/apartamento-alquiler-la-magnolia-envigado/9420502
                is_valid = False
                if "apartamento" in href and "alquiler" in href:
                    is_valid = True
                elif re.search(r"/\d+$", href) and "inmobiliariaproteger.com" in href:
                    is_valid = True

                if is_valid:
                    href = self.normalize_url(href, PROTEGER_BASE_URL)
                    if href not in links and href != search_url:
                        links.append(href)

        return list(set(links))

    async def extract_property_details(
        self, page: Page, link: str, barrio_name: str
    ) -> Property:
        await self.navigate_and_wait(page, link)

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
            title = await page.title()
            title = title.split("-")[0].strip()
        except:
            pass

        # Details Extraction with Parent Fallback
        async def get_value(label_text):
            try:
                elements = await page.locator(
                    f"xpath=//*[contains(text(), '{label_text}')]"
                ).all()

                for el in elements:

                    def clean_val(v):
                        v = (
                            v.replace(label_text, "")
                            .replace(":", "")
                            .replace(".", "")
                            .strip()
                        )
                        if len(v) > 50:
                            return ""
                        return v

                    txt = await el.inner_text()
                    val = clean_val(txt)
                    if val:
                        return val

                    parent = el.locator("xpath=..")
                    p_txt = await parent.inner_text()
                    val = clean_val(p_txt)
                    if val:
                        return val

                    sibling = el.locator("xpath=following-sibling::*[1]")
                    if await sibling.count() > 0:
                        s_txt = await sibling.inner_text()
                        if len(s_txt) < 50:
                            return s_txt.strip()
            except:
                pass
            return ""

        # Price extraction
        try:
            price_el = page.locator(
                ".price, .precio, .property-price, .precio-inmueble"
            ).first
            if await price_el.count() > 0:
                price = await price_el.inner_text()
            else:
                headers = await page.locator("h1, h2, h3, h4, strong, span").all()
                for h in headers:
                    txt = await h.inner_text()
                    if "$" in txt and any(c.isdigit() for c in txt) and "COP" in txt:
                        clean_p = txt.strip()
                        if len(clean_p) < 40:
                            price = clean_p
                            break
        except:
            pass

        if not price:
            try:
                t_str = await page.title()
                if "-" in t_str:
                    parts = t_str.split("-")
                    for p in reversed(parts):
                        if "$" in p or "COP" in p:
                            price = p.strip()
                            break
            except:
                pass

        code = await get_value("Código")
        area = (
            await get_value("Área Construida")
            or await get_value("Área Privada")
            or await get_value("Área")
        )
        bedrooms = await get_value("Alcoba") or await get_value("Habitaciones")
        bathrooms = await get_value("Baños")
        parking = await get_value("Garaje") or await get_value("Parqueadero")
        estrato = await get_value("Estrato")

        # Description
        try:
            desc_el = page.locator("#description, .description").first
            if await desc_el.count() > 0:
                description = await desc_el.inner_text()
        except:
            pass

        # Images - using filter utility
        try:
            try:
                await page.wait_for_selector(".swiper-slide", timeout=5000)
            except:
                pass

            raw_images = []
            imgs = await page.locator(".swiper-slide img").all()
            for img in imgs:
                src = await img.get_attribute("src")
                if src:
                    raw_images.append(src)

            images = self.filter_property_images(raw_images)
        except:
            pass

        if images:
            image_url = images[0]

        # Refine Code
        if not code:
            match = re.search(r"/(\d+)$", link)
            if match:
                code = match.group(1)

        # Refine Price
        if not price:
            try:
                t_str = await page.title()
                if "-" in t_str:
                    parts = t_str.split("-")
                    for p in reversed(parts):
                        if "$" in p or "COP" in p:
                            price = p.strip()
                            break
            except:
                pass

        if not price:
            try:
                price = await page.evaluate(
                    """() => {
                     const headers = Array.from(document.querySelectorAll('h1, h2, h3, .price, .precio'));
                     for (const h of headers) {
                        if (h.innerText.includes('$')) return h.innerText;
                     }
                     return '';
                 }"""
                )
            except:
                pass

        # Extract GPS using base utility
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
            "source": "proteger",
            "description": description,
            "latitude": latitude,
            "longitude": longitude,
        }
